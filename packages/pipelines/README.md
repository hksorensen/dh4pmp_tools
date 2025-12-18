# Pipelines

Reusable data pipeline framework for research workflows.

## Overview

This package provides a generic pipeline infrastructure that can be extended for specific use cases:
- PDF downloads
- Data processing
- Metadata extraction
- API data collection
- Any batch processing task

## Features

- **Generic base class** (`BasePipeline`) with lifecycle management
- **Configuration management** (`PipelineConfig`) with dataclass support
- **Result tracking** (`PipelineResult`) with stats, errors, and warnings
- **Built-in logging** (console + file)
- **Error handling** and reporting
- **JSON result export**
- **Checkpoint management** (`CheckpointManager`) for resumable pipelines
- **Stage orchestration** (`StageOrchestrator`) for multi-stage pipelines
- **Status tracking** (`StatusTracker`) for item-level progress tracking

## Installation

```bash
pip install -e packages/pipelines
```

## Quick Start

```python
from pipelines import BasePipeline, PipelineConfig
from pathlib import Path

class MyPipeline(BasePipeline):
    """Your custom pipeline."""
    
    def validate_inputs(self) -> bool:
        # Check that input data exists
        return True
    
    def prepare_environment(self):
        # Setup directories, connections, etc.
        pass
    
    def process_data(self):
        # Your main processing logic
        pass
    
    def validate_outputs(self) -> bool:
        # Verify results
        return True

# Use it
config = PipelineConfig(
    input_dir=Path("./input"),
    output_dir=Path("./output"),
    log_dir=Path("./logs"),
    verbose=True
)

pipeline = MyPipeline(config)
result = pipeline.run()
```

## Architecture

The pipeline follows a standard lifecycle:

```
run() → validate_inputs() → prepare_environment() 
     → process_data() → validate_outputs() → cleanup()
```

Each step is an abstract method that you implement for your specific use case.

## Example: PDF Download Pipeline

See `packages/web_fetcher/examples/pdf_download_pipeline_template.py` for a complete example using this package with `web_fetcher`.

## Advanced Features

### Checkpoint Manager

Save and load intermediate results:

```python
from pipelines import CheckpointManager
from pathlib import Path

checkpoint_mgr = CheckpointManager(Path("./checkpoints"))

# Save checkpoint
checkpoint_mgr.save("stage1", my_data)

# Load checkpoint
if checkpoint_mgr.exists("stage1"):
    data = checkpoint_mgr.load("stage1")
```

### Stage Orchestrator

Coordinate multi-stage pipelines:

```python
from pipelines import StageOrchestrator, Stage

stages = [
    Stage("prepare", depends_on=[]),
    Stage("process", depends_on=["prepare"]),
    Stage("visualize", depends_on=["prepare"]),  # Can run in parallel
]

orchestrator = StageOrchestrator(stages)
results = orchestrator.run()
```

### Status Tracker

Track individual item processing:

```python
from pipelines import StatusTracker

tracker = StatusTracker(Path("./status.json"))
tracker.initialize_items(["item1", "item2", "item3"])

for item_id in tracker.get_pending():
    tracker.mark_processing(item_id)
    # ... process item ...
    tracker.mark_completed(item_id)
```

## API Reference

### `BasePipeline`

Abstract base class for all pipelines.

**Methods to implement:**
- `validate_inputs() -> bool` - Validate input data
- `prepare_environment()` - Setup environment
- `process_data()` - Main processing logic
- `validate_outputs() -> bool` - Validate results

**Built-in methods:**
- `run() -> PipelineResult` - Execute the pipeline
- `save_results(output_file: Optional[Path]) -> Path` - Save results to JSON
- `cleanup()` - Clean up temporary resources

### `PipelineConfig`

Configuration dataclass for pipelines.

**Fields:**
- `input_dir: Optional[Path]` - Input directory
- `output_dir: Optional[Path]` - Output directory
- `log_dir: Optional[Path]` - Log directory
- `temp_dir: Optional[Path]` - Temporary directory
- `batch_size: int = 100` - Batch size for processing
- `max_retries: int = 3` - Maximum retry attempts
- `verbose: bool = False` - Enable verbose logging

### `PipelineResult`

Result tracking dataclass.

**Fields:**
- `start_time: datetime` - Pipeline start time
- `end_time: Optional[datetime]` - Pipeline end time
- `success: bool` - Whether pipeline succeeded
- `stats: Dict[str, Any]` - Statistics dictionary
- `errors: List[Dict]` - List of errors
- `warnings: List[Dict]` - List of warnings

**Methods:**
- `add_error(error: str, context: Optional[Dict])` - Add an error
- `add_warning(warning: str, context: Optional[Dict])` - Add a warning
- `finish(success: bool = True)` - Mark pipeline as finished
- `to_dict() -> Dict` - Convert to dictionary for JSON export

## Use Cases

### In Research Repo

1. Install the package:
   ```bash
   pip install -e /path/to/dh4pmp_tools/packages/pipelines
   ```

2. Create your pipeline:
   ```python
   from pipelines import BasePipeline, PipelineConfig
   # ... implement your pipeline
   ```

3. Use it:
   ```bash
   python data/my_pipeline.py --input-dir ./input --output-dir ./output
   ```

## Dependencies

This package has **no dependencies** - it's a pure Python framework using only the standard library. This makes it:
- Lightweight
- Easy to install
- Compatible with any Python 3.8+ environment

## License

MIT License - see LICENSE file for details.

