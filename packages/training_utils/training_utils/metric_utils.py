"""
Training metrics calculation and reporting utilities.
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional
import csv
import json
from collections import defaultdict


def parse_yolo_results_csv(results_file: Path) -> List[Dict]:
    """
    Parse YOLO results.csv file from training.

    Args:
        results_file: Path to results.csv

    Returns:
        List of dicts, one per epoch
    """
    results = []

    with open(results_file, 'r') as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [name.strip() for name in reader.fieldnames]

        for row in reader:
            # Convert to proper types
            epoch_data = {}
            for key, value in row.items():
                try:
                    # Try int first, then float
                    if '.' in value:
                        epoch_data[key] = float(value)
                    else:
                        epoch_data[key] = int(value)
                except (ValueError, AttributeError):
                    epoch_data[key] = value

            results.append(epoch_data)

    return results


def find_best_epoch(results: List[Dict], metric: str = 'metrics/mAP50-95(B)') -> Tuple[int, Dict]:
    """
    Find epoch with best metric value.

    Args:
        results: List of epoch results from parse_yolo_results_csv
        metric: Metric to optimize (default: mAP50-95)

    Returns:
        Tuple of (best_epoch_number, best_epoch_data)
    """
    best_epoch = None
    best_value = -float('inf')

    for epoch_data in results:
        if metric in epoch_data:
            value = epoch_data[metric]
            if value > best_value:
                best_value = value
                best_epoch = epoch_data

    if best_epoch is None:
        raise ValueError(f"Metric '{metric}' not found in results")

    return best_epoch.get('epoch', 0), best_epoch


def calculate_improvement(results: List[Dict], metric: str) -> Dict:
    """
    Calculate improvement metrics over training.

    Args:
        results: List of epoch results
        metric: Metric to analyze

    Returns:
        Dict with improvement statistics
    """
    values = [r[metric] for r in results if metric in r]

    if not values:
        raise ValueError(f"Metric '{metric}' not found")

    initial = values[0]
    final = values[-1]
    best = max(values)
    worst = min(values)

    # Find where best occurred
    best_epoch = next(i for i, v in enumerate(values) if v == best)

    return {
        'initial': initial,
        'final': final,
        'best': best,
        'worst': worst,
        'best_epoch': best_epoch,
        'absolute_improvement': final - initial,
        'relative_improvement': (final - initial) / initial if initial > 0 else 0,
        'peak_improvement': (best - initial) / initial if initial > 0 else 0,
        'total_epochs': len(values)
    }


def detect_overfitting(
    results: List[Dict],
    train_metric: str = 'train/box_loss',
    val_metric: str = 'val/box_loss'
) -> Dict:
    """
    Detect potential overfitting by comparing train and validation metrics.

    Args:
        results: List of epoch results
        train_metric: Training metric name
        val_metric: Validation metric name

    Returns:
        Dict with overfitting indicators
    """
    train_values = [r[train_metric] for r in results if train_metric in r]
    val_values = [r[val_metric] for r in results if val_metric in r]

    if not train_values or not val_values:
        return {'error': 'Metrics not found'}

    # Calculate gap between train and val loss
    final_gap = val_values[-1] - train_values[-1]
    avg_gap = sum(v - t for v, t in zip(val_values, train_values)) / len(val_values)

    # Check if validation loss is increasing while train loss decreases
    train_improving = train_values[-1] < train_values[len(train_values)//2]
    val_degrading = val_values[-1] > val_values[len(val_values)//2]

    # Overfitting indicators
    overfitting = (
        final_gap > 0.1 or  # Large gap between train and val
        (train_improving and val_degrading)  # Train improves but val degrades
    )

    return {
        'overfitting_detected': overfitting,
        'final_gap': final_gap,
        'average_gap': avg_gap,
        'train_improving': train_improving,
        'val_degrading': val_degrading,
        'recommendation': 'Consider early stopping or regularization' if overfitting else 'No overfitting detected'
    }


def summarize_training_run(results_file: Path) -> Dict:
    """
    Generate comprehensive summary of training run.

    Args:
        results_file: Path to results.csv

    Returns:
        Dict with training summary
    """
    results = parse_yolo_results_csv(results_file)

    if not results:
        return {'error': 'No results found'}

    summary = {
        'total_epochs': len(results),
        'metrics': {}
    }

    # Analyze key metrics
    key_metrics = [
        'metrics/precision(B)',
        'metrics/recall(B)',
        'metrics/mAP50(B)',
        'metrics/mAP50-95(B)',
        'train/box_loss',
        'val/box_loss'
    ]

    for metric in key_metrics:
        try:
            improvement = calculate_improvement(results, metric)
            summary['metrics'][metric] = improvement
        except (ValueError, KeyError):
            pass

    # Find best epoch
    try:
        best_epoch, best_data = find_best_epoch(results)
        summary['best_epoch'] = {
            'epoch': best_epoch,
            'metrics': best_data
        }
    except ValueError:
        pass

    # Check for overfitting
    try:
        overfitting = detect_overfitting(results)
        summary['overfitting_analysis'] = overfitting
    except (ValueError, KeyError):
        pass

    return summary


def print_training_summary(results_file: Path):
    """
    Print formatted training summary.

    Args:
        results_file: Path to results.csv
    """
    summary = summarize_training_run(results_file)

    print("=" * 80)
    print("TRAINING SUMMARY")
    print("=" * 80)

    print(f"\nTotal epochs: {summary['total_epochs']}")

    if 'best_epoch' in summary:
        best = summary['best_epoch']
        print(f"\nBest epoch: {best['epoch']}")
        print("Metrics at best epoch:")
        for key, value in best['metrics'].items():
            if isinstance(value, (int, float)):
                print(f"  {key}: {value:.4f}")

    print("\nMetric Improvements:")
    for metric, stats in summary['metrics'].items():
        print(f"\n{metric}:")
        print(f"  Initial: {stats['initial']:.4f}")
        print(f"  Final:   {stats['final']:.4f}")
        print(f"  Best:    {stats['best']:.4f} (epoch {stats['best_epoch']})")
        print(f"  Change:  {stats['absolute_improvement']:+.4f} ({stats['relative_improvement']:+.1%})")

    if 'overfitting_analysis' in summary:
        ov = summary['overfitting_analysis']
        print(f"\nOverfitting Analysis:")
        print(f"  Status: {'⚠️  DETECTED' if ov['overfitting_detected'] else '✓ None detected'}")
        print(f"  Train/Val gap: {ov['final_gap']:.4f}")
        print(f"  {ov['recommendation']}")


def compare_training_runs(
    results_files: List[Tuple[str, Path]],
    metric: str = 'metrics/mAP50-95(B)'
) -> Dict:
    """
    Compare multiple training runs.

    Args:
        results_files: List of (name, path) tuples for each run
        metric: Metric to compare

    Returns:
        Dict with comparison data
    """
    comparison = {
        'metric': metric,
        'runs': {}
    }

    for name, results_file in results_files:
        try:
            results = parse_yolo_results_csv(results_file)
            best_epoch, best_data = find_best_epoch(results, metric)

            comparison['runs'][name] = {
                'best_epoch': best_epoch,
                'best_value': best_data[metric],
                'total_epochs': len(results),
                'final_value': results[-1][metric] if metric in results[-1] else None
            }
        except Exception as e:
            comparison['runs'][name] = {'error': str(e)}

    # Find overall best
    valid_runs = {k: v for k, v in comparison['runs'].items() if 'best_value' in v}
    if valid_runs:
        best_run = max(valid_runs.items(), key=lambda x: x[1]['best_value'])
        comparison['best_run'] = {
            'name': best_run[0],
            'value': best_run[1]['best_value'],
            'epoch': best_run[1]['best_epoch']
        }

    return comparison


def print_run_comparison(results_files: List[Tuple[str, Path]], metric: str = 'metrics/mAP50-95(B)'):
    """
    Print formatted comparison of training runs.

    Args:
        results_files: List of (name, path) tuples
        metric: Metric to compare
    """
    comparison = compare_training_runs(results_files, metric)

    print("=" * 80)
    print("TRAINING RUN COMPARISON")
    print("=" * 80)
    print(f"\nMetric: {metric}")

    print(f"\n{'Run Name':<30} {'Best Value':<15} {'Epoch':<10} {'Final Value':<15}")
    print("-" * 80)

    for name, data in comparison['runs'].items():
        if 'error' in data:
            print(f"{name:<30} Error: {data['error']}")
        else:
            best_val = f"{data['best_value']:.4f}" if data['best_value'] is not None else 'N/A'
            final_val = f"{data['final_value']:.4f}" if data['final_value'] is not None else 'N/A'
            epoch = data['best_epoch']
            print(f"{name:<30} {best_val:<15} {epoch:<10} {final_val:<15}")

    if 'best_run' in comparison:
        best = comparison['best_run']
        print(f"\n🏆 Best run: {best['name']} ({best['value']:.4f} at epoch {best['epoch']})")


def export_metrics_json(results_file: Path, output_file: Path):
    """
    Export metrics to JSON format.

    Args:
        results_file: Path to results.csv
        output_file: Path to output JSON file
    """
    results = parse_yolo_results_csv(results_file)
    summary = summarize_training_run(results_file)

    output = {
        'summary': summary,
        'epochs': results
    }

    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"Metrics exported to {output_file}")


def calculate_convergence_epoch(
    results: List[Dict],
    metric: str = 'metrics/mAP50-95(B)',
    threshold: float = 0.01,
    window: int = 5
) -> Optional[int]:
    """
    Estimate when training converged (metric stopped improving significantly).

    Args:
        results: List of epoch results
        metric: Metric to analyze
        threshold: Improvement threshold (default: 1%)
        window: Number of epochs to check for improvement

    Returns:
        Epoch number when convergence detected, or None if not converged
    """
    values = [r[metric] for r in results if metric in r]

    if len(values) < window:
        return None

    for i in range(len(values) - window):
        current = values[i]
        future_max = max(values[i+1:i+1+window])

        improvement = (future_max - current) / max(current, 1e-6)

        if improvement < threshold:
            return i

    return None


def estimate_training_efficiency(results: List[Dict]) -> Dict:
    """
    Estimate training efficiency metrics.

    Args:
        results: List of epoch results

    Returns:
        Dict with efficiency metrics
    """
    total_epochs = len(results)

    # Find convergence point
    convergence_epoch = calculate_convergence_epoch(results)

    # Calculate wasted epochs (after convergence)
    if convergence_epoch is not None:
        wasted_epochs = total_epochs - convergence_epoch
        efficiency = convergence_epoch / total_epochs
    else:
        wasted_epochs = 0
        efficiency = 1.0

    return {
        'total_epochs': total_epochs,
        'convergence_epoch': convergence_epoch,
        'wasted_epochs': wasted_epochs,
        'efficiency': efficiency,
        'recommendation': (
            f"Training converged at epoch {convergence_epoch}. Consider reducing patience or max epochs."
            if convergence_epoch and wasted_epochs > 10
            else "Training efficiency looks good."
        )
    }
