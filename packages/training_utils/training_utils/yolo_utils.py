"""
YOLO dataset utilities for statistics, validation, and visualization.
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
from collections import defaultdict
import json


def convert_bbox_to_yolo(
    bbox: Tuple[float, float, float, float],
    image_width: int,
    image_height: int,
    class_id: int = 0
) -> Tuple[int, float, float, float, float]:
    """
    Convert bounding box from (x1, y1, x2, y2) to YOLO format.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2) in pixels
        image_width: Image width in pixels
        image_height: Image height in pixels
        class_id: Class ID (default: 0)

    Returns:
        Tuple of (class_id, x_center, y_center, width, height) normalized to [0, 1]

    Example:
        >>> bbox = (100, 50, 200, 150)  # x1, y1, x2, y2
        >>> convert_bbox_to_yolo(bbox, 800, 600, class_id=0)
        (0, 0.1875, 0.1667, 0.125, 0.1667)
    """
    x1, y1, x2, y2 = bbox

    # Calculate center and dimensions
    width = x2 - x1
    height = y2 - y1
    x_center = x1 + width / 2
    y_center = y1 + height / 2

    # Normalize to [0, 1]
    x_center_norm = x_center / image_width
    y_center_norm = y_center / image_height
    width_norm = width / image_width
    height_norm = height / image_height

    # Clamp to valid range [0, 1]
    x_center_norm = max(0.0, min(1.0, x_center_norm))
    y_center_norm = max(0.0, min(1.0, y_center_norm))
    width_norm = max(0.0, min(1.0, width_norm))
    height_norm = max(0.0, min(1.0, height_norm))

    return (class_id, x_center_norm, y_center_norm, width_norm, height_norm)


def convert_yolo_to_bbox(
    yolo: Tuple[int, float, float, float, float],
    image_width: int,
    image_height: int
) -> Tuple[int, float, float, float, float]:
    """
    Convert YOLO format to bounding box (x1, y1, x2, y2).

    Args:
        yolo: YOLO format (class_id, x_center, y_center, width, height) normalized
        image_width: Image width in pixels
        image_height: Image height in pixels

    Returns:
        Tuple of (class_id, x1, y1, x2, y2) in pixels

    Example:
        >>> yolo = (0, 0.5, 0.5, 0.2, 0.3)
        >>> convert_yolo_to_bbox(yolo, 800, 600)
        (0, 320.0, 225.0, 480.0, 375.0)
    """
    class_id, x_center_norm, y_center_norm, width_norm, height_norm = yolo

    # Convert to pixels
    x_center = x_center_norm * image_width
    y_center = y_center_norm * image_height
    width = width_norm * image_width
    height = height_norm * image_height

    # Calculate corners
    x1 = x_center - width / 2
    y1 = y_center - height / 2
    x2 = x_center + width / 2
    y2 = y_center + height / 2

    # Clamp to image bounds
    x1 = max(0.0, min(image_width, x1))
    y1 = max(0.0, min(image_height, y1))
    x2 = max(0.0, min(image_width, x2))
    y2 = max(0.0, min(image_height, y2))

    return (class_id, x1, y1, x2, y2)


def format_yolo_label(
    bbox: Tuple[float, float, float, float],
    image_width: int,
    image_height: int,
    class_id: int = 0
) -> str:
    """
    Convert bbox to YOLO label format string.

    Args:
        bbox: Bounding box as (x1, y1, x2, y2) in pixels
        image_width: Image width in pixels
        image_height: Image height in pixels
        class_id: Class ID (default: 0)

    Returns:
        YOLO format string: "class_id x_center y_center width height"

    Example:
        >>> bbox = (100, 50, 200, 150)
        >>> format_yolo_label(bbox, 800, 600, class_id=0)
        '0 0.1875 0.1667 0.125 0.1667'
    """
    class_id, x_center, y_center, width, height = convert_bbox_to_yolo(
        bbox, image_width, image_height, class_id
    )
    return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"


def get_dataset_statistics(dataset_path: Path, splits: List[str] = None) -> Dict:
    """
    Calculate statistics for YOLO dataset.

    Args:
        dataset_path: Path to YOLO dataset root
        splits: List of splits to analyze (default: ['train', 'val', 'test'])

    Returns:
        Dict with statistics for each split and overall
    """
    dataset_path = Path(dataset_path)

    if splits is None:
        splits = ['train', 'val', 'test']

    stats = {
        'splits': {},
        'overall': {
            'total_images': 0,
            'total_boxes': 0,
            'total_empty_labels': 0,
            'class_distribution': defaultdict(int)
        }
    }

    for split in splits:
        images_dir = dataset_path / 'images' / split
        labels_dir = dataset_path / 'labels' / split

        if not images_dir.exists() or not labels_dir.exists():
            continue

        split_stats = {
            'images': 0,
            'boxes': 0,
            'empty_labels': 0,
            'class_distribution': defaultdict(int),
            'boxes_per_image': []
        }

        # Count images
        image_files = list(images_dir.glob('*.png')) + list(images_dir.glob('*.jpg'))
        split_stats['images'] = len(image_files)

        # Analyze labels
        for label_file in labels_dir.glob('*.txt'):
            with open(label_file, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]

            if len(lines) == 0:
                split_stats['empty_labels'] += 1

            split_stats['boxes'] += len(lines)
            split_stats['boxes_per_image'].append(len(lines))

            # Count classes
            for line in lines:
                parts = line.split()
                if parts:
                    class_id = int(parts[0])
                    split_stats['class_distribution'][class_id] += 1

        # Calculate average boxes per image
        if split_stats['boxes_per_image']:
            split_stats['avg_boxes_per_image'] = sum(split_stats['boxes_per_image']) / len(split_stats['boxes_per_image'])
            split_stats['max_boxes_per_image'] = max(split_stats['boxes_per_image'])
        else:
            split_stats['avg_boxes_per_image'] = 0
            split_stats['max_boxes_per_image'] = 0

        # Remove boxes_per_image list from output (too large)
        del split_stats['boxes_per_image']

        # Convert defaultdict to regular dict for JSON serialization
        split_stats['class_distribution'] = dict(split_stats['class_distribution'])

        stats['splits'][split] = split_stats

        # Update overall stats
        stats['overall']['total_images'] += split_stats['images']
        stats['overall']['total_boxes'] += split_stats['boxes']
        stats['overall']['total_empty_labels'] += split_stats['empty_labels']

        for class_id, count in split_stats['class_distribution'].items():
            stats['overall']['class_distribution'][class_id] += count

    # Convert overall class_distribution to regular dict
    stats['overall']['class_distribution'] = dict(stats['overall']['class_distribution'])

    return stats


def print_dataset_statistics(dataset_path: Path, splits: List[str] = None):
    """
    Print formatted dataset statistics.

    Args:
        dataset_path: Path to YOLO dataset root
        splits: List of splits to analyze
    """
    stats = get_dataset_statistics(dataset_path, splits)

    print("=" * 80)
    print("YOLO DATASET STATISTICS")
    print("=" * 80)

    for split, split_stats in stats['splits'].items():
        print(f"\n{split.upper()} Split:")
        print(f"  Images: {split_stats['images']}")
        print(f"  Boxes:  {split_stats['boxes']}")
        print(f"  Empty labels: {split_stats['empty_labels']} ({split_stats['empty_labels']/max(1, split_stats['images'])*100:.1f}%)")
        print(f"  Avg boxes/image: {split_stats['avg_boxes_per_image']:.2f}")
        print(f"  Max boxes/image: {split_stats['max_boxes_per_image']}")

        if split_stats['class_distribution']:
            print(f"  Class distribution:")
            for class_id in sorted(split_stats['class_distribution'].keys()):
                count = split_stats['class_distribution'][class_id]
                print(f"    Class {class_id}: {count} boxes")

    print(f"\nOVERALL:")
    print(f"  Total images: {stats['overall']['total_images']}")
    print(f"  Total boxes:  {stats['overall']['total_boxes']}")
    print(f"  Empty labels: {stats['overall']['total_empty_labels']}")

    if stats['overall']['class_distribution']:
        print(f"  Class distribution:")
        for class_id in sorted(stats['overall']['class_distribution'].keys()):
            count = stats['overall']['class_distribution'][class_id]
            pct = count / max(1, stats['overall']['total_boxes']) * 100
            print(f"    Class {class_id}: {count} boxes ({pct:.1f}%)")


def find_duplicate_images(dataset_path: Path, splits: List[str] = None) -> Dict[str, List[Tuple[str, str]]]:
    """
    Find duplicate image filenames across splits.

    Args:
        dataset_path: Path to YOLO dataset root
        splits: List of splits to check

    Returns:
        Dict mapping filename to list of (split, path) tuples
    """
    dataset_path = Path(dataset_path)

    if splits is None:
        splits = ['train', 'val', 'test']

    file_locations = defaultdict(list)

    for split in splits:
        images_dir = dataset_path / 'images' / split

        if not images_dir.exists():
            continue

        for img_file in images_dir.glob('*'):
            if img_file.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                file_locations[img_file.name].append((split, str(img_file)))

    # Find duplicates (files appearing in multiple splits)
    duplicates = {
        name: locations
        for name, locations in file_locations.items()
        if len(locations) > 1
    }

    return duplicates


def check_image_label_pairing(dataset_path: Path, splits: List[str] = None) -> Dict:
    """
    Check for missing images or labels.

    Args:
        dataset_path: Path to YOLO dataset root
        splits: List of splits to check

    Returns:
        Dict with orphaned images and labels for each split
    """
    dataset_path = Path(dataset_path)

    if splits is None:
        splits = ['train', 'val', 'test']

    results = {}

    for split in splits:
        images_dir = dataset_path / 'images' / split
        labels_dir = dataset_path / 'labels' / split

        if not images_dir.exists() or not labels_dir.exists():
            continue

        # Get all image and label stems
        image_exts = ['.png', '.jpg', '.jpeg']
        images = {f.stem for ext in image_exts for f in images_dir.glob(f'*{ext}')}
        labels = {f.stem for f in labels_dir.glob('*.txt')}

        # Find orphans
        orphaned_images = images - labels
        orphaned_labels = labels - images

        results[split] = {
            'orphaned_images': list(orphaned_images),
            'orphaned_labels': list(orphaned_labels),
            'total_images': len(images),
            'total_labels': len(labels)
        }

    return results


def analyze_bbox_distributions(dataset_path: Path, split: str = 'train') -> Dict:
    """
    Analyze bounding box size distributions.

    Args:
        dataset_path: Path to YOLO dataset root
        split: Split to analyze

    Returns:
        Dict with bbox statistics
    """
    dataset_path = Path(dataset_path)
    labels_dir = dataset_path / 'labels' / split

    if not labels_dir.exists():
        raise ValueError(f"Labels directory not found: {labels_dir}")

    widths = []
    heights = []
    areas = []
    aspect_ratios = []

    for label_file in labels_dir.glob('*.txt'):
        with open(label_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    # YOLO format: class x_center y_center width height
                    width = float(parts[3])
                    height = float(parts[4])

                    widths.append(width)
                    heights.append(height)
                    areas.append(width * height)

                    if height > 0:
                        aspect_ratios.append(width / height)

    if not widths:
        return {
            'count': 0,
            'width': {},
            'height': {},
            'area': {},
            'aspect_ratio': {}
        }

    def get_stats(values):
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            'min': min(values),
            'max': max(values),
            'mean': sum(values) / n,
            'median': sorted_vals[n // 2],
            'p25': sorted_vals[n // 4],
            'p75': sorted_vals[3 * n // 4]
        }

    return {
        'count': len(widths),
        'width': get_stats(widths),
        'height': get_stats(heights),
        'area': get_stats(areas),
        'aspect_ratio': get_stats(aspect_ratios) if aspect_ratios else {}
    }


def export_statistics(dataset_path: Path, output_file: Path, splits: List[str] = None):
    """
    Export dataset statistics to JSON file.

    Args:
        dataset_path: Path to YOLO dataset root
        output_file: Path to output JSON file
        splits: List of splits to analyze
    """
    stats = get_dataset_statistics(dataset_path, splits)

    output_file = Path(output_file)
    with open(output_file, 'w') as f:
        json.dump(stats, f, indent=2)

    print(f"Statistics exported to {output_file}")


def validate_label_format(label_file: Path) -> Tuple[bool, List[str]]:
    """
    Validate YOLO label file format.

    Args:
        label_file: Path to label file

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    try:
        with open(label_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                parts = line.split()

                # Check number of fields
                if len(parts) != 5:
                    errors.append(f"Line {line_num}: Expected 5 values, got {len(parts)}")
                    continue

                try:
                    # Parse values
                    class_id = int(parts[0])
                    x_center = float(parts[1])
                    y_center = float(parts[2])
                    width = float(parts[3])
                    height = float(parts[4])

                    # Check ranges
                    if not (0 <= x_center <= 1):
                        errors.append(f"Line {line_num}: x_center {x_center} not in [0, 1]")
                    if not (0 <= y_center <= 1):
                        errors.append(f"Line {line_num}: y_center {y_center} not in [0, 1]")
                    if not (0 < width <= 1):
                        errors.append(f"Line {line_num}: width {width} not in (0, 1]")
                    if not (0 < height <= 1):
                        errors.append(f"Line {line_num}: height {height} not in (0, 1]")
                    if class_id < 0:
                        errors.append(f"Line {line_num}: class_id {class_id} is negative")

                except ValueError as e:
                    errors.append(f"Line {line_num}: Cannot parse values: {e}")

    except Exception as e:
        errors.append(f"Error reading file: {e}")

    return (len(errors) == 0, errors)


def count_classes(dataset_path: Path, split: str) -> Dict[int, int]:
    """
    Count instances of each class in a split.

    Args:
        dataset_path: Path to YOLO dataset root
        split: Split to analyze

    Returns:
        Dict mapping class_id to count
    """
    dataset_path = Path(dataset_path)
    labels_dir = dataset_path / 'labels' / split

    class_counts = defaultdict(int)

    if labels_dir.exists():
        for label_file in labels_dir.glob('*.txt'):
            with open(label_file, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if parts:
                        class_id = int(parts[0])
                        class_counts[class_id] += 1

    return dict(class_counts)
