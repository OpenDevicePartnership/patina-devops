"""
Renders the test app and OS boot sections of the Patina QEMU PR validation comment.

Reads the result.json files uploaded by the validate-test-apps and validate-os-boot jobs (artifacts named
qemu-test-apps-* and qemu-os-boot-*) and writes test-apps-section.md and os-boot-section.md.

Those jobs run the pull request's code, so the values read from result.json are untrusted. A result that
fails validation is treated as missing.

Usage:
  python render_os_boot_and_tests.py --results-dir <dir> --output-dir <dir> [--release-tag <tag>]
      [--test-apps-enabled true|false] [--os-boot-enabled true|false]

Copyright (c) Microsoft Corporation.
SPDX-License-Identifier: Apache-2.0
"""

import argparse
import json
import math
import pathlib
import re
from typing import Dict, List, Optional, Tuple

SCHEMA_VERSION = 1
MAX_RESULT_BYTES = 2 * 1024 * 1024
MAX_APPS = 200
MAX_CASES_PER_APP = 2000
MAX_FAILURES_LISTED = 20

PLATFORMS = ("Q35", "ArmVirt")
TARGETS = ("DEBUG", "RELEASE")
ARCHITECTURES = {"Q35": "x64", "ArmVirt": "aarch64"}
OS_FAMILIES = ("ubuntu", "windows")
OS_ARTIFACTS = ("ubuntu-x64-image", "ubuntu-aarch64-image", "windows-x64-image", "windows-aarch64-image")
OS_BOOT_ROWS = [(platform, family) for platform in PLATFORMS for family in OS_FAMILIES]

PASS = ":white_check_mark:"
FAIL = ":x:"
UNKNOWN = ":grey_question:"

_APP_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_VERSION = re.compile(r"^[A-Za-z0-9.+~:_-]{1,64}$")
_OS_VERSION = re.compile(r"^[A-Za-z0-9.+~:_ -]{1,64}$")
_TAG = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]<>()#+!|~&:])")


def sanitize(value: object, limit: int) -> str:
    """Returns `value` as single-line text that renders literally in markdown and cannot mention users."""
    text = value if isinstance(value, str) else ""
    text = "".join(ch if ch.isprintable() else " " for ch in text)
    text = " ".join(text.split())
    truncated = len(text) > limit
    text = _MARKDOWN_SPECIAL.sub(r"\\\1", text[:limit]).replace("@", "@\u200b")
    return text + ("..." if truncated else "")


def _seconds(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0 or value > 86400:
        return None
    return float(value)


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "N/A"
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes)}m {secs:.0f}s" if minutes >= 1 else f"{seconds:.1f}s"


def _load_result(path: pathlib.Path, kind: str) -> Optional[dict]:
    """Loads and validates one result.json, returning None if it is missing or invalid."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_RESULT_BYTES:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION or data.get("kind") != kind:
        return None
    if data.get("platform") not in PLATFORMS or data.get("target") not in TARGETS:
        return None
    if data.get("result") not in ("success", "failure", "unavailable"):
        return None

    result = {
        "platform": data["platform"],
        "target": data["target"],
        "result": data["result"],
        "reason": sanitize(data.get("reason"), 200),
        "timed_out": data.get("timed_out") is True,
        "seconds": _seconds(data.get("qemu_run_seconds")),
    }
    if result["seconds"] is None:
        result["seconds"] = _seconds(data.get("elapsed_seconds"))

    if kind == "os-boot":
        artifact = data.get("os_artifact")
        family = artifact.split("-", 1)[0] if artifact in OS_ARTIFACTS else ""
        if not family:
            return None
        result["os_family"] = family
        version = data.get("os_version")
        result["os_version"] = version if isinstance(version, str) and _OS_VERSION.match(version) else ""
        result["bootloader"] = None
        bootloader = data.get("bootloader")
        if isinstance(bootloader, dict) and bootloader.get("name") == "GRUB":
            grub = bootloader.get("version")
            shim = bootloader.get("shim_version")
            result["bootloader"] = {
                "grub": grub if isinstance(grub, str) and _VERSION.match(grub) else "",
                "shim": shim if isinstance(shim, str) and _VERSION.match(shim) else "",
            }
    else:
        apps = []
        raw_apps = data.get("apps")
        for raw_app in raw_apps[:MAX_APPS] if isinstance(raw_apps, list) else []:
            if not isinstance(raw_app, dict) or not isinstance(raw_app.get("name"), str):
                continue
            if not _APP_NAME.match(raw_app["name"]):
                continue
            cases = []
            raw_cases = raw_app.get("cases")
            for raw_case in raw_cases[:MAX_CASES_PER_APP] if isinstance(raw_cases, list) else []:
                if not isinstance(raw_case, dict):
                    continue
                cases.append(
                    {
                        "name": sanitize(raw_case.get("name"), 200),
                        "passed": raw_case.get("result") == "pass",
                        "message": sanitize(raw_case.get("message"), 300),
                    }
                )
            apps.append({"name": raw_app["name"], "found": raw_app.get("result_found") is True, "cases": cases})
        result["apps"] = apps

    return result


def load_results(results_dir: pathlib.Path, kind: str) -> Dict[Tuple, dict]:
    """Loads every valid result for `kind`, keyed by (platform, target[, os_family])."""
    prefix = "qemu-test-apps-" if kind == "test-apps" else "qemu-os-boot-"
    results = {}
    if not results_dir.is_dir():
        return results

    for artifact_dir in sorted(results_dir.iterdir()):
        if not artifact_dir.is_dir() or artifact_dir.is_symlink() or not artifact_dir.name.startswith(prefix):
            continue
        result = _load_result(artifact_dir / "result.json", kind)
        if result is None:
            continue
        key = (result["platform"], result["target"])
        if kind == "os-boot":
            key += (result["os_family"],)
        results[key] = result
    return results


def _cell(result: Optional[dict]) -> str:
    if result is None:
        return f"{UNKNOWN} no result"
    if result["result"] == "success":
        return f"{PASS} {format_duration(result['seconds'])}"
    if result["result"] == "unavailable":
        return f"{UNKNOWN} unavailable"
    return f"{FAIL} timed out" if result["timed_out"] else f"{FAIL} failed"


def render_os_boot(results: Dict[Tuple, dict]) -> str:
    lines = ["### OS Boot Results", ""]
    if not results:
        return "\n".join(lines + ["No OS boot results were produced.", ""])

    lines += [
        "| Platform | OS | Bootloader | DEBUG | RELEASE |",
        "|:---------|:---|:-----------|:------|:--------|",
    ]
    for platform, family in OS_BOOT_ROWS:
        cells = {target: results.get((platform, target, family)) for target in TARGETS}
        known = next((cell for cell in cells.values() if cell is not None and cell["os_version"]), None)

        bootloader = "—"
        if family == "windows":
            os_name = "Windows Validation OS"
        else:
            os_name = "Ubuntu" + (f" {sanitize(known['os_version'], 64)}" if known else "")
            if known and known["bootloader"]:
                grub = sanitize(known["bootloader"]["grub"], 64)
                shim = sanitize(known["bootloader"]["shim"], 64)
                parts = [f"GRUB {grub}" if grub else "", f"shim {shim}" if shim else ""]
                bootloader = ", ".join(part for part in parts if part) or "—"

        lines.append(
            f"| {platform} | {os_name} ({ARCHITECTURES[platform]}) | {bootloader} | "
            f"{_cell(cells['DEBUG'])} | {_cell(cells['RELEASE'])} |"
        )

    lines += [
        "",
        "Booted from an SSD. Time is QEMU power-on to guest power-off, so it includes OS shutdown.",
        "Q35 runs with KVM acceleration and ArmVirt with TCG emulation, so times are not comparable across platforms.",
        "USB boot is covered by the nightly OS boot test in patina-qemu.",
        "",
    ]
    return "\n".join(lines)


def _app_totals(result: dict) -> Tuple[int, int, int]:
    """Returns (apps, passed cases, failed cases). An app without a usable result counts as one failure."""
    passed = sum(1 for app in result["apps"] for case in app["cases"] if case["passed"])
    failed = sum(1 for app in result["apps"] for case in app["cases"] if not case["passed"])
    failed += sum(1 for app in result["apps"] if not app["found"])
    return len(result["apps"]), passed, failed


def render_test_apps(results: Dict[Tuple, dict], release_tag: str) -> str:
    lines = ["### EFI Test App Results", ""]
    if not results:
        return "\n".join(lines + ["No test app results were produced.", ""])

    if release_tag and _TAG.match(release_tag):
        lines += [
            "Pre-compiled test apps from the "
            f"[`{release_tag}`](https://github.com/OpenDevicePartnership/patina-qemu/releases/tag/{release_tag}) "
            "patina-qemu release.",
            "",
        ]

    lines += [
        "| Platform | Target | Result | Apps | Cases passed | Cases failed | Elapsed |",
        "|:---------|:-------|:------:|-----:|-------------:|-------------:|--------:|",
    ]
    failures: List[str] = []
    ordered = [(platform, target) for platform in PLATFORMS for target in TARGETS]
    for platform, target in ordered:
        result = results.get((platform, target))
        if result is None:
            lines.append(f"| {platform} | {target} | {UNKNOWN} no result | - | - | - | - |")
            continue
        if result["result"] == "unavailable":
            lines.append(f"| {platform} | {target} | {UNKNOWN} unavailable | - | - | - | - |")
            continue

        apps, passed, failed = _app_totals(result)
        icon = PASS if result["result"] == "success" else FAIL
        lines.append(
            f"| {platform} | {target} | {icon} | {apps} | {passed} | {failed} | {format_duration(result['seconds'])} |"
        )
        if result["result"] != "success" and not result["apps"]:
            reason = "timed out" if result["timed_out"] else "failed"
            failures.append(f"- {platform} {target}: the run {reason} before test results were produced")
        for app in result["apps"]:
            if not app["found"]:
                failures.append(f"- {platform} {target} `{app['name']}`: no result file was produced")
            failures += [
                f"- {platform} {target} `{app['name']}` {case['name']}: {case['message']}"
                for case in app["cases"]
                if not case["passed"]
            ]

    reasons = {r["reason"] for r in results.values() if r["result"] == "unavailable" and r["reason"]}
    for reason in sorted(reasons):
        lines += ["", reason]

    if failures:
        lines += ["", "#### Failed Test Cases", ""]
        lines += failures[:MAX_FAILURES_LISTED]
        if len(failures) > MAX_FAILURES_LISTED:
            more = len(failures) - MAX_FAILURES_LISTED
            lines.append(f"- ...and {more} more. See the test app logs in the workflow run artifacts.")

    app_names = sorted({app["name"] for r in results.values() if r["result"] != "unavailable" for app in r["apps"]})
    if app_names:
        lines += [
            "",
            "<details><summary>Per-app results</summary>",
            "",
            "| App | Q35 DEBUG | Q35 RELEASE | ArmVirt DEBUG | ArmVirt RELEASE |",
            "|:----|:---------:|:-----------:|:-------------:|:---------------:|",
        ]
        for name in app_names:
            cells = []
            for platform, target in ordered:
                result = results.get((platform, target))
                app = next((a for a in result["apps"] if a["name"] == name), None) if result else None
                if app is None:
                    cells.append("-")
                elif not app["found"]:
                    cells.append(f"{FAIL} no result")
                else:
                    passed = sum(1 for case in app["cases"] if case["passed"])
                    icon = PASS if passed == len(app["cases"]) else FAIL
                    cells.append(f"{icon} {passed}/{len(app['cases'])}")
            lines.append(f"| `{name}` | {' | '.join(cells)} |")
        lines += ["", "</details>"]

    lines.append("")
    return "\n".join(lines)


def _as_bool(value: str) -> bool:
    return value.lower() == "true"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-dir", type=pathlib.Path, required=True)
    parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    parser.add_argument("--release-tag", default="")
    parser.add_argument("--test-apps-enabled", type=_as_bool, default=False)
    parser.add_argument("--os-boot-enabled", type=_as_bool, default=False)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    test_apps = ""
    if args.test_apps_enabled:
        test_apps = render_test_apps(load_results(args.results_dir, "test-apps"), args.release_tag)
    os_boot = ""
    if args.os_boot_enabled:
        os_boot = render_os_boot(load_results(args.results_dir, "os-boot"))

    (args.output_dir / "test-apps-section.md").write_text(test_apps, encoding="utf-8")
    (args.output_dir / "os-boot-section.md").write_text(os_boot, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
