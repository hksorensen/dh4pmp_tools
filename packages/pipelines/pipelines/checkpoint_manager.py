"""
Checkpoint Manager - Generic checkpoint system for pipelines.

Saves and loads intermediate results to allow resumable pipelines.
"""

import pickle
import json
from pathlib import Path
from typing import Any, Optional, Dict
import hashlib
import logging

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manage checkpoints for pipeline stages.
    
    Allows saving/loading intermediate results to enable:
    - Resuming from failures
    - Skipping completed stages
    - Debugging intermediate states
    """
    
    def __init__(self, checkpoint_dir: Path):
        """
        Initialize checkpoint manager.
        
        Args:
            checkpoint_dir: Directory to store checkpoints
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"CheckpointManager initialized with directory: {checkpoint_dir}")
    
    def _get_checkpoint_path(self, stage_name: str, extension: str = ".pkl") -> Path:
        """Get path for a checkpoint file."""
        # Sanitize stage name for filename
        safe_name = stage_name.replace("/", "_").replace("\\", "_")
        return self.checkpoint_dir / f"{safe_name}{extension}"
    
    def save(self, stage_name: str, data: Any, format: str = "pickle") -> Path:
        """
        Save checkpoint data.
        
        Args:
            stage_name: Name of the stage (used as filename)
            data: Data to save (any Python object)
            format: Format to use ('pickle' or 'json')
            
        Returns:
            Path to saved checkpoint file
        """
        if format == "pickle":
            checkpoint_path = self._get_checkpoint_path(stage_name, ".pkl")
            with open(checkpoint_path, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"Saved checkpoint: {checkpoint_path}")
        elif format == "json":
            checkpoint_path = self._get_checkpoint_path(stage_name, ".json")
            # Only works for JSON-serializable data
            with open(checkpoint_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            logger.info(f"Saved checkpoint: {checkpoint_path}")
        else:
            raise ValueError(f"Unknown format: {format}. Use 'pickle' or 'json'")
        
        return checkpoint_path
    
    def load(self, stage_name: str, format: Optional[str] = None) -> Any:
        """
        Load checkpoint data.
        
        Args:
            stage_name: Name of the stage
            format: Format to use ('pickle' or 'json'). If None, auto-detect.
            
        Returns:
            Loaded data
            
        Raises:
            FileNotFoundError: If checkpoint doesn't exist
        """
        # Try to auto-detect format
        if format is None:
            pickle_path = self._get_checkpoint_path(stage_name, ".pkl")
            json_path = self._get_checkpoint_path(stage_name, ".json")
            
            if pickle_path.exists():
                format = "pickle"
                checkpoint_path = pickle_path
            elif json_path.exists():
                format = "json"
                checkpoint_path = json_path
            else:
                raise FileNotFoundError(f"Checkpoint not found: {stage_name}")
        else:
            checkpoint_path = self._get_checkpoint_path(
                stage_name, 
                ".pkl" if format == "pickle" else ".json"
            )
        
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
        
        if format == "pickle":
            with open(checkpoint_path, 'rb') as f:
                data = pickle.load(f)
        elif format == "json":
            with open(checkpoint_path, 'r') as f:
                data = json.load(f)
        else:
            raise ValueError(f"Unknown format: {format}")
        
        logger.info(f"Loaded checkpoint: {checkpoint_path}")
        return data
    
    def exists(self, stage_name: str) -> bool:
        """
        Check if checkpoint exists.
        
        Args:
            stage_name: Name of the stage
            
        Returns:
            True if checkpoint exists, False otherwise
        """
        pickle_path = self._get_checkpoint_path(stage_name, ".pkl")
        json_path = self._get_checkpoint_path(stage_name, ".json")
        return pickle_path.exists() or json_path.exists()
    
    def remove(self, stage_name: str) -> bool:
        """
        Remove a checkpoint.
        
        Args:
            stage_name: Name of the stage
            
        Returns:
            True if checkpoint was removed, False if it didn't exist
        """
        pickle_path = self._get_checkpoint_path(stage_name, ".pkl")
        json_path = self._get_checkpoint_path(stage_name, ".json")
        
        removed = False
        if pickle_path.exists():
            pickle_path.unlink()
            removed = True
            logger.debug(f"Removed checkpoint: {pickle_path}")
        if json_path.exists():
            json_path.unlink()
            removed = True
            logger.debug(f"Removed checkpoint: {json_path}")
        
        return removed
    
    def list_checkpoints(self) -> Dict[str, Path]:
        """
        List all available checkpoints.
        
        Returns:
            Dictionary mapping stage names to checkpoint paths
        """
        checkpoints = {}
        for path in self.checkpoint_dir.glob("*"):
            if path.suffix in (".pkl", ".json"):
                stage_name = path.stem
                checkpoints[stage_name] = path
        return checkpoints
    
    def clear_all(self) -> int:
        """
        Clear all checkpoints.
        
        Returns:
            Number of checkpoints removed
        """
        count = 0
        for path in self.checkpoint_dir.glob("*"):
            if path.suffix in (".pkl", ".json"):
                path.unlink()
                count += 1
        logger.info(f"Cleared {count} checkpoints")
        return count

