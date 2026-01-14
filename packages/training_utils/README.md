# Training Utilities

Comprehensive utilities for training diagram detection models with YOLO.

## Features

### Data Preparation
- **XML to YOLO Conversion**: Convert PASCAL VOC XML annotations to YOLO format
- **Dataset Splitting**: Automatic train/val/test splits
- **Background Filtering**: Handle negative examples correctly
- **Zip File Support**: Process datasets directly from zip archives

### Dataset Analysis
- **YOLO Dataset Statistics**: Comprehensive dataset analysis and reporting
- **Validation**: Check image-label pairing, format, and bbox ranges
- **Duplicate Detection**: Find duplicate files across splits
- **Bbox Distribution Analysis**: Analyze bbox size and aspect ratio distributions

### Training Analysis
- **Metrics Parsing**: Parse and analyze YOLO training results
- **Best Epoch Detection**: Find optimal training checkpoint
- **Overfitting Detection**: Identify training issues automatically
- **Run Comparison**: Compare multiple training runs
- **Convergence Analysis**: Detect when training has converged

### Model Management
- **Checkpoint Management**: List, backup, and verify model checkpoints
- **Checksum Verification**: Ensure checkpoint integrity
- **Cleanup Tools**: Remove old checkpoints to save space
- **Archiving**: Archive checkpoints with metadata

### Augmentation
- **Configuration Validation**: Validate augmentation parameters
- **Preset Configurations**: Conservative, aggressive, and no-aug presets
- **Strength Estimation**: Analyze augmentation aggressiveness
- **Effective Dataset Size**: Estimate training variety from augmentation

## Installation

```bash
cd /Users/fvb832/Documents/dh4pmp_tools/packages/training_utils
pip install -e .
```

## Usage

### Convert Dataset from Zip File

```python
from training_utils import convert_dataset_from_zip
from pathlib import Path

convert_dataset_from_zip(
    zip_path=Path('dataset.zip'),
    output_dir=Path('yolo_dataset'),
    val_split=0.15,
    test_split=0.15,
    seed=42,
    filter_backgrounds=True  # Exclude images without objects
)
```

### Convert Dataset from Directory

```python
from training_utils import convert_dataset_from_dir
from pathlib import Path

convert_dataset_from_dir(
    input_dir=Path('dataset'),  # Should contain images/ and annotations/
    output_dir=Path('yolo_dataset'),
    val_split=0.15,
    test_split=0.15,
    seed=42
)
```

### Parse Individual XML Annotations

```python
from training_utils import parse_xml_annotation, convert_bbox_to_yolo
from pathlib import Path

# Parse XML file
annotation = parse_xml_annotation(Path('annotation.xml'))

# Or parse from bytes (e.g., from zip)
annotation = parse_xml_annotation(xml_bytes)

# Get image info
width = annotation['size']['width']
height = annotation['size']['height']

# Convert bboxes to YOLO format
for obj in annotation['objects']:
    bbox = obj['bbox']  # {xmin, ymin, xmax, ymax}
    x_center, y_center, w, h = convert_bbox_to_yolo(bbox, width, height)
    print(f"Class: {obj['class']}, YOLO bbox: {x_center:.4f} {y_center:.4f} {w:.4f} {h:.4f}")
```

### Create Class Mapping

```python
from training_utils import create_class_mapping, create_class_mapping_from_zip
from pathlib import Path

# From directory of XML files
class_to_id = create_class_mapping(Path('annotations'))
# Returns: {'diagram': 0, 'flowchart': 1, ...}

# From zip file
class_to_id = create_class_mapping_from_zip(Path('dataset.zip'))
```

## Use in Jupyter Notebooks

```python
# In a Jupyter notebook
from pathlib import Path
from training_utils import convert_dataset_from_zip

# Convert dataset
convert_dataset_from_zip(
    zip_path=Path('../data/raw/annotations.zip'),
    output_dir=Path('../data/processed/yolo_dataset'),
    val_split=0.15,
    test_split=0.15
)

# Results will be in yolo_dataset/ with structure:
# yolo_dataset/
#   images/
#     train/
#     val/
#     test/
#   labels/
#     train/
#     val/
#     test/
#   dataset.yaml
#   classes.txt
```

## Output Format

### Directory Structure

```
yolo_dataset/
├── images/
│   ├── train/
│   │   ├── image001.png
│   │   └── ...
│   ├── val/
│   └── test/
├── labels/
│   ├── train/
│   │   ├── image001.txt
│   │   └── ...
│   ├── val/
│   └── test/
├── dataset.yaml      # YOLO dataset config
└── classes.txt       # Class names
```

### YOLO Label Format

Each label file contains one line per object:
```
class_id x_center y_center width height
```

All values are normalized to [0, 1].

Example label file:
```
0 0.5 0.6 0.3 0.2
0 0.2 0.3 0.15 0.1
```

### dataset.yaml

```yaml
path: .
train: images/train
val: images/val
test: images/test
names:
  0: diagram
  1: flowchart
```

## Background Handling

The converter handles three types of images:

1. **Images with objects**: Annotations with class names (e.g., "diagram")
   - Included in train/val/test splits
   - Label files contain bbox annotations

2. **Verified backgrounds**: Annotations with only `class="bg"`
   - Saved to `backgrounds/` directory
   - Can be used as test negatives for F1 evaluation
   - NOT included in training by default

3. **Unannotated images**: PNG files without corresponding XML
   - Ignored (not included in any split)
   - These are NOT considered backgrounds since they haven't been verified

### Including Backgrounds in Training

```python
convert_dataset_from_zip(
    zip_path='dataset.zip',
    output_dir='yolo_dataset',
    filter_backgrounds=False  # Include backgrounds in training
)
```

## Coordinate Conversion

### PASCAL VOC Format (Input)
- Top-left corner + bottom-right corner
- Absolute pixel coordinates
- Format: `[xmin, ymin, xmax, ymax]`

### YOLO Format (Output)
- Center + dimensions
- Normalized to [0, 1]
- Format: `[x_center, y_center, width, height]`

Conversion formula:
```python
x_center = (xmin + xmax) / 2 / img_width
y_center = (ymin + ymax) / 2 / img_height
width = (xmax - xmin) / img_width
height = (ymax - ymin) / img_height
```

## Advanced Usage

### Custom Split Ratios

```python
convert_dataset_from_zip(
    zip_path='dataset.zip',
    output_dir='yolo_dataset',
    val_split=0.2,    # 20% validation
    test_split=0.1,   # 10% test
    seed=123          # Custom random seed
)
# Remaining 70% will be used for training
```

### Reproducible Splits

Use the same `seed` value to get identical splits:

```python
# First run
convert_dataset_from_zip(..., seed=42)

# Second run with same seed produces identical splits
convert_dataset_from_zip(..., seed=42)
```

## Notes

- Test set is reserved for final evaluation (threshold tuning, etc.)
- Don't use test set during training or validation
- Background class (`bg`) is automatically filtered out
- Supports both grayscale and color images
- Images must be in PNG format
- XML annotations must be in PASCAL VOC format

## Additional Examples

### Dataset Statistics

```python
from training_utils import print_dataset_statistics, analyze_bbox_distributions
from pathlib import Path

# Print comprehensive dataset statistics
print_dataset_statistics(Path('yolo_dataset'))

# Analyze bbox distributions for train set
bbox_stats = analyze_bbox_distributions(Path('yolo_dataset'), split='train')
print(f"Average bbox width: {bbox_stats['width']['mean']:.3f}")
print(f"Average aspect ratio: {bbox_stats['aspect_ratio']['mean']:.2f}")
```

### Training Metrics Analysis

```python
from training_utils import print_training_summary, detect_overfitting
from pathlib import Path

# Analyze training run
print_training_summary(Path('work/runs/detect/v5/results.csv'))

# Check for overfitting
results = parse_yolo_results_csv(Path('work/runs/detect/v5/results.csv'))
overfitting = detect_overfitting(results)
print(overfitting['recommendation'])
```

### Compare Training Runs

```python
from training_utils import print_run_comparison
from pathlib import Path

runs = [
    ('v4', Path('work/runs/detect/v4/results.csv')),
    ('v5', Path('work/runs/detect/v5/results.csv')),
    ('v5_balanced', Path('work/runs/detect/v5_balanced/results.csv'))
]

print_run_comparison(runs, metric='metrics/mAP50-95(B)')
```

### Checkpoint Management

```python
from training_utils import (
    print_checkpoint_summary,
    backup_checkpoint,
    cleanup_old_checkpoints
)
from pathlib import Path

# List all checkpoints
print_checkpoint_summary(Path('work/runs/detect/v5/weights'))

# Backup best checkpoint
backup_checkpoint(
    checkpoint_path=Path('work/runs/detect/v5/weights/best.pt'),
    backup_dir=Path('checkpoints/backups'),
    add_timestamp=True
)

# Cleanup old checkpoints (dry run first!)
cleanup_old_checkpoints(
    checkpoint_dir=Path('work/runs/detect/v5/weights'),
    keep_best=True,
    keep_last=True,
    keep_recent=3,
    dry_run=True  # Set to False to actually delete
)
```

### Augmentation Configuration

```python
from training_utils import (
    suggest_conservative_augmentation,
    validate_augmentation_config,
    print_augmentation_summary
)

# Get conservative augmentation preset
config = suggest_conservative_augmentation()

# Validate configuration
is_valid, warnings = validate_augmentation_config(config)
for warning in warnings:
    print(f"⚠️  {warning}")

# Print detailed summary
print_augmentation_summary(config, dataset_size=5000, epochs=100)
```

### Custom Augmentation for Diagrams

```python
from training_utils import (
    suggest_conservative_augmentation,
    compare_augmentation_configs
)

# Start with conservative preset
config = suggest_conservative_augmentation()

# Customize for diagrams (no flips that change semantic meaning)
config['fliplr'] = 0.0  # Diagrams have semantic orientation
config['flipud'] = 0.0  # No vertical flips
config['degrees'] = 0.0  # No rotation for diagrams

# Compare with standard config
standard = suggest_conservative_augmentation()
print(compare_augmentation_configs(standard, config, "Standard", "Diagram-specific"))
```

## See Also

- [YOLOv8 Documentation](https://docs.ultralytics.com/)
- [PASCAL VOC Format](http://host.robots.ox.ac.uk/pascal/VOC/)
