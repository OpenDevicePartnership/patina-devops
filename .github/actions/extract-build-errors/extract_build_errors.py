#!/usr/bin/env python3
# Extract full compiler error/warning sections from QEMU validation logs.
#
# Scans a directory of log files for rustc diagnostic blocks and build-system
# errors, then writes a JSON file mapping artifact directory names to markdown
# snippets for embedding in PR comments.
#
# Usage:
#   python extract_build_errors.py <logs-dir> <output-json>
#
# Arguments:
#   logs-dir     Path to the directory containing downloaded log artifacts.
#                Each artifact is expected to be in a subdirectory, e.g.
#                logs/qemu-validation-logs-Linux-Q35/build.log
#   output-json  Path to write the resulting JSON error map.
#
# Output format (JSON):
#   {
#     "qemu-validation-logs-Linux-Q35": [
#       "<details>...</details>"
#     ],
#     ...
#   }
#
# Example:
#   python extract_build_errors.py logs/ error-map.json
#
# Copyright (c) Microsoft Corporation.
# SPDX-License-Identifier: Apache-2.0
##

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

# Max number of combined output lines per log file before truncation.
MAX_SNIPPET_LINES = 60

# ---------------------------------------------------------------------------
# Regex patterns for rustc diagnostic parsing
# ---------------------------------------------------------------------------

# Patterns that start a compilation error/warning section.
# Multi-line blocks from rustc.
#   error[E0425]: cannot find value ...
#   error: could not compile ...
#   warning: unused import ...
#   warning: `crate` (lib) generated N warning(s)
SECTION_START_RE = re.compile(
    r"^(error(\[E\d+\])?:|warning(\[[\w\d]+\])?:)\s"
)

# cargo-make build error messages
BUILD_ERROR_RE = re.compile(
    r"\[cargo-make\] ERROR|error: build failed|error: could not compile"
)

# Rustc source-gutter lines are like:
# - "  637 | code..."
# - "    | ^^^"
# - Diff: "  637 - old" / "  637 + new".
# - Cross-file reference: "  ::: path/to/file.rs:37:1".
RUSTC_GUTTER_RE = re.compile(r"^\s*(\d+\s*[|+\-]|[|]|\.\.\.|:::)\s?")

# More info hint line
RUSTC_INFO_RE = re.compile(r"^For more information about this error")


def extract_error_sections(lines: list[str]) -> list[str]:
    """Extract full compiler error/warning sections and build errors.

    Compiler diagnostics are multi-line blocks that contain conextual info.

    This function captures each block as a whole rather than individual lines.

    Args:
        lines: All lines from a single log file.

    Returns:
        A list of section strings, each representing one complete diagnostic
        block or build-system error line.
    """
    sections: list[str] = []
    current_section: list[str] = []
    in_section = False

    for line in lines:
        if SECTION_START_RE.match(line):
            if current_section:
                sections.append("\n".join(current_section))
            current_section = [line]
            in_section = True
        elif in_section:
            stripped = line.strip()
            is_continuation = (
                stripped.startswith("|")
                or stripped.startswith("-->")
                or stripped.startswith("=")
                or stripped.startswith("help:")
                or stripped.startswith("note:")
                or bool(RUSTC_GUTTER_RE.match(line))
                or bool(RUSTC_INFO_RE.match(line))
                or stripped == ""
            )
            if is_continuation:
                current_section.append(line)
            else:
                sections.append("\n".join(current_section))
                current_section = []
                in_section = False

                if BUILD_ERROR_RE.search(line):
                    sections.append(line)
        elif BUILD_ERROR_RE.search(line):
            sections.append(line)

    # Flush any trailing section.
    if current_section:
        sections.append("\n".join(current_section))

    return sections


def build_error_map(logs_dir: pathlib.Path) -> dict[str, list[str]]:
    """Scan *logs_dir* for log files and build a per-artifact error map.

    The returned dict maps subdirectory names to lists of markdown
    ``<details>`` snippets.

    Args:
        logs_dir: Root directory containing downloaded log artifacts.

    Returns:
        A dict keyed by artifact subdirectory name with markdown snippet
        lists as values.
    """
    error_map: dict[str, list[str]] = {}

    if not logs_dir.is_dir():
        return error_map

    for log_file in sorted(logs_dir.rglob("*.log")):
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        sections = extract_error_sections(lines)

        if not sections:
            continue

        # Combine sections and trim to a reasonable size.
        combined = "\n\n".join(sections)
        combined_lines = combined.splitlines()
        if len(combined_lines) > MAX_SNIPPET_LINES:
            combined_lines = combined_lines[-MAX_SNIPPET_LINES:]
            combined = "… (truncated)\n" + "\n".join(combined_lines)
        else:
            combined = "\n".join(combined_lines)

        # Key is the artifact subdirectory (e.g. "qemu-validation-logs-Linux-Q35")
        artifact_dir = log_file.relative_to(logs_dir).parts[0]
        label = str(log_file.relative_to(logs_dir))
        n_sections = len(sections)
        summary_text = (
            f'{n_sections} error/warning section{"s" if n_sections != 1 else ""}'
        )
        snippet = (
            f"<details>\n<summary><code>{label}</code>"
            f" ({summary_text})</summary>\n\n```\n"
        )
        snippet += combined
        snippet += "\n```\n</details>"
        error_map.setdefault(artifact_dir, []).append(snippet)

    return error_map


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Extract compiler error sections from platform validation logs."
    )
    parser.add_argument(
        "logs_dir",
        type=pathlib.Path,
        help="Directory containing downloaded log artifacts.",
    )
    parser.add_argument(
        "output_json",
        type=pathlib.Path,
        help="Path to write the JSON error map.",
    )
    args = parser.parse_args(argv)

    error_map = build_error_map(args.logs_dir)
    args.output_json.write_text(json.dumps(error_map), encoding="utf-8")

    total_snippets = sum(len(v) for v in error_map.values())
    print(
        f"Wrote {len(error_map)} artifact(s) with "
        f"{total_snippets} snippet(s) to {args.output_json}"
    )


if __name__ == "__main__":
    main()
