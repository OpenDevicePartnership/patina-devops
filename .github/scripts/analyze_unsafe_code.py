#!/usr/bin/env python3
"""
Analyze unsafe code usage from count-unsafe output and generate badge data.

Processes the output from the count-unsafe tool to calculate percentages of
unsafe code across different categories and creates JSON files for shields.io
badges.

Tool Link: https://crates.io/crates/count-unsafe

Copyright (c) Microsoft Corporation.
SPDX-License-Identifier: Apache-2.0
"""

import json
import sys
from pathlib import Path


CATEGORIES = ['functions', 'exprs', 'item_impls', 'item_traits', 'methods']

def calculate_percentage(safe_count: int, unsafe_count: int) -> float:
    """Calculate the percentage of unsafe code."""
    total = safe_count + unsafe_count
    if total == 0:
        return 0.0
    return round((unsafe_count / total) * 100, 1)


def get_badge_color(percentage: float) -> str:
    """Determine the badge color based on the percentage."""
    if percentage < 10:
        return 'green'
    elif percentage < 15:
        return 'yellow'
    else:
        return 'red'


def analyze_unsafe_code(input_file: str, output_dir: str = '.') -> dict:
    """
    Analyze unsafe code using count-unsafe.

    Args:
        input_file: Path to the raw count-unsafe JSON output
        output_dir: Directory to write output files to

    Returns:
        Dictionary containing analysis results
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    with open(input_file, 'r') as f:
        data = json.load(f)

    results = {}

    # Calculate percentages for each category
    for category in CATEGORIES:
        if category in data:
            safe = data[category]['safe']
            unsafe = data[category]['unsafe_']
            percentage = calculate_percentage(safe, unsafe)

            results[category] = {
                'safe': safe,
                'unsafe': unsafe,
                'total': safe + unsafe,
                'unsafe_percentage': percentage
            }

    total_safe = sum(results[cat]['safe'] for cat in results)
    total_unsafe = sum(results[cat]['unsafe'] for cat in results)
    overall_percentage = calculate_percentage(total_safe, total_unsafe)

    results['overall'] = {
        'safe': total_safe,
        'unsafe': total_unsafe,
        'total': total_safe + total_unsafe,
        'unsafe_percentage': overall_percentage
    }

    analysis_file = output_path / 'unsafe_analysis.json'
    with open(analysis_file, 'w') as f:
        json.dump(results, f, indent=2)

    # Create individual JSON files for each badge (since this is required by shields.io)
    for category in results:
        badge_data = {
            'schemaVersion': 1,
            'label': f'{category.replace("_", " ").title()}',
            'message': f'{results[category]["unsafe_percentage"]}%',
            'color': get_badge_color(results[category]['unsafe_percentage'])
        }

        badge_file = output_path / f'badge_{category}.json'
        with open(badge_file, 'w') as f:
            json.dump(badge_data, f, indent=2)

    return results


def print_summary(results: dict) -> None:
    """Print a summary to stdout."""
    print(f"Overall unsafe percentage: {results['overall']['unsafe_percentage']}%")

    for category in CATEGORIES:
        if category in results:
            print(f"{category}: {results[category]['unsafe_percentage']}%")


def generate_github_summary(results: dict, output_file: str) -> None:
    """
    Generate a summary table.

    Args:
        results: A dictionary with the analysis results
        output_file: Path to fiel to write to
    """
    summary_content = []
    summary_content.append("## Unsafe Code Analysis Results")
    summary_content.append("")
    summary_content.append("| Category | Safe | Unsafe | Total | Unsafe % |")
    summary_content.append("|----------|------|--------|-------|----------|")

    for category in CATEGORIES + ['overall']:
        if category in results:
            data = results[category]
            name = category.replace('_', ' ').title()
            summary_content.append(
                f"| {name} | {data['safe']} | {data['unsafe']} | "
                f"{data['total']} | {data['unsafe_percentage']}% |"
            )

    with open(output_file, 'a') as f:
        f.write('\n'.join(summary_content))
        f.write('\n')


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: analyze_unsafe_code.py <input_file> [output_dir] [--github-summary]", file=sys.stderr)
        sys.exit(1)

    input_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else '.'
    github_summary = '--github-summary' in sys.argv

    results = analyze_unsafe_code(input_file, output_dir)
    print_summary(results)

    # Generate GitHub Actions summary if requested
    if github_summary:
        import os
        github_step_summary = os.environ.get('GITHUB_STEP_SUMMARY')
        if github_step_summary:
            generate_github_summary(results, github_step_summary)
        else:
            print("Warning: GITHUB_STEP_SUMMARY environment variable not set", file=sys.stderr)


if __name__ == '__main__':
    main()
