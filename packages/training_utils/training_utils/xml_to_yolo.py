"""
Convert PASCAL VOC XML annotations to YOLO format and split into train/val sets.

This module provides functions for converting PASCAL VOC format annotations to YOLO format.
Supports both directory-based and zip file-based inputs.

Key functions:
- parse_xml_annotation: Parse PASCAL VOC XML files
- convert_bbox_to_yolo: Convert bbox coordinates to YOLO format
- create_class_mapping: Build class-to-id mapping
- convert_dataset_from_dir: Convert dataset from directory
- convert_dataset_from_zip: Convert dataset from zip file

Example usage:
    from training_utils import convert_dataset_from_zip

    convert_dataset_from_zip(
        zip_path='dataset.zip',
        output_dir='yolo_dataset',
        val_split=0.15,
        test_split=0.15
    )
"""

import xml.etree.ElementTree as ET
from pathlib import Path
import shutil
import random
from typing import Dict, List, Tuple, Optional
import yaml
import zipfile
import io


def parse_xml_annotation(xml_source) -> Dict:
    """
    Parse PASCAL VOC XML annotation file.
    
    Args:
        xml_source: Either a Path object or bytes content from zip
    """
    if isinstance(xml_source, bytes):
        root = ET.fromstring(xml_source)
    else:
        tree = ET.parse(xml_source)
        root = tree.getroot()
    
    annotation = {
        'filename': root.find('filename').text if root.find('filename') is not None else None,
        'size': {},
        'objects': []
    }
    
    # Get image dimensions
    size_elem = root.find('size')
    if size_elem is not None:
        annotation['size'] = {
            'width': int(size_elem.find('width').text),
            'height': int(size_elem.find('height').text),
            'depth': int(size_elem.find('depth').text) if size_elem.find('depth') is not None else 3
        }
    
    # Get all objects
    for obj in root.findall('object'):
        name = obj.find('name').text.strip() if obj.find('name').text else ''
        bbox = obj.find('bndbox')
        
        annotation['objects'].append({
            'class': name,
            'bbox': {
                'xmin': int(float(bbox.find('xmin').text)),
                'ymin': int(float(bbox.find('ymin').text)),
                'xmax': int(float(bbox.find('xmax').text)),
                'ymax': int(float(bbox.find('ymax').text))
            }
        })
    
    return annotation


def convert_bbox_to_yolo(bbox: Dict, img_width: int, img_height: int) -> Tuple[float, float, float, float]:
    """
    Convert PASCAL VOC bbox to YOLO format.
    
    PASCAL VOC: [xmin, ymin, xmax, ymax] (absolute coordinates)
    YOLO: [x_center, y_center, width, height] (normalized 0-1)
    """
    xmin = bbox['xmin']
    ymin = bbox['ymin']
    xmax = bbox['xmax']
    ymax = bbox['ymax']
    
    # Calculate center coordinates and dimensions
    x_center = (xmin + xmax) / 2.0
    y_center = (ymin + ymax) / 2.0
    width = xmax - xmin
    height = ymax - ymin
    
    # Normalize by image dimensions
    x_center /= img_width
    y_center /= img_height
    width /= img_width
    height /= img_height
    
    # Clamp values to [0, 1] to handle any edge cases
    x_center = max(0.0, min(1.0, x_center))
    y_center = max(0.0, min(1.0, y_center))
    width = max(0.0, min(1.0, width))
    height = max(0.0, min(1.0, height))
    
    return x_center, y_center, width, height


def create_class_mapping(xml_dir: Path) -> Dict[str, int]:
    """
    Scan all XML files to find unique classes and create class-to-id mapping.
    Excludes 'bg' (background) class.
    """
    classes = set()
    
    for xml_file in xml_dir.glob('*.xml'):
        annotation = parse_xml_annotation(xml_file)
        for obj in annotation['objects']:
            class_name = obj['class']
            # Skip background class
            if class_name.lower() != 'bg':
                classes.add(class_name)
    
    # Sort classes for consistent ordering
    sorted_classes = sorted(classes)
    class_to_id = {cls_name: idx for idx, cls_name in enumerate(sorted_classes)}
    
    return class_to_id


def create_class_mapping_from_zip(zip_path: Path) -> Dict[str, int]:
    """
    Scan all XML files in zip to find unique classes and create class-to-id mapping.
    Excludes 'bg' (background) class.
    """
    classes = set()
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        xml_files = [f for f in zf.namelist() if f.endswith('.xml') and not f.startswith('__MACOSX')]
        
        for xml_file in xml_files:
            xml_content = zf.read(xml_file)
            annotation = parse_xml_annotation(xml_content)
            for obj in annotation['objects']:
                class_name = obj['class']
                # Skip background class
                if class_name.lower() != 'bg':
                    classes.add(class_name)
    
    # Sort classes for consistent ordering
    sorted_classes = sorted(classes)
    class_to_id = {cls_name: idx for idx, cls_name in enumerate(sorted_classes)}
    
    return class_to_id


def convert_dataset_from_dir(
    input_dir: Path,
    output_dir: Path,
    val_split: float = 0.15,
    test_split: float = 0.15,
    seed: int = 42
) -> None:
    """
    Convert entire dataset from PASCAL VOC XML to YOLO format (from directory).
    Creates train/val/test splits for proper model evaluation.
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    
    images_dir = input_dir / 'images'
    annotations_dir = input_dir / 'annotations'
    
    if not images_dir.exists() or not annotations_dir.exists():
        raise ValueError(f"Expected {input_dir}/images and {input_dir}/annotations directories")
    
    # Create output directory structure
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'images' / 'train').mkdir(parents=True, exist_ok=True)
    (output_dir / 'images' / 'val').mkdir(parents=True, exist_ok=True)
    (output_dir / 'images' / 'test').mkdir(parents=True, exist_ok=True)
    (output_dir / 'labels' / 'train').mkdir(parents=True, exist_ok=True)
    (output_dir / 'labels' / 'val').mkdir(parents=True, exist_ok=True)
    (output_dir / 'labels' / 'test').mkdir(parents=True, exist_ok=True)
    
    # Create class mapping
    print("Creating class mapping...")
    class_to_id = create_class_mapping(annotations_dir)
    print(f"Found {len(class_to_id)} classes: {list(class_to_id.keys())}")
    
    # Save class names
    with open(output_dir / 'classes.txt', 'w') as f:
        for cls_name in sorted(class_to_id.keys(), key=lambda x: class_to_id[x]):
            f.write(f"{cls_name}\n")
    
    # Get all XML files
    xml_files = list(annotations_dir.glob('*.xml'))
    print(f"Found {len(xml_files)} annotation files")
    
    # Filter backgrounds (images without diagrams) BEFORE splitting
    # Save these for test negatives
    background_files = []
    filtered_xml_files = []
    
    print("Filtering backgrounds...")
    for xml_file in xml_files:
        try:
            annotation = parse_xml_annotation(xml_file)
            # Check if has any non-background objects
            has_objects = any(obj['class'].lower() != 'bg' for obj in annotation['objects'])
            
            if has_objects:
                filtered_xml_files.append(xml_file)
            else:
                # Find corresponding image
                img_name = annotation['filename'] or f"{xml_file.stem}.png"
                img_path = images_dir / img_name
                if not img_path.exists():
                    img_path = images_dir / f"{xml_file.stem}.png"
                
                if img_path.exists():
                    background_files.append(img_path)
        except Exception as e:
            print(f"Warning: Error checking {xml_file.name}: {e}")
            filtered_xml_files.append(xml_file)  # Keep it if we can't check
    
    print(f"After filtering: {len(filtered_xml_files)} files with diagrams")
    print(f"Backgrounds (no diagrams): {len(background_files)} files")
    
    # Use filtered files for splitting
    xml_files = filtered_xml_files
    
    # Split into train/val/test
    random.seed(seed)
    random.shuffle(xml_files)
    
    # Calculate split sizes
    test_size = int(len(xml_files) * test_split)
    val_size = int(len(xml_files) * val_split)
    
    # Create splits
    test_files = xml_files[:test_size]
    val_files = xml_files[test_size:test_size + val_size]
    train_files = xml_files[test_size + val_size:]
    
    print(f"Split: {len(train_files)} train, {len(val_files)} val, {len(test_files)} test")
    
    # Convert each split
    for split_name, xml_file_list in [('train', train_files), ('val', val_files), ('test', test_files)]:
        print(f"\nProcessing {split_name} split...")
        
        converted = 0
        skipped = 0
        
        for xml_file in xml_file_list:
            try:
                annotation = parse_xml_annotation(xml_file)
                
                # Skip if no objects (shouldn't happen if we filtered backgrounds)
                if len(annotation['objects']) == 0:
                    skipped += 1
                    continue
                
                # Find corresponding image
                img_name = annotation['filename'] or f"{xml_file.stem}.png"
                img_path = images_dir / img_name
                
                if not img_path.exists():
                    # Try with just the stem
                    img_path = images_dir / f"{xml_file.stem}.png"
                    if not img_path.exists():
                        print(f"Warning: Image not found for {xml_file.name}")
                        skipped += 1
                        continue
                
                # Get image dimensions
                img_width = annotation['size']['width']
                img_height = annotation['size']['height']
                
                # Convert bounding boxes to YOLO format
                yolo_lines = []
                for obj in annotation['objects']:
                    # Skip background class
                    if obj['class'].lower() == 'bg':
                        continue
                    
                    class_id = class_to_id[obj['class']]
                    x_center, y_center, width, height = convert_bbox_to_yolo(
                        obj['bbox'], img_width, img_height
                    )
                    yolo_lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")
                
                # Skip if no valid objects after filtering backgrounds
                if len(yolo_lines) == 0:
                    skipped += 1
                    continue
                
                # Write YOLO label file
                label_path = output_dir / 'labels' / split_name / f"{xml_file.stem}.txt"
                with open(label_path, 'w') as f:
                    f.write('\n'.join(yolo_lines))
                
                # Copy image to output directory
                dest_img_path = output_dir / 'images' / split_name / img_path.name
                shutil.copy2(img_path, dest_img_path)
                
                converted += 1
                
            except Exception as e:
                print(f"Error processing {xml_file.name}: {e}")
                skipped += 1
        
        print(f"  Converted: {converted}, Skipped: {skipped}")
    
    # Create YOLO dataset config file
    # YOLO expects names as {0: 'class1', 1: 'class2', ...}
    # Convert from class_to_id {'class1': 0, 'class2': 1} to id_to_class {0: 'class1', 1: 'class2'}
    id_to_class = {v: k for k, v in class_to_id.items()}
    
    # Use relative path (.) instead of absolute path for portability
    # This allows the dataset to work when uploaded to remote servers
    config = {
        'path': '.',  # Current directory (relative path)
        'train': 'images/train',
        'val': 'images/val',
        'names': id_to_class
    }
    
    with open(output_dir / 'dataset.yaml', 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    print(f"\nDataset conversion complete!")
    print(f"Output directory: {output_dir}")
    print(f"Config file: {output_dir / 'dataset.yaml'}")


def convert_dataset_from_zip(
    zip_path: Path,
    output_dir: Path,
    val_split: float = 0.15,
    test_split: float = 0.15,
    seed: int = 42,
    filter_backgrounds: bool = True
) -> None:
    """
    Convert entire dataset from PASCAL VOC XML to YOLO format (from zip file).
    Creates train/val/test splits for proper model evaluation.
    
    Args:
        zip_path: Path to zip file containing images and annotations
        output_dir: Output directory for YOLO dataset
        val_split: Fraction for validation (default: 0.15)
        test_split: Fraction for test set (default: 0.15)
        seed: Random seed for reproducibility
        filter_backgrounds: Exclude images without objects
    
    Note:
        Test set is reserved for final evaluation (threshold tuning, etc.)
        and should NOT be used during training.
    """
    zip_path = Path(zip_path)
    output_dir = Path(output_dir)
    
    if not zip_path.exists():
        raise ValueError(f"Zip file not found: {zip_path}")
    
    # Create output directory structure
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'images' / 'train').mkdir(parents=True, exist_ok=True)
    (output_dir / 'images' / 'val').mkdir(parents=True, exist_ok=True)
    (output_dir / 'images' / 'test').mkdir(parents=True, exist_ok=True)
    (output_dir / 'labels' / 'train').mkdir(parents=True, exist_ok=True)
    (output_dir / 'labels' / 'val').mkdir(parents=True, exist_ok=True)
    (output_dir / 'labels' / 'test').mkdir(parents=True, exist_ok=True)
    
    # Create class mapping
    print("Creating class mapping from zip...")
    class_to_id = create_class_mapping_from_zip(zip_path)
    print(f"Found {len(class_to_id)} classes: {list(class_to_id.keys())}")
    
    # Save class names
    with open(output_dir / 'classes.txt', 'w') as f:
        for cls_name in sorted(class_to_id.keys(), key=lambda x: class_to_id[x]):
            f.write(f"{cls_name}\n")
    
    # Build list of image-annotation pairs
    print("Scanning zip file for image-annotation pairs...")
    pairs = []
    background_pairs = []  # Collect backgrounds separately
    unmatched_pngs = []  # PNGs without XML = unannotated (NOT backgrounds!)
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        # Get all files
        all_files = [f for f in zf.namelist() if not f.startswith('__MACOSX') and not f.endswith('/')]
        png_files = {Path(f).stem: f for f in all_files if f.endswith('.png')}
        png_files_used = set()  # Track which PNGs we matched
        xml_files = [f for f in all_files if f.endswith('.xml')]
        
        print(f"Found {len(png_files)} PNG files and {len(xml_files)} XML files")
        
        for xml_file in xml_files:
            xml_content = zf.read(xml_file)
            annotation = parse_xml_annotation(xml_content)
            
            # Check if has any non-background objects
            has_objects = any(obj['class'].lower() != 'bg' for obj in annotation['objects'])
            
            # Find matching PNG
            xml_stem = Path(xml_file).stem
            
            # Try exact stem match first
            png_file = png_files.get(xml_stem)
            
            # If not found and annotation has filename, try that
            if png_file is None and annotation['filename']:
                filename_stem = Path(annotation['filename']).stem
                png_file = png_files.get(filename_stem)
            
            if png_file:
                if has_objects:
                    # Has diagrams - add to main pairs
                    pairs.append((png_file, xml_file))
                else:
                    # Has only class='bg' - this is a verified background
                    background_pairs.append((png_file, xml_file))
                png_files_used.add(png_file)
            else:
                print(f"Warning: No matching PNG for {xml_file}")
        
        # Find PNGs without XMLs - DO NOT use as backgrounds!
        # (These are unannotated, not verified as backgrounds)
        for png_stem, png_path in png_files.items():
            if png_path not in png_files_used:
                unmatched_pngs.append(png_path)
    
    print(f"Found {len(pairs)} image-annotation pairs (with diagrams)")
    print(f"Found {len(background_pairs)} verified backgrounds (XMLs with only class='bg')")
    print(f"Found {len(unmatched_pngs)} PNG files without XML (unannotated - IGNORED)")

    # Include or exclude backgrounds based on filter_backgrounds parameter
    if filter_backgrounds:
        print(f"After filtering: {len(pairs)} pairs with diagrams")
        print(f"Verified backgrounds (XMLs with only class='bg'): {len(background_pairs)} - EXCLUDED from training")
        print(f"Unannotated PNGs (ignored): {len(unmatched_pngs)}")
    else:
        # Include backgrounds in training splits
        print(f"Including backgrounds in training:")
        print(f"  Positives (with diagrams): {len(pairs)}")
        print(f"  Negatives (only class='bg'): {len(background_pairs)}")
        pairs.extend(background_pairs)
        print(f"  Total for training: {len(pairs)}")

    print(f"Using {len(pairs)} valid pairs for train/val/test split")
    
    # Split into train/val/test
    random.seed(seed)
    random.shuffle(pairs)
    
    # Calculate split sizes
    test_size = int(len(pairs) * test_split)
    val_size = int(len(pairs) * val_split)
    train_size = len(pairs) - test_size - val_size
    
    # Create splits
    test_pairs = pairs[:test_size]
    val_pairs = pairs[test_size:test_size + val_size]
    train_pairs = pairs[test_size + val_size:]
    
    print(f"Split: {len(train_pairs)} train, {len(val_pairs)} val, {len(test_pairs)} test")
    print(f"Split ratios: {len(train_pairs)/len(pairs):.1%} train, {len(val_pairs)/len(pairs):.1%} val, {len(test_pairs)/len(pairs):.1%} test")
    
    # Convert each split
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for split_name, pair_list in [('train', train_pairs), ('val', val_pairs), ('test', test_pairs)]:
            print(f"\nProcessing {split_name} split...")
            
            converted = 0
            skipped = 0
            
            for png_file, xml_file in pair_list:
                try:
                    # Read annotation
                    xml_content = zf.read(xml_file)
                    annotation = parse_xml_annotation(xml_content)
                    
                    # At this point, all pairs should have objects (filtered earlier)
                    if len(annotation['objects']) == 0:
                        # This shouldn't happen if filtering worked correctly
                        print(f"Warning: Empty annotation {xml_file} - skipping")
                        skipped += 1
                        continue
                    
                    # Get image dimensions
                    img_width = annotation['size']['width']
                    img_height = annotation['size']['height']
                    
                    # Convert bounding boxes to YOLO format
                    yolo_lines = []
                    for obj in annotation['objects']:
                        # Skip background class (bg objects indicate negative examples)
                        if obj['class'].lower() == 'bg':
                            continue

                        class_id = class_to_id[obj['class']]
                        x_center, y_center, width, height = convert_bbox_to_yolo(
                            obj['bbox'], img_width, img_height
                        )
                        yolo_lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")

                    # Allow empty label files for negative examples (images with only 'bg' class)
                    # YOLO uses empty labels to train on "no detections"
                    # if len(yolo_lines) == 0:
                    #     skipped += 1
                    #     continue

                    # Write YOLO label file (empty for negatives, with boxes for positives)
                    base_name = Path(png_file).stem
                    label_path = output_dir / 'labels' / split_name / f"{base_name}.txt"
                    with open(label_path, 'w') as f:
                        f.write('\n'.join(yolo_lines))
                    
                    # Extract and save image
                    try:
                        img_data = zf.read(png_file)
                    except KeyError:
                        print(f"Error: PNG file not found in zip: {png_file}")
                        skipped += 1
                        continue
                    
                    dest_img_path = output_dir / 'images' / split_name / Path(png_file).name
                    with open(dest_img_path, 'wb') as f:
                        f.write(img_data)
                    
                    converted += 1
                    
                except Exception as e:
                    print(f"Error processing {xml_file}: {e}")
                    skipped += 1
            
            print(f"  Converted: {converted}, Skipped: {skipped}")
    
    # Create YOLO dataset config file
    # YOLO expects names as {0: 'class1', 1: 'class2', ...}
    # Convert from class_to_id {'class1': 0, 'class2': 1} to id_to_class {0: 'class1', 1: 'class2'}
    id_to_class = {v: k for k, v in class_to_id.items()}
    
    # Use relative path (.) instead of absolute path for portability
    # This allows the dataset to work when uploaded to remote servers
    config = {
        'path': '.',  # Current directory (relative path)
        'train': 'images/train',
        'val': 'images/val',
        'test': 'images/test',  # Reserved for final evaluation
        'names': id_to_class
    }
    
    with open(output_dir / 'dataset.yaml', 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    print(f"\nDataset conversion complete!")
    print(f"Output directory: {output_dir}")
    print(f"Config file: {output_dir / 'dataset.yaml'}")
    print(f"\n⚠️  IMPORTANT: Test set ({len(test_pairs)} images) is reserved for final evaluation.")
    print(f"   Do NOT use for training or validation - only for threshold tuning and final metrics.")
    
    # Save background images for test negatives (F1 evaluation)
    if background_pairs:
        print(f"\nSaving {len(background_pairs)} background images for test negatives...")
        backgrounds_dir = output_dir / 'backgrounds'
        backgrounds_dir.mkdir(parents=True, exist_ok=True)
        
        saved_backgrounds = 0
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for png_file, xml_file in background_pairs:
                try:
                    img_data = zf.read(png_file)
                    dest_path = backgrounds_dir / Path(png_file).name
                    with open(dest_path, 'wb') as f:
                        f.write(img_data)
                    saved_backgrounds += 1
                except Exception as e:
                    print(f"Error saving background {png_file}: {e}")
        
        print(f"✓ Saved {saved_backgrounds} background images to {backgrounds_dir}")
        print(f"  These can be used as test negatives for F1 evaluation")
    
    # Verify conversion
    print(f"\nVerifying conversion...")
    issues_found = False
    
    for split_name in ['train', 'val', 'test']:
        images_dir = output_dir / 'images' / split_name
        labels_dir = output_dir / 'labels' / split_name
        
        image_files = set(f.stem for f in images_dir.glob('*.png'))
        label_files = set(f.stem for f in labels_dir.glob('*.txt'))
        
        # Check for mismatches
        missing_labels = image_files - label_files
        missing_images = label_files - image_files
        
        if missing_labels:
            print(f"  ⚠️  {split_name}: {len(missing_labels)} images without labels")
            issues_found = True
        
        if missing_images:
            print(f"  ⚠️  {split_name}: {len(missing_images)} labels without images")
            issues_found = True
            
        if not missing_labels and not missing_images:
            print(f"  ✓ {split_name}: {len(image_files)} pairs OK")
    
    if issues_found:
        print(f"\n⚠️  Some issues found - please review before training")
    else:
        print(f"\n✓ All splits verified successfully")

    print(f"Config file: {output_dir / 'dataset.yaml'}")
