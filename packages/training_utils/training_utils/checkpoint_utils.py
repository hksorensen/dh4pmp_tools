"""
Model checkpoint management utilities.
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional
import shutil
import json
from datetime import datetime
import hashlib


def compute_file_checksum(file_path: Path) -> str:
    """
    Compute SHA256 checksum of a file.

    Args:
        file_path: Path to file

    Returns:
        Hex digest of SHA256 checksum
    """
    sha256 = hashlib.sha256()

    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)

    return sha256.hexdigest()


def list_checkpoints(checkpoint_dir: Path, pattern: str = '*.pt') -> List[Dict]:
    """
    List all checkpoints in directory with metadata.

    Args:
        checkpoint_dir: Directory containing checkpoints
        pattern: Glob pattern for checkpoint files

    Returns:
        List of dicts with checkpoint info
    """
    checkpoint_dir = Path(checkpoint_dir)

    if not checkpoint_dir.exists():
        return []

    checkpoints = []

    for ckpt_file in sorted(checkpoint_dir.glob(pattern)):
        stat = ckpt_file.stat()

        checkpoint_info = {
            'name': ckpt_file.name,
            'path': str(ckpt_file),
            'size_mb': stat.st_size / (1024 * 1024),
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'checksum': None  # Computed on demand
        }

        checkpoints.append(checkpoint_info)

    return checkpoints


def find_best_checkpoint(checkpoint_dir: Path, prefix: str = 'best') -> Optional[Path]:
    """
    Find the best checkpoint in directory.

    Args:
        checkpoint_dir: Directory containing checkpoints
        prefix: Prefix for best checkpoint (default: 'best')

    Returns:
        Path to best checkpoint or None if not found
    """
    checkpoint_dir = Path(checkpoint_dir)

    # Try common names
    candidates = [
        checkpoint_dir / f'{prefix}.pt',
        checkpoint_dir / 'weights' / f'{prefix}.pt',
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def find_last_checkpoint(checkpoint_dir: Path, prefix: str = 'last') -> Optional[Path]:
    """
    Find the last checkpoint in directory.

    Args:
        checkpoint_dir: Directory containing checkpoints
        prefix: Prefix for last checkpoint (default: 'last')

    Returns:
        Path to last checkpoint or None if not found
    """
    checkpoint_dir = Path(checkpoint_dir)

    # Try common names
    candidates = [
        checkpoint_dir / f'{prefix}.pt',
        checkpoint_dir / 'weights' / f'{prefix}.pt',
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def backup_checkpoint(
    checkpoint_path: Path,
    backup_dir: Path,
    add_timestamp: bool = True,
    compute_checksum: bool = True
) -> Path:
    """
    Create backup of checkpoint.

    Args:
        checkpoint_path: Path to checkpoint to backup
        backup_dir: Directory for backups
        add_timestamp: Add timestamp to backup filename
        compute_checksum: Compute and save checksum

    Returns:
        Path to backup file
    """
    checkpoint_path = Path(checkpoint_path)
    backup_dir = Path(backup_dir)

    backup_dir.mkdir(parents=True, exist_ok=True)

    # Generate backup filename
    if add_timestamp:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{checkpoint_path.stem}_{timestamp}{checkpoint_path.suffix}"
    else:
        backup_name = checkpoint_path.name

    backup_path = backup_dir / backup_name

    # Copy checkpoint
    shutil.copy2(checkpoint_path, backup_path)

    # Compute and save checksum
    if compute_checksum:
        checksum = compute_file_checksum(backup_path)
        checksum_file = backup_path.with_suffix('.sha256')

        with open(checksum_file, 'w') as f:
            f.write(f"{checksum}  {backup_path.name}\n")

    return backup_path


def verify_checkpoint(checkpoint_path: Path, checksum_file: Path = None) -> bool:
    """
    Verify checkpoint integrity using checksum.

    Args:
        checkpoint_path: Path to checkpoint
        checksum_file: Path to checksum file (default: checkpoint_path.with_suffix('.sha256'))

    Returns:
        True if checksum matches, False otherwise
    """
    checkpoint_path = Path(checkpoint_path)

    if checksum_file is None:
        checksum_file = checkpoint_path.with_suffix('.sha256')

    if not checksum_file.exists():
        print(f"No checksum file found: {checksum_file}")
        return False

    # Read expected checksum
    with open(checksum_file, 'r') as f:
        expected = f.read().strip().split()[0]

    # Compute actual checksum
    actual = compute_file_checksum(checkpoint_path)

    return actual == expected


def create_checkpoint_manifest(
    checkpoint_dir: Path,
    output_file: Path = None,
    include_checksums: bool = True
) -> Dict:
    """
    Create manifest of all checkpoints in directory.

    Args:
        checkpoint_dir: Directory containing checkpoints
        output_file: Optional path to save manifest JSON
        include_checksums: Compute checksums for each checkpoint

    Returns:
        Manifest dict
    """
    checkpoint_dir = Path(checkpoint_dir)

    manifest = {
        'created': datetime.now().isoformat(),
        'checkpoint_dir': str(checkpoint_dir),
        'checkpoints': []
    }

    checkpoints = list_checkpoints(checkpoint_dir)

    for ckpt in checkpoints:
        if include_checksums:
            ckpt['checksum'] = compute_file_checksum(Path(ckpt['path']))

        manifest['checkpoints'].append(ckpt)

    if output_file:
        output_file = Path(output_file)
        with open(output_file, 'w') as f:
            json.dump(manifest, f, indent=2)

    return manifest


def cleanup_old_checkpoints(
    checkpoint_dir: Path,
    keep_best: bool = True,
    keep_last: bool = True,
    keep_recent: int = 3,
    dry_run: bool = True
) -> List[Path]:
    """
    Clean up old checkpoints to save space.

    Args:
        checkpoint_dir: Directory containing checkpoints
        keep_best: Keep best.pt
        keep_last: Keep last.pt
        keep_recent: Number of recent epoch checkpoints to keep
        dry_run: If True, only report what would be deleted

    Returns:
        List of deleted (or would-be-deleted) checkpoint paths
    """
    checkpoint_dir = Path(checkpoint_dir)

    # Find checkpoints to keep
    keep_files = set()

    if keep_best:
        best_ckpt = find_best_checkpoint(checkpoint_dir)
        if best_ckpt:
            keep_files.add(best_ckpt)

    if keep_last:
        last_ckpt = find_last_checkpoint(checkpoint_dir)
        if last_ckpt:
            keep_files.add(last_ckpt)

    # Find epoch checkpoints and keep most recent
    epoch_checkpoints = []
    for ckpt_file in checkpoint_dir.glob('epoch*.pt'):
        epoch_checkpoints.append(ckpt_file)

    # Sort by modification time (most recent first)
    epoch_checkpoints.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    # Keep most recent epoch checkpoints
    for ckpt in epoch_checkpoints[:keep_recent]:
        keep_files.add(ckpt)

    # Find checkpoints to delete
    all_checkpoints = set(checkpoint_dir.glob('*.pt'))
    to_delete = all_checkpoints - keep_files

    if dry_run:
        print(f"DRY RUN - Would delete {len(to_delete)} checkpoints:")
        for ckpt in sorted(to_delete):
            size_mb = ckpt.stat().st_size / (1024 * 1024)
            print(f"  {ckpt.name} ({size_mb:.1f} MB)")

        total_size = sum(ckpt.stat().st_size for ckpt in to_delete) / (1024 * 1024)
        print(f"\nTotal space to free: {total_size:.1f} MB")
    else:
        for ckpt in to_delete:
            ckpt.unlink()

    return list(to_delete)


def compare_checkpoints(checkpoint_paths: List[Path]) -> Dict:
    """
    Compare multiple checkpoints.

    Args:
        checkpoint_paths: List of checkpoint paths to compare

    Returns:
        Dict with comparison data
    """
    comparison = {
        'checkpoints': [],
        'statistics': {}
    }

    sizes = []
    checksums = set()

    for ckpt_path in checkpoint_paths:
        ckpt_path = Path(ckpt_path)

        if not ckpt_path.exists():
            continue

        size = ckpt_path.stat().st_size
        checksum = compute_file_checksum(ckpt_path)

        comparison['checkpoints'].append({
            'name': ckpt_path.name,
            'path': str(ckpt_path),
            'size_mb': size / (1024 * 1024),
            'checksum': checksum
        })

        sizes.append(size)
        checksums.add(checksum)

    if sizes:
        comparison['statistics'] = {
            'count': len(sizes),
            'total_size_mb': sum(sizes) / (1024 * 1024),
            'avg_size_mb': sum(sizes) / len(sizes) / (1024 * 1024),
            'min_size_mb': min(sizes) / (1024 * 1024),
            'max_size_mb': max(sizes) / (1024 * 1024),
            'unique_checksums': len(checksums)
        }

    return comparison


def archive_checkpoint(
    checkpoint_path: Path,
    archive_dir: Path,
    metadata: Optional[Dict] = None
) -> Path:
    """
    Archive checkpoint with metadata.

    Args:
        checkpoint_path: Path to checkpoint
        archive_dir: Directory for archived checkpoints
        metadata: Optional metadata dict to save

    Returns:
        Path to archived checkpoint
    """
    checkpoint_path = Path(checkpoint_path)
    archive_dir = Path(archive_dir)

    archive_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamped subdirectory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    version_dir = archive_dir / timestamp
    version_dir.mkdir(exist_ok=True)

    # Copy checkpoint
    archived_ckpt = version_dir / checkpoint_path.name
    shutil.copy2(checkpoint_path, archived_ckpt)

    # Compute checksum
    checksum = compute_file_checksum(archived_ckpt)

    # Save metadata
    metadata_dict = {
        'original_path': str(checkpoint_path),
        'archived_at': timestamp,
        'checksum': checksum,
        'size_mb': checkpoint_path.stat().st_size / (1024 * 1024)
    }

    if metadata:
        metadata_dict.update(metadata)

    metadata_file = version_dir / 'metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump(metadata_dict, f, indent=2)

    # Save checksum file
    checksum_file = version_dir / f'{checkpoint_path.stem}.sha256'
    with open(checksum_file, 'w') as f:
        f.write(f"{checksum}  {checkpoint_path.name}\n")

    return archived_ckpt


def print_checkpoint_summary(checkpoint_dir: Path):
    """
    Print formatted summary of checkpoints in directory.

    Args:
        checkpoint_dir: Directory containing checkpoints
    """
    checkpoints = list_checkpoints(checkpoint_dir)

    print("=" * 80)
    print("CHECKPOINT SUMMARY")
    print("=" * 80)
    print(f"\nDirectory: {checkpoint_dir}")
    print(f"Total checkpoints: {len(checkpoints)}")

    if not checkpoints:
        print("No checkpoints found")
        return

    total_size = sum(ckpt['size_mb'] for ckpt in checkpoints)
    print(f"Total size: {total_size:.1f} MB")

    print(f"\n{'Checkpoint':<30} {'Size (MB)':<15} {'Modified':<25}")
    print("-" * 80)

    for ckpt in checkpoints:
        print(f"{ckpt['name']:<30} {ckpt['size_mb']:<15.1f} {ckpt['modified']:<25}")

    # Highlight special checkpoints
    best_ckpt = find_best_checkpoint(checkpoint_dir)
    last_ckpt = find_last_checkpoint(checkpoint_dir)

    print("\nSpecial checkpoints:")
    if best_ckpt:
        print(f"  Best: {best_ckpt.name}")
    if last_ckpt:
        print(f"  Last: {last_ckpt.name}")
