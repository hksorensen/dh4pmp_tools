# Pipeline Architecture

## Overview

The pipeline system is designed with a **separation of concerns**:

- **Tools Repo** (`dh4pmp_tools`): Contains reusable `BasePipeline` class
- **Research Repo**: Contains your specific pipeline implementations

## Structure

```
dh4pmp_tools/                          (Tools repo - public)
├── packages/pipelines/                ← Standalone pipeline framework
│   ├── pipelines/
│   │   ├── pipeline_base.py           ← Generic BasePipeline class
│   │   ├── checkpoint_manager.py      ← Checkpoint management
│   │   ├── stage_orchestrator.py      ← Stage orchestration
│   │   └── status_tracker.py          ← Status tracking
│   └── README.md
├── packages/web_fetcher/
│   └── web_fetcher/
│       └── pdf_fetcher.py              ← PDF downloading utilities
│       ├── RESEARCH_REPO_SETUP.md     ← Setup instructions
│       └── PIPELINE_ARCHITECTURE.md   ← This file

your_research_repo/                    (Research repo - private)
├── data/
│   ├── download_pdfs.py               ← Your specific pipeline
│   ├── input/
│   │   └── dois.txt
│   └── pdfs/
└── .gitignore
```

## BasePipeline Class

The `BasePipeline` class provides:

1. **Abstract methods** (must implement):
   - `validate_inputs()` - Check input data
   - `prepare_environment()` - Setup (dirs, connections, etc.)
   - `process_data()` - Main processing logic
   - `validate_outputs()` - Verify results

2. **Built-in features**:
   - Logging (console + file)
   - Error tracking
   - Result statistics
   - Cleanup handling
   - JSON result export

3. **Lifecycle**:
   ```
   run() → validate_inputs() → prepare_environment() 
        → process_data() → validate_outputs() → cleanup()
   ```

## Usage Pattern

### In Research Repo

```python
# data/download_pdfs.py
from pipelines import BasePipeline, PipelineConfig
from web_fetcher import PDFFetcher

class PDFDownloadPipeline(BasePipeline):
    """Your specific pipeline."""
    
    def validate_inputs(self) -> bool:
        # Your validation
        return True
    
    def process_data(self):
        # Your processing using PDFFetcher
        pass
    
    # ... implement other methods
```

## Benefits

1. **Reusability**: Base class stays in tools repo, shared across projects
2. **Customization**: Research repo has full control over implementation
3. **Maintainability**: Updates to base class benefit all pipelines
4. **Separation**: Tools stay generic, research code stays specific
5. **Version Control**: Tools repo public, research repo private

## Extending for Other Use Cases

The `BasePipeline` is generic enough for:
- PDF downloads (example provided)
- Metadata extraction
- Data transformation
- API data collection
- Any batch processing task

Just subclass and implement the abstract methods!

