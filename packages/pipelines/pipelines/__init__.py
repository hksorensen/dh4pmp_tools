"""
Data Pipeline Framework - Reusable pipeline infrastructure.

This package provides a generic pipeline framework that can be extended
for specific use cases (PDF downloads, data processing, etc.).

The base classes are independent of any specific tool or library, making
them reusable across different projects.
"""

from .pipeline_base import BasePipeline, PipelineConfig, PipelineResult
from .checkpoint_manager import CheckpointManager
from .stage_orchestrator import StageOrchestrator, Stage, StageStatus
from .status_tracker import StatusTracker, ItemStatus

__version__ = "1.0.0"
__all__ = [
    "BasePipeline", 
    "PipelineConfig", 
    "PipelineResult",
    "CheckpointManager",
    "StageOrchestrator",
    "Stage",
    "StageStatus",
    "StatusTracker",
    "ItemStatus",
]

