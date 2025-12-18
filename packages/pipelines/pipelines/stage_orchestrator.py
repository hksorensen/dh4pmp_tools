"""
Stage Orchestrator - Coordinate multi-stage pipelines.

Manages dependencies, execution order, and parallel execution of pipeline stages.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Callable, Any
from enum import Enum
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class StageStatus(Enum):
    """Status of a pipeline stage."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Stage:
    """
    Represents a pipeline stage.
    
    Attributes:
        name: Unique name for the stage
        pipeline_class: Class that extends BasePipeline
        depends_on: List of stage names this stage depends on
        enabled: Whether this stage should run
        checkpoint: Whether to save checkpoint after this stage
        config: Optional configuration dict for this stage
    """
    name: str
    pipeline_class: Optional[Callable] = None
    depends_on: List[str] = field(default_factory=list)
    enabled: bool = True
    checkpoint: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    status: StageStatus = StageStatus.PENDING
    
    def __post_init__(self):
        """Validate stage configuration."""
        if not self.name:
            raise ValueError("Stage name cannot be empty")
    
    def can_run(self, completed_stages: Set[str]) -> bool:
        """
        Check if this stage can run (all dependencies completed).
        
        Args:
            completed_stages: Set of completed stage names
            
        Returns:
            True if all dependencies are completed
        """
        if not self.enabled:
            return False
        
        # Check if all dependencies are completed
        for dep in self.depends_on:
            if dep not in completed_stages:
                return False
        
        return True


class StageOrchestrator:
    """
    Orchestrate execution of multiple pipeline stages.
    
    Handles:
    - Dependency resolution
    - Execution order
    - Parallel execution of independent stages
    - Checkpoint management
    """
    
    def __init__(self, stages: List[Stage], checkpoint_dir: Optional[Path] = None):
        """
        Initialize orchestrator.
        
        Args:
            stages: List of stages to orchestrate
            checkpoint_dir: Optional directory for checkpoints
        """
        self.stages = {stage.name: stage for stage in stages}
        self.checkpoint_dir = checkpoint_dir
        
        # Validate dependencies
        self._validate_dependencies()
        
        logger.info(f"StageOrchestrator initialized with {len(stages)} stages")
    
    def _validate_dependencies(self):
        """Validate that all dependencies exist and there are no circular dependencies."""
        stage_names = set(self.stages.keys())
        
        # Check all dependencies exist
        for stage in self.stages.values():
            for dep in stage.depends_on:
                if dep not in stage_names:
                    raise ValueError(f"Stage '{stage.name}' depends on unknown stage '{dep}'")
        
        # Check for circular dependencies (simple check)
        # TODO: More sophisticated cycle detection if needed
        for stage in self.stages.values():
            visited = set()
            self._check_cycles(stage.name, visited)
    
    def _check_cycles(self, stage_name: str, visited: Set[str]):
        """Check for circular dependencies."""
        if stage_name in visited:
            raise ValueError(f"Circular dependency detected involving stage '{stage_name}'")
        
        visited.add(stage_name)
        stage = self.stages[stage_name]
        for dep in stage.depends_on:
            self._check_cycles(dep, visited)
        visited.remove(stage_name)
    
    def get_execution_order(self) -> List[List[str]]:
        """
        Get stages grouped by execution order (parallel groups).
        
        Returns:
            List of lists, where each inner list contains stage names that can run in parallel
        """
        execution_groups = []
        completed = set()
        remaining = set(self.stages.keys())
        
        while remaining:
            # Find stages that can run now (all dependencies completed)
            ready = [
                name for name in remaining
                if self.stages[name].can_run(completed)
            ]
            
            if not ready:
                # Circular dependency or missing dependency
                raise ValueError(f"Cannot resolve execution order. Remaining stages: {remaining}")
            
            execution_groups.append(ready)
            remaining -= set(ready)
            # Mark as completed for dependency resolution (actual execution happens later)
            completed.update(ready)
        
        return execution_groups
    
    def run(self, 
            run_stage: Optional[Callable[[Stage], Any]] = None,
            skip_completed: bool = True,
            checkpoint_manager = None) -> Dict[str, Any]:
        """
        Execute all stages in dependency order.
        
        Args:
            run_stage: Optional function to run a stage. If None, uses stage.pipeline_class
            skip_completed: If True, skip stages that are already completed
            checkpoint_manager: Optional CheckpointManager to check for existing checkpoints
            
        Returns:
            Dictionary mapping stage names to results
        """
        execution_order = self.get_execution_order()
        results = {}
        completed_stages = set()
        
        logger.info(f"Executing {len(self.stages)} stages in {len(execution_order)} groups")
        
        for group_idx, stage_group in enumerate(execution_order, 1):
            logger.info(f"Execution group {group_idx}/{len(execution_order)}: {stage_group}")
            
            # Check for checkpoints if skip_completed is enabled
            if skip_completed and checkpoint_manager:
                for stage_name in stage_group[:]:  # Copy list to modify during iteration
                    if checkpoint_manager.exists(stage_name):
                        logger.info(f"Skipping {stage_name} - checkpoint exists")
                        self.stages[stage_name].status = StageStatus.SKIPPED
                        completed_stages.add(stage_name)
                        stage_group.remove(stage_name)
            
            # Execute stages in this group (currently sequential, can be parallelized)
            for stage_name in stage_group:
                stage = self.stages[stage_name]
                
                if not stage.enabled:
                    logger.info(f"Skipping disabled stage: {stage_name}")
                    stage.status = StageStatus.SKIPPED
                    continue
                
                try:
                    logger.info(f"Running stage: {stage_name}")
                    stage.status = StageStatus.RUNNING
                    
                    # Run the stage
                    if run_stage:
                        result = run_stage(stage)
                    elif stage.pipeline_class:
                        # Instantiate and run pipeline
                        pipeline = stage.pipeline_class(**stage.config)
                        result = pipeline.run()
                    else:
                        raise ValueError(f"Stage '{stage_name}' has no pipeline_class or run_stage function")
                    
                    stage.status = StageStatus.COMPLETED
                    completed_stages.add(stage_name)
                    results[stage_name] = result
                    
                    # Save checkpoint if enabled
                    if stage.checkpoint and checkpoint_manager:
                        checkpoint_manager.save(stage_name, result)
                    
                    logger.info(f"Completed stage: {stage_name}")
                    
                except Exception as e:
                    logger.error(f"Stage '{stage_name}' failed: {e}", exc_info=True)
                    stage.status = StageStatus.FAILED
                    results[stage_name] = {"error": str(e), "status": "failed"}
                    # Decide whether to continue or stop
                    # For now, we continue (failures are recorded in results)
        
        return results
    
    def get_status_summary(self) -> Dict[str, str]:
        """Get status summary of all stages."""
        return {
            name: stage.status.value 
            for name, stage in self.stages.items()
        }

