"""
Training Utilities for Diagram Detection

Provides utilities for:
- Converting PASCAL VOC XML to YOLO format
- Dataset validation and statistics
- Training metrics analysis
- Checkpoint management
- Generic augmentation helpers

Version: 0.1.0

Modules:
- xml_to_yolo: PASCAL VOC to YOLO conversion
- yolo_utils: Dataset statistics and validation
- metric_utils: Training metrics analysis
- checkpoint_utils: Model checkpoint management
- augmentation_utils: Generic augmentation helpers
"""

# XML to YOLO conversion
from .xml_to_yolo import (
    parse_xml_annotation,
    convert_bbox_to_yolo,
    convert_dataset_from_zip,
    convert_dataset_from_dir,
    create_class_mapping,
    create_class_mapping_from_zip
)

# YOLO utilities
from .yolo_utils import (
    get_dataset_statistics,
    print_dataset_statistics,
    find_duplicate_images,
    check_image_label_pairing,
    analyze_bbox_distributions,
    export_statistics,
    validate_label_format,
    count_classes
)

# Metric utilities
from .metric_utils import (
    parse_yolo_results_csv,
    find_best_epoch,
    calculate_improvement,
    detect_overfitting,
    summarize_training_run,
    print_training_summary,
    compare_training_runs,
    print_run_comparison,
    export_metrics_json,
    calculate_convergence_epoch,
    estimate_training_efficiency
)

# Checkpoint utilities
from .checkpoint_utils import (
    compute_file_checksum,
    list_checkpoints,
    find_best_checkpoint,
    find_last_checkpoint,
    backup_checkpoint,
    verify_checkpoint,
    create_checkpoint_manifest,
    cleanup_old_checkpoints,
    compare_checkpoints,
    archive_checkpoint,
    print_checkpoint_summary
)

# Augmentation utilities
from .augmentation_utils import (
    validate_augmentation_config,
    compare_augmentation_configs,
    suggest_conservative_augmentation,
    suggest_aggressive_augmentation,
    disable_all_augmentation,
    calculate_effective_dataset_size,
    sample_augmentation_parameters,
    estimate_augmentation_strength,
    print_augmentation_summary
)

__version__ = "0.1.0"

__all__ = [
    # xml_to_yolo
    "parse_xml_annotation",
    "convert_bbox_to_yolo",
    "convert_dataset_from_zip",
    "convert_dataset_from_dir",
    "create_class_mapping",
    "create_class_mapping_from_zip",

    # yolo_utils
    "get_dataset_statistics",
    "print_dataset_statistics",
    "find_duplicate_images",
    "check_image_label_pairing",
    "analyze_bbox_distributions",
    "export_statistics",
    "validate_label_format",
    "count_classes",

    # metric_utils
    "parse_yolo_results_csv",
    "find_best_epoch",
    "calculate_improvement",
    "detect_overfitting",
    "summarize_training_run",
    "print_training_summary",
    "compare_training_runs",
    "print_run_comparison",
    "export_metrics_json",
    "calculate_convergence_epoch",
    "estimate_training_efficiency",

    # checkpoint_utils
    "compute_file_checksum",
    "list_checkpoints",
    "find_best_checkpoint",
    "find_last_checkpoint",
    "backup_checkpoint",
    "verify_checkpoint",
    "create_checkpoint_manifest",
    "cleanup_old_checkpoints",
    "compare_checkpoints",
    "archive_checkpoint",
    "print_checkpoint_summary",

    # augmentation_utils
    "validate_augmentation_config",
    "compare_augmentation_configs",
    "suggest_conservative_augmentation",
    "suggest_aggressive_augmentation",
    "disable_all_augmentation",
    "calculate_effective_dataset_size",
    "sample_augmentation_parameters",
    "estimate_augmentation_strength",
    "print_augmentation_summary",
]
