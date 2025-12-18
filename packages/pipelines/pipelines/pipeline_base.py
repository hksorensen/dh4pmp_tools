"""
Base Pipeline Template - Reusable pipeline framework.

This provides a generic pipeline structure that can be extended for specific use cases.
Use this in your research repo by importing and subclassing.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict


@dataclass
class PipelineConfig:
    """Base configuration for pipelines."""
    input_dir: Optional[Path] = None
    output_dir: Optional[Path] = None
    log_dir: Optional[Path] = None
    temp_dir: Optional[Path] = None
    batch_size: int = 100
    max_retries: int = 3
    verbose: bool = False
    
    def __post_init__(self):
        """Create directories."""
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        if self.temp_dir:
            self.temp_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class PipelineResult:
    """Track pipeline execution results."""
    start_time: datetime
    end_time: Optional[datetime] = None
    success: bool = False
    stats: Dict[str, Any] = None
    errors: List[Dict] = None
    warnings: List[Dict] = None
    
    def __post_init__(self):
        if self.stats is None:
            self.stats = {}
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
    
    def add_error(self, error: str, context: Optional[Dict] = None):
        """Add an error with optional context."""
        self.errors.append({
            'error': error,
            'context': context or {},
            'timestamp': datetime.now().isoformat()
        })
    
    def add_warning(self, warning: str, context: Optional[Dict] = None):
        """Add a warning with optional context."""
        self.warnings.append({
            'warning': warning,
            'context': context or {},
            'timestamp': datetime.now().isoformat()
        })
    
    def finish(self, success: bool = True):
        """Mark pipeline as finished."""
        self.end_time = datetime.now()
        self.success = success
    
    @property
    def duration(self) -> float:
        """Get pipeline duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'success': self.success,
            'duration_seconds': self.duration,
            'stats': self.stats,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings),
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
        }


class BasePipeline(ABC):
    """
    Base pipeline class that can be extended for specific use cases.
    
    Subclass this in your research repo to create custom pipelines.
    
    Example:
        class MyPipeline(BasePipeline):
            def validate_inputs(self) -> bool:
                # Your validation logic
                return True
            
            def process_data(self):
                # Your processing logic
                pass
    """
    
    def __init__(self, config: PipelineConfig, logger: Optional[logging.Logger] = None):
        """
        Initialize pipeline.
        
        Args:
            config: Pipeline configuration
            logger: Optional logger (will create one if not provided)
        """
        self.config = config
        self.result = PipelineResult(start_time=datetime.now())
        
        if logger:
            self.logger = logger
        else:
            self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging if not provided."""
        level = logging.DEBUG if self.config.verbose else logging.INFO
        
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(level)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_format = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)
        
        # File handler (if log_dir specified)
        if self.config.log_dir:
            log_file = self.config.log_dir / f"{self.__class__.__name__.lower()}.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)
        
        return logger
    
    def run(self) -> PipelineResult:
        """
        Execute the pipeline.
        
        This is the main entry point. It calls the abstract methods
        in order: validate_inputs -> prepare_environment -> process_data -> validate_outputs -> cleanup
        """
        self.logger.info("=" * 80)
        self.logger.info(f"Starting {self.__class__.__name__}")
        self.logger.info("=" * 80)
        self.logger.info(f"Configuration: {self._config_to_dict()}")
        
        try:
            # Step 1: Validate inputs
            self.logger.info("Step 1: Validating inputs...")
            if not self.validate_inputs():
                raise ValueError("Input validation failed")
            
            # Step 2: Prepare environment
            self.logger.info("Step 2: Preparing environment...")
            self.prepare_environment()
            
            # Step 3: Process data
            self.logger.info("Step 3: Processing data...")
            self.process_data()
            
            # Step 4: Validate outputs
            self.logger.info("Step 4: Validating outputs...")
            if not self.validate_outputs():
                raise ValueError("Output validation failed")
            
            # Step 5: Cleanup
            self.logger.info("Step 5: Cleaning up...")
            self.cleanup()
            
            self.result.finish(success=True)
            self.logger.info("=" * 80)
            self.logger.info("Pipeline completed successfully!")
            self.logger.info(f"Duration: {self.result.duration:.2f} seconds")
            self.logger.info(f"Stats: {self.result.stats}")
            self.logger.info("=" * 80)
            
        except Exception as e:
            self.result.finish(success=False)
            self.result.add_error(str(e), {'exception_type': type(e).__name__})
            self.logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise
        
        return self.result
    
    def _config_to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for logging."""
        return {
            'input_dir': str(self.config.input_dir) if self.config.input_dir else None,
            'output_dir': str(self.config.output_dir) if self.config.output_dir else None,
            'batch_size': self.config.batch_size,
            'max_retries': self.config.max_retries,
        }
    
    # Abstract methods - must be implemented by subclasses
    @abstractmethod
    def validate_inputs(self) -> bool:
        """Validate input data exists and is valid. Returns True if valid."""
        pass
    
    @abstractmethod
    def prepare_environment(self):
        """Prepare working environment (create dirs, init connections, etc.)."""
        pass
    
    @abstractmethod
    def process_data(self):
        """Main data processing logic."""
        pass
    
    @abstractmethod
    def validate_outputs(self) -> bool:
        """Validate output data. Returns True if valid."""
        pass
    
    def cleanup(self):
        """Clean up temporary files/resources. Override if needed."""
        if self.config.temp_dir and self.config.temp_dir.exists():
            import shutil
            try:
                shutil.rmtree(self.config.temp_dir)
                self.logger.debug(f"Cleaned up {self.config.temp_dir}")
            except Exception as e:
                self.logger.warning(f"Could not clean up temp directory: {e}")
    
    def save_results(self, output_file: Optional[Path] = None) -> Path:
        """Save pipeline results to JSON."""
        if not output_file:
            if self.config.output_dir:
                output_file = self.config.output_dir / f"pipeline_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            else:
                output_file = Path(f"pipeline_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(self.result.to_dict(), f, indent=2)
        
        return output_file


def load_config_from_file(config_file: Path, default_config: Optional[Dict] = None) -> Dict:
    """Load configuration from JSON file."""
    if config_file.exists():
        with open(config_file) as f:
            config_data = json.load(f)
            if default_config:
                default_config.update(config_data)
                return default_config
            return config_data
    return default_config or {}

