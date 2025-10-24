#!/usr/bin/env python3
"""
Analyze unsafe code using cargo-geiger and generate shields.io badge JSON files.

cargo-geiger: https://crates.io/crates/cargo-geiger

Processes cargo-geiger JSON output to create badge files for shields.io. Only workspace
crates are analyzed (excluding dependencies). Output files are split up target triples
(e.g., x86_64-unknown-uefi, aarch64-unknown-uefi) and include an overall badge file and
category-specific badge files.

Note: cargo-geiger can be run manually to get results against custom targets, features, etc.

This is meant to provide a rough approximation of unsafe code present in the codebase.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

CATERGORIES = ["functions", "exprs", "item_impls", "item_traits", "methods"]

def calculate_percentage(unsafe_count: int, total_count: int) -> float:
    """Calculate the percentage of unsafe code."""
    if total_count == 0:
        return 0.0
    return (unsafe_count / total_count) * 100


def get_badge_color(percentage: float) -> str:
    """Determine the badge color based on unsafe percentage.

    Args:
        percentage: Percentage of unsafe code

    Returns:
        Color name for the shields.io badge
    """
    if percentage < 10:
        return "green"
    elif percentage < 15:
        return "yellow"
    else:
        return "red"


def run_cargo_geiger(workspace_root: Path, target: str) -> List[Dict]:
    """Run cargo-geiger for workspace packages and parse JSON output.

    Args:
        workspace_root: Path to the workspace root directory
        target: Target triple (e.g., "x86_64-unknown-uefi")

    Returns:
        List of workspace package entries from cargo-geiger JSON output
    """
    # First, get the list of workspace members and their paths
    metadata_cmd = [
        "cargo", "metadata",
        "--no-deps",
        "--format-version", "1"
    ]

    print(f"Getting workspace members...")
    metadata_result = subprocess.run(
        metadata_cmd,
        capture_output=True,
        text=True,
        check=True,
        cwd=str(workspace_root)
    )

    metadata = json.loads(metadata_result.stdout)
    workspace_packages_info = {
        pkg["name"]: Path(pkg["manifest_path"]).parent
        for pkg in metadata.get("packages", [])
    }

    print(f"Found {len(workspace_packages_info)} workspace members")

    # Run cargo-geiger from each package directory
    all_workspace_packages = []
    workspace_root_str = str(workspace_root).lower().replace('\\', '/')

    for pkg_name, pkg_path in workspace_packages_info.items():
        print(f"Running cargo-geiger for {pkg_name} at {pkg_path}...")

        geiger_cmd = [
            "cargo", "geiger",
            "--output-format", "Json",
            "--all-features",
            "--target", target
        ]

        try:
            env = os.environ.copy()
            env['RUSTC_BOOTSTRAP'] = '1'

            geiger_result = subprocess.run(
                geiger_cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=str(pkg_path),
                env=env
            )

            # cargo-geiger may output build messages before JSON
            # Find the start of JSON by looking for {"packages":
            output_lines = geiger_result.stdout.strip().split('\n')
            json_start = -1

            for i, line in enumerate(output_lines):
                stripped = line.strip()
                if stripped.startswith('{"packages":[') or stripped.startswith('{"packages": ['):
                    json_start = i
                    break

            if json_start == -1:
                print(f"  Warning: No JSON output found from cargo-geiger for {pkg_name}")
                continue

            json_output = '\n'.join(output_lines[json_start:])
            data = json.loads(json_output)
            all_packages = data.get("packages", [])

            # Filter to only the workspace packages (Path source within workspace)
            for pkg in all_packages:
                pkg_id = pkg.get("package", {}).get("id", {})
                pkg_source = pkg_id.get("source", {})

                # Check if this is a workspace package (Path source within workspace)
                if "Path" in pkg_source:
                    path_value = pkg_source.get("Path", "").lower().replace('\\', '/')
                    if workspace_root_str in path_value:
                        # Avoid adding duplicates
                        pkg_id_str = json.dumps(pkg_id, sort_keys=True)
                        if not any(json.dumps(p.get("package", {}).get("id", {}), sort_keys=True) == pkg_id_str
                                   for p in all_workspace_packages):
                            all_workspace_packages.append(pkg)

        except subprocess.CalledProcessError as e:
            print(f"  Error running cargo-geiger for {pkg_name}: {e}")
            if e.stderr:
                print(f"  stderr: {e.stderr}")
            continue

    print(f"Successfully analyzed {len(all_workspace_packages)} workspace packages")
    return all_workspace_packages


def aggregate_metrics(packages: List[Dict]) -> Dict[str, Dict[str, int]]:
    """Aggregate unsafe metrics from multiple packages.

    Args:
        packages: List of package entries from cargo-geiger

    Returns:
        Dictionary with aggregated metrics by category
    """
    aggregated = {cat: {"safe": 0, "unsafe": 0} for cat in CATERGORIES}

    for package in packages:
        unsafety = package.get("unsafety", {})
        used = unsafety.get("used", {})

        # Only aggregate "used" metrics, not "unused"
        for category in CATERGORIES:
            cat_data = used.get(category, {})
            aggregated[category]["safe"] += cat_data.get("safe", 0)
            aggregated[category]["unsafe"] += cat_data.get("unsafe_", 0)

    return aggregated


def create_badge_json(label: str, message: str, color: str) -> Dict:
    """Create a shields.io JSON object.

    Args:
        label: Badge label
        message: Badge message
        color: Badge color

    Returns:
        Dictionary in shields.io JSON format
    """
    return {
        "schemaVersion": 1,
        "label": label,
        "message": message,
        "color": color
    }


def generate_badges(metrics: Dict[str, Dict[str, int]], output_dir: Path) -> None:
    """Generate all badge JSON files from aggregated metrics.

    Args:
        metrics: Aggregated metrics by category
        output_dir: Directory to write badge JSON files
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Calculate totals for the overall badge
    total_safe = sum(cat["safe"] for cat in metrics.values())
    total_unsafe = sum(cat["unsafe"] for cat in metrics.values())
    total_count = total_safe + total_unsafe
    overall_percentage = calculate_percentage(total_unsafe, total_count)
    overall_color = get_badge_color(overall_percentage)

    # Create the overall badge
    overall_badge = create_badge_json(
        "overall",
        f"{overall_percentage:.1f}%",
        overall_color
    )

    with open(output_dir / "badge_overall.json", "w") as f:
        json.dump(overall_badge, f, indent=2)

    print(f"Created badge_overall.json: {overall_percentage:.1f}% ({overall_color})")

    # Create category-specific badges
    category_names = {
        "functions": "functions",
        "exprs": "expressions",
        "item_impls": "item impls",
        "item_traits": "item traits",
        "methods": "methods"
    }

    for category, label in category_names.items():
        safe_count = metrics[category]["safe"]
        unsafe_count = metrics[category]["unsafe"]
        total = safe_count + unsafe_count
        percentage = calculate_percentage(unsafe_count, total)
        color = get_badge_color(percentage)

        badge = create_badge_json(label, f"{percentage:.1f}%", color)

        output_file = output_dir / f"badge_{category}.json"
        with open(output_file, "w") as f:
            json.dump(badge, f, indent=2)

        print(f"Created {output_file.name}: {percentage:.1f}% ({color})")


def generate_summary(metrics: Dict[str, Dict[str, int]], target: str) -> str:
    """Generate a markdown summary of unsafe code analysis.

    Args:
        metrics: Aggregated metrics by category
        target: Target triple

    Returns:
        Markdown formatted summary
    """
    summary = f"# Unsafe Code Analysis for {target}\n\n"

    # Overall statistics
    total_safe = sum(cat["safe"] for cat in metrics.values())
    total_unsafe = sum(cat["unsafe"] for cat in metrics.values())
    total_count = total_safe + total_unsafe
    overall_percentage = calculate_percentage(total_unsafe, total_count)

    summary += f"**Overall Unsafe Percentage:** {overall_percentage:.1f}%\n\n"
    summary += f"- Total Safe: {total_safe:,}\n"
    summary += f"- Total Unsafe: {total_unsafe:,}\n"
    summary += f"- Total Items: {total_count:,}\n\n"

    # Category breakdown
    summary += "## Category Breakdown\n\n"
    summary += "| Category | Safe | Unsafe | Total | Unsafe % |\n"
    summary += "|----------|------|--------|-------|----------|\n"

    for category in CATERGORIES:
        safe_count = metrics[category]["safe"]
        unsafe_count = metrics[category]["unsafe"]
        total = safe_count + unsafe_count
        percentage = calculate_percentage(unsafe_count, total)

        summary += f"| {category} | {safe_count:,} | {unsafe_count:,} | {total:,} | {percentage:.1f}% |\n"

    return summary


def analyze_target(workspace_root: Path, target: str, output_dir: Path) -> Tuple[Dict, str]:
    """Analyze unsafe code for a specific target.

    Args:
        workspace_root: Path to workspace root
        target: Target triple
        output_dir: Output directory for badge files

    Returns:
        Tuple of (aggregated metrics, markdown summary)
    """
    print(f"\n{'='*60}")
    print(f"Analyzing target: {target}")
    print(f"{'='*60}\n")

    # Run cargo-geiger for all workspace crates
    packages = run_cargo_geiger(workspace_root, target)

    if not packages:
        print(f"Error: No packages analyzed for target {target}")
        sys.exit(1)

    print(f"\nSuccessfully analyzed {len(packages)} workspace packages")

    metrics = aggregate_metrics(packages)

    target_output_dir = output_dir / target
    generate_badges(metrics, target_output_dir)

    summary = generate_summary(metrics, target)

    return metrics, summary


def main():
    """Main entry point for the script."""
    # Use current directory for the workspace root if it has Cargo.toml, otherwise error
    workspace_root = Path.cwd()

    if not (workspace_root / "Cargo.toml").exists():
        print("Error: No Cargo.toml found in the current directory", file=sys.stderr)
        print("Run this script from the workspace root", file=sys.stderr)
        sys.exit(1)

    print(f"Workspace root: {workspace_root}")

    # Define targets to analyze
    targets = [
        "x86_64-unknown-uefi",
        "aarch64-unknown-uefi"
    ]

    # Output directory for badges
    output_dir = workspace_root / "unsafe-code-analysis"

    # Analyze each target
    all_summaries = []
    all_metrics = {}

    for target in targets:
        metrics, summary = analyze_target(workspace_root, target, output_dir)
        all_metrics[target] = metrics
        all_summaries.append(summary)

    # Write combined summary
    combined_summary = "\n\n".join(all_summaries)
    summary_file = output_dir / "unsafe_analysis.md"

    with open(summary_file, "w") as f:
        f.write(combined_summary)

    print(f"\n{'='*60}")
    print("Analysis Done.")
    print(f"{'='*60}")
    print(f"\nResults written to: {output_dir}")
    print(f"Summary: {summary_file}")

    metrics_json = output_dir / "unsafe_analysis.json"
    with open(metrics_json, "w") as f:
        json.dump(all_metrics, f, indent=2)

    print(f"Metrics JSON: {metrics_json}")


if __name__ == "__main__":
    main()
