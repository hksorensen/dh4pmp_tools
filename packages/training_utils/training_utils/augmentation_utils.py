"""
Generic augmentation utilities.

Note: This module contains only generic augmentation helpers.
Diagram-specific augmentation logic should be configured in the training pipeline.
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional
import random


def validate_augmentation_config(config: Dict) -> Tuple[bool, List[str]]:
    """
    Validate augmentation configuration parameters.

    Args:
        config: Augmentation config dict with YOLO parameters

    Returns:
        Tuple of (is_valid, list_of_warnings)
    """
    warnings = []

    # Check for incompatible augmentations
    if config.get('mosaic', 1.0) > 0 and config.get('mixup', 0.0) > 0:
        warnings.append("Both mosaic and mixup enabled - these may interact unexpectedly")

    # Check value ranges
    range_checks = {
        'fliplr': (0.0, 1.0, 'horizontal flip probability'),
        'flipud': (0.0, 1.0, 'vertical flip probability'),
        'degrees': (0.0, 180.0, 'rotation degrees'),
        'translate': (0.0, 1.0, 'translation fraction'),
        'scale': (0.0, 2.0, 'scale factor'),
        'shear': (0.0, 45.0, 'shear degrees'),
        'perspective': (0.0, 0.001, 'perspective transform'),
        'hsv_h': (0.0, 1.0, 'hue augmentation'),
        'hsv_s': (0.0, 1.0, 'saturation augmentation'),
        'hsv_v': (0.0, 1.0, 'value augmentation'),
        'mosaic': (0.0, 1.0, 'mosaic probability'),
        'mixup': (0.0, 1.0, 'mixup probability'),
    }

    for param, (min_val, max_val, description) in range_checks.items():
        if param in config:
            value = config[param]
            if not (min_val <= value <= max_val):
                warnings.append(
                    f"{param} ({description}): {value} outside recommended range [{min_val}, {max_val}]"
                )

    # Check for potentially extreme values
    if config.get('scale', 0.5) > 1.5:
        warnings.append(f"scale={config['scale']} is very aggressive - may distort objects significantly")

    if config.get('translate', 0.1) > 0.5:
        warnings.append(f"translate={config['translate']} is very aggressive - objects may move out of frame")

    if config.get('degrees', 0.0) > 45:
        warnings.append(f"degrees={config['degrees']} is very aggressive for most object types")

    return (len(warnings) == 0, warnings)


def compare_augmentation_configs(config1: Dict, config2: Dict, name1: str = "Config 1", name2: str = "Config 2") -> str:
    """
    Compare two augmentation configurations and return formatted diff.

    Args:
        config1: First config dict
        config2: Second config dict
        name1: Label for first config
        name2: Label for second config

    Returns:
        Formatted comparison string
    """
    all_keys = sorted(set(config1.keys()) | set(config2.keys()))

    lines = []
    lines.append(f"\nAugmentation Config Comparison:")
    lines.append(f"{'Parameter':<20} {name1:<15} {name2:<15} {'Difference':<20}")
    lines.append("-" * 70)

    for key in all_keys:
        val1 = config1.get(key, 'N/A')
        val2 = config2.get(key, 'N/A')

        if val1 == val2:
            diff = "✓ Same"
        elif val1 == 'N/A':
            diff = f"Added in {name2}"
        elif val2 == 'N/A':
            diff = f"Removed from {name1}"
        else:
            try:
                numeric_diff = float(val2) - float(val1)
                diff = f"{numeric_diff:+.3f}"
            except (ValueError, TypeError):
                diff = "Changed"

        lines.append(f"{key:<20} {str(val1):<15} {str(val2):<15} {diff:<20}")

    return "\n".join(lines)


def suggest_conservative_augmentation() -> Dict:
    """
    Return conservative augmentation settings suitable for most datasets.

    Returns:
        Dict with recommended conservative augmentation parameters
    """
    return {
        'augment': True,
        'fliplr': 0.5,       # 50% horizontal flip
        'flipud': 0.0,       # No vertical flip
        'degrees': 0.0,      # No rotation
        'translate': 0.1,    # 10% translation
        'scale': 0.5,        # 50% scale variation
        'shear': 0.0,        # No shear
        'perspective': 0.0,  # No perspective
        'hsv_h': 0.015,      # Slight hue variation
        'hsv_s': 0.7,        # Moderate saturation
        'hsv_v': 0.4,        # Moderate value
        'mosaic': 1.0,       # Use mosaic
        'mixup': 0.0,        # No mixup
    }


def suggest_aggressive_augmentation() -> Dict:
    """
    Return aggressive augmentation settings for data-hungry models.

    Returns:
        Dict with aggressive augmentation parameters
    """
    return {
        'augment': True,
        'fliplr': 0.5,
        'flipud': 0.5,
        'degrees': 15.0,
        'translate': 0.2,
        'scale': 0.9,
        'shear': 5.0,
        'perspective': 0.0005,
        'hsv_h': 0.015,
        'hsv_s': 0.7,
        'hsv_v': 0.4,
        'mosaic': 1.0,
        'mixup': 0.15,
    }


def disable_all_augmentation() -> Dict:
    """
    Return config with all augmentation disabled.

    Returns:
        Dict with augmentation disabled
    """
    return {
        'augment': False,
        'fliplr': 0.0,
        'flipud': 0.0,
        'degrees': 0.0,
        'translate': 0.0,
        'scale': 0.0,
        'shear': 0.0,
        'perspective': 0.0,
        'hsv_h': 0.0,
        'hsv_s': 0.0,
        'hsv_v': 0.0,
        'mosaic': 0.0,
        'mixup': 0.0,
    }


def calculate_effective_dataset_size(
    base_size: int,
    epochs: int,
    augmentation_config: Dict
) -> int:
    """
    Estimate effective dataset size with augmentation.

    Args:
        base_size: Number of base images
        epochs: Number of training epochs
        augmentation_config: Augmentation config

    Returns:
        Estimated number of unique augmented examples seen during training
    """
    # Count enabled augmentations
    enabled_augs = 0

    flip_enabled = (augmentation_config.get('fliplr', 0.0) > 0 or
                   augmentation_config.get('flipud', 0.0) > 0)
    if flip_enabled:
        enabled_augs += 1

    if augmentation_config.get('degrees', 0.0) > 0:
        enabled_augs += 1

    if augmentation_config.get('translate', 0.0) > 0:
        enabled_augs += 1

    if augmentation_config.get('scale', 0.0) > 0:
        enabled_augs += 1

    color_enabled = (augmentation_config.get('hsv_h', 0.0) > 0 or
                    augmentation_config.get('hsv_s', 0.0) > 0 or
                    augmentation_config.get('hsv_v', 0.0) > 0)
    if color_enabled:
        enabled_augs += 1

    if augmentation_config.get('mosaic', 0.0) > 0:
        enabled_augs += 2  # Mosaic has high variability

    if augmentation_config.get('mixup', 0.0) > 0:
        enabled_augs += 2  # Mixup has high variability

    # Rough estimate: each augmentation type roughly doubles variety
    variety_multiplier = 2 ** enabled_augs

    # Effective size is bounded by total iterations
    max_effective = base_size * epochs
    estimated_effective = min(base_size * variety_multiplier, max_effective)

    return int(estimated_effective)


def sample_augmentation_parameters(config: Dict, seed: Optional[int] = None) -> Dict:
    """
    Sample specific augmentation parameters from configuration ranges.

    Useful for visualizing what augmentations will look like.

    Args:
        config: Augmentation config with max values
        seed: Random seed for reproducibility

    Returns:
        Dict with sampled parameter values
    """
    if seed is not None:
        random.seed(seed)

    sampled = {}

    # Binary augmentations (apply or not)
    if random.random() < config.get('fliplr', 0.0):
        sampled['fliplr'] = True

    if random.random() < config.get('flipud', 0.0):
        sampled['flipud'] = True

    # Continuous augmentations (sample from range)
    if config.get('degrees', 0.0) > 0:
        max_deg = config['degrees']
        sampled['degrees'] = random.uniform(-max_deg, max_deg)

    if config.get('translate', 0.0) > 0:
        max_trans = config['translate']
        sampled['translate_x'] = random.uniform(-max_trans, max_trans)
        sampled['translate_y'] = random.uniform(-max_trans, max_trans)

    if config.get('scale', 0.0) > 0:
        scale_range = config['scale']
        sampled['scale'] = random.uniform(1.0 - scale_range, 1.0 + scale_range)

    if config.get('shear', 0.0) > 0:
        max_shear = config['shear']
        sampled['shear'] = random.uniform(-max_shear, max_shear)

    # Color augmentations
    for param in ['hsv_h', 'hsv_s', 'hsv_v']:
        if config.get(param, 0.0) > 0:
            max_val = config[param]
            sampled[param] = random.uniform(-max_val, max_val)

    return sampled


def estimate_augmentation_strength(config: Dict) -> str:
    """
    Estimate overall augmentation strength.

    Args:
        config: Augmentation configuration

    Returns:
        Strength level: "none", "light", "moderate", "aggressive", or "extreme"
    """
    # Calculate weighted score
    score = 0

    # Geometric augmentations (high impact)
    score += config.get('degrees', 0.0) / 45.0 * 2.0  # Max 2.0
    score += config.get('translate', 0.0) * 2.0       # Max 2.0
    score += config.get('scale', 0.0)                 # Max ~1.0
    score += config.get('shear', 0.0) / 45.0 * 1.5    # Max 1.5
    score += config.get('perspective', 0.0) * 1000    # Max ~1.0

    # Flip augmentations (moderate impact)
    score += config.get('fliplr', 0.0) * 0.5
    score += config.get('flipud', 0.0) * 0.5

    # Color augmentations (low-moderate impact)
    score += config.get('hsv_h', 0.0) * 10
    score += config.get('hsv_s', 0.0) * 0.5
    score += config.get('hsv_v', 0.0) * 0.5

    # Advanced augmentations (high impact)
    score += config.get('mosaic', 0.0) * 2.0
    score += config.get('mixup', 0.0) * 2.0

    # Classify strength
    if score == 0:
        return "none"
    elif score < 2.0:
        return "light"
    elif score < 5.0:
        return "moderate"
    elif score < 10.0:
        return "aggressive"
    else:
        return "extreme"


def print_augmentation_summary(config: Dict, dataset_size: int = None, epochs: int = None):
    """
    Print formatted summary of augmentation configuration.

    Args:
        config: Augmentation configuration
        dataset_size: Optional dataset size for effective size calculation
        epochs: Optional number of epochs
    """
    print("=" * 70)
    print("AUGMENTATION CONFIGURATION")
    print("=" * 70)

    strength = estimate_augmentation_strength(config)
    print(f"\nOverall strength: {strength.upper()}")

    print("\nGeometric Augmentations:")
    print(f"  Horizontal flip: {config.get('fliplr', 0.0):.2f}")
    print(f"  Vertical flip:   {config.get('flipud', 0.0):.2f}")
    print(f"  Rotation:        ±{config.get('degrees', 0.0):.1f}°")
    print(f"  Translation:     ±{config.get('translate', 0.0):.2f}")
    print(f"  Scale:           ±{config.get('scale', 0.0):.2f}")
    print(f"  Shear:           ±{config.get('shear', 0.0):.1f}°")
    print(f"  Perspective:     {config.get('perspective', 0.0):.4f}")

    print("\nColor Augmentations:")
    print(f"  Hue:        ±{config.get('hsv_h', 0.0):.3f}")
    print(f"  Saturation: ±{config.get('hsv_s', 0.0):.2f}")
    print(f"  Value:      ±{config.get('hsv_v', 0.0):.2f}")

    print("\nAdvanced Augmentations:")
    print(f"  Mosaic: {config.get('mosaic', 0.0):.2f}")
    print(f"  Mixup:  {config.get('mixup', 0.0):.2f}")

    # Validation
    is_valid, warnings = validate_augmentation_config(config)
    if warnings:
        print("\n⚠️  Warnings:")
        for warning in warnings:
            print(f"  - {warning}")

    # Effective dataset size
    if dataset_size and epochs:
        effective_size = calculate_effective_dataset_size(dataset_size, epochs, config)
        print(f"\nEffective Dataset Size:")
        print(f"  Base size:      {dataset_size:,}")
        print(f"  Epochs:         {epochs}")
        print(f"  Effective size: ~{effective_size:,} unique examples")
        print(f"  Multiplier:     ~{effective_size/dataset_size:.1f}x")
