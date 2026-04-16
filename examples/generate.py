#!/usr/bin/env python3
"""CLI for the Dimensigon Training Examples Library.

Usage:
    python examples/generate.py generate [--category CATEGORY]
    python examples/generate.py validate
    python examples/generate.py export --output FILE
    python examples/generate.py split --train RATIO --output-dir DIR
    python examples/generate.py stats
"""

import argparse
import json
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from examples.lib.base import TrainingExample
from examples.lib.registry import ExampleRegistry
from examples.lib.exporter import ChatMLExporter
from examples.lib.validator import validate_example

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger('examples')


def cmd_generate(args):
    """Generate examples from all or specific generators."""
    registry = ExampleRegistry()
    registry.auto_discover()

    if args.category:
        examples = registry.generate_category(args.category)
    else:
        examples = registry.generate_all()

    print(f"\nGenerated {len(examples)} examples")

    # Save to output directory
    output_dir = args.output_dir or os.path.join(os.path.dirname(__file__), 'output')
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, 'all_examples.json')
    with open(output_path, 'w') as f:
        json.dump([ex.to_dict() for ex in examples], f, indent=2, default=str)

    print(f"Saved to {output_path}")

    # Print stats
    stats = registry.stats
    print(f"\nBy action type:")
    for at, count in sorted(stats['by_type'].items()):
        print(f"  {at}: {count}")
    print(f"\nBy topology:")
    for topo, count in sorted(stats['by_topology'].items()):
        print(f"  {topo}: {count}")


def cmd_validate(args):
    """Validate all generated examples against DM schemas."""
    output_dir = args.output_dir or os.path.join(os.path.dirname(__file__), 'output')
    examples_path = os.path.join(output_dir, 'all_examples.json')

    if not os.path.exists(examples_path):
        print("No examples found. Run 'generate' first.")
        sys.exit(1)

    with open(examples_path) as f:
        examples_data = json.load(f)

    total = len(examples_data)
    passed = 0
    failed = 0
    errors_by_category = {}

    for ex_data in examples_data:
        ex = TrainingExample.from_dict(ex_data)
        valid, errors = validate_example(ex.dm_json, ex.entity_type)
        if valid:
            passed += 1
        else:
            failed += 1
            cat = ex.category
            errors_by_category.setdefault(cat, []).append({
                'id': ex.id,
                'errors': errors,
            })

    print(f"\nValidation Results:")
    print(f"  Total:  {total}")
    print(f"  Passed: {passed} ({100 * passed / total:.1f}%)")
    print(f"  Failed: {failed} ({100 * failed / total:.1f}%)")

    if errors_by_category:
        print(f"\nErrors by category:")
        for cat, errs in sorted(errors_by_category.items()):
            print(f"  {cat}: {len(errs)} failures")
            for e in errs[:3]:
                print(f"    {e['id']}: {e['errors'][0]}")

    # Save report
    report_path = os.path.join(output_dir, 'validation_report.json')
    with open(report_path, 'w') as f:
        json.dump({
            'total': total, 'passed': passed, 'failed': failed,
            'pass_rate': passed / total if total else 0,
            'errors': errors_by_category,
        }, f, indent=2)
    print(f"\nReport saved to {report_path}")

    sys.exit(0 if failed == 0 else 1)


def cmd_export(args):
    """Export examples to ChatML JSONL."""
    output_dir = args.output_dir or os.path.join(os.path.dirname(__file__), 'output')
    examples_path = os.path.join(output_dir, 'all_examples.json')

    if not os.path.exists(examples_path):
        print("No examples found. Run 'generate' first.")
        sys.exit(1)

    with open(examples_path) as f:
        examples_data = json.load(f)

    examples = [TrainingExample.from_dict(d) for d in examples_data]

    exporter = ChatMLExporter()
    output_file = args.output or os.path.join(output_dir, 'training_data.jsonl')
    count = exporter.export_to_file(examples, output_file)
    print(f"Exported {count} examples to {output_file}")


def cmd_split(args):
    """Split examples into train/val sets."""
    output_dir = args.output_dir or os.path.join(os.path.dirname(__file__), 'output')
    examples_path = os.path.join(output_dir, 'all_examples.json')

    if not os.path.exists(examples_path):
        print("No examples found. Run 'generate' first.")
        sys.exit(1)

    with open(examples_path) as f:
        examples_data = json.load(f)

    examples = [TrainingExample.from_dict(d) for d in examples_data]

    exporter = ChatMLExporter()
    train_path = os.path.join(output_dir, 'train.jsonl')
    val_path = os.path.join(output_dir, 'val.jsonl')

    result = exporter.split_and_export(
        examples, train_path, val_path,
        train_ratio=args.train_ratio,
    )

    print(f"Split results:")
    print(f"  Train: {result['train']} examples -> {train_path}")
    print(f"  Val:   {result['val']} examples -> {val_path}")
    print(f"  Categories: {result['categories']}")


def cmd_stats(args):
    """Show statistics about generated examples."""
    registry = ExampleRegistry()
    registry.auto_discover()
    examples = registry.generate_all()

    stats = registry.stats
    print(f"\n{'='*60}")
    print(f"Dimensigon Training Examples Library")
    print(f"{'='*60}")
    print(f"\nTotal examples: {stats['total']}")
    print(f"Generators:     {stats['generators']}")

    print(f"\nBy Action Type:")
    for at, count in sorted(stats['by_type'].items(), key=lambda x: -x[1]):
        bar = '#' * (count // 20)
        print(f"  {at:15s} {count:5d}  {bar}")

    print(f"\nBy Topology:")
    for topo, count in sorted(stats['by_topology'].items(), key=lambda x: -x[1]):
        print(f"  {topo:10s} {count:5d}")

    print(f"\nBy Difficulty:")
    for diff, count in sorted(stats['by_difficulty'].items()):
        print(f"  {diff:15s} {count:5d}")

    print(f"\nBy Category:")
    for cat, count in sorted(stats['by_category'].items()):
        print(f"  {cat:40s} {count:5d}")


def main():
    parser = argparse.ArgumentParser(description='Dimensigon Training Examples Library')
    parser.add_argument('--output-dir', help='Output directory (default: examples/output/)')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # generate
    gen_parser = subparsers.add_parser('generate', help='Generate examples')
    gen_parser.add_argument('--category', help='Generate only this category')
    gen_parser.set_defaults(func=cmd_generate)

    # validate
    val_parser = subparsers.add_parser('validate', help='Validate examples against DM schemas')
    val_parser.set_defaults(func=cmd_validate)

    # export
    exp_parser = subparsers.add_parser('export', help='Export to ChatML JSONL')
    exp_parser.add_argument('--output', help='Output JSONL file path')
    exp_parser.set_defaults(func=cmd_export)

    # split
    split_parser = subparsers.add_parser('split', help='Split into train/val sets')
    split_parser.add_argument('--train-ratio', type=float, default=0.9)
    split_parser.set_defaults(func=cmd_split)

    # stats
    stats_parser = subparsers.add_parser('stats', help='Show example statistics')
    stats_parser.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
