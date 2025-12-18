# Setting Up Pipeline in Research Repo

This guide shows how to use the pipeline template in your research repository.

## Structure

**Tools Repo (dh4pmp_tools):**
- `packages/pipelines/` - Standalone pipeline framework package
- `packages/web_fetcher/` - PDF fetching utilities

**Research Repo (your private repo):**
- `data/pipeline.py` - Main pipeline orchestrator
- `data/stages/` - Stage implementations
- `data/config/` - Pipeline configuration

## Setup in Research Repo

### 1. Install the required packages

```bash
# In your research repo
pip install -e /path/to/dh4pmp_tools/packages/pipelines
pip install -e /path/to/dh4pmp_tools/packages/web_fetcher
```

Or if you have the tools repo as a submodule:
```bash
pip install -e ./submodules/dh4pmp_tools/packages/pipelines
pip install -e ./submodules/dh4pmp_tools/packages/web_fetcher
```

### 2. Copy the template to your research repo

```bash
# In your research repo
mkdir -p data
cp /path/to/dh4pmp_tools/packages/web_fetcher/examples/pdf_download_pipeline_template.py \
   data/download_pdfs.py
```

### 3. Customize for your needs

Edit `data/download_pdfs.py` to:
- Add your specific validation logic
- Customize processing steps
- Add research-specific metadata handling
- Integrate with your other tools

### 4. Use it

```bash
# In your research repo
python data/download_pdfs.py \
    --input-file data/input/dois.txt \
    --output-dir ./data/pdfs \
    --verbose
```

## Example: Custom Pipeline

You can extend the base class for your specific needs:

```python
# In your research repo: data/my_custom_pipeline.py

from pipelines import BasePipeline, PipelineConfig

class MyCustomPipeline(BasePipeline):
    """My research-specific pipeline."""
    
    def validate_inputs(self) -> bool:
        # Your validation
        return True
    
    def process_data(self):
        # Your processing
        # Can use PDFFetcher, api_clients, etc.
        pass
    
    # ... implement other abstract methods
```

## Benefits

1. **Reusable base**: The `BasePipeline` class stays in tools repo (version controlled, shareable)
2. **Research-specific**: Your pipeline in research repo can be customized without affecting the base
3. **Easy updates**: Update tools repo, your pipeline automatically gets improvements
4. **Separation**: Tools repo stays clean, research repo has your specific code

## File Locations

```
dh4pmp_tools/                          (Tools repo - public)
├── packages/web_fetcher/
│   ├── web_fetcher/
│   │   └── pipeline_base.py          ← Generic base class
│   └── examples/
│       ├── pdf_download_pipeline_template.py  ← Template
│       └── RESEARCH_REPO_SETUP.md     ← This file

your_research_repo/                    (Research repo - private)
├── data/
│   ├── download_pdfs.py               ← Your specific pipeline
│   ├── input/
│   │   └── dois.txt
│   └── pdfs/
└── .gitignore                         (exclude pdfs/, logs/, etc.)
```

