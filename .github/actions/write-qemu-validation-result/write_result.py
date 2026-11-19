"""
Writes a result.json summarizing one QEMU validation run (test apps or OS boot).

The file is uploaded with the run's logs and read by the Patina QEMU PR Validation Post workflow. It is treated
as untrusted input there. Keep the field names in sync with render_os_boot_and_tests.py in
.github/actions/render-os-boot-and-test-results.

Usage:
  python write_result.py '<json_string>'

JSON keys:
  kind             (string, required)  "test-apps" or "os-boot".
  platform         (string, required)  "Q35" or "ArmVirt".
  target           (string, required)  "DEBUG" or "RELEASE".
  outcome          (string, required)  Outcome of the run step: "success", "failure", "cancelled", "skipped", or
                   "unavailable" when the inputs needed to run were not available.
  reason           (string, optional)  Why the run was unavailable.
  log_file         (string, required)  Path to the run's log file. Timing and test results are read from files next
                   to it (<stem>.timing.json and <stem>.test-results.json).
  output           (string, required)  Path to write result.json to.
  os_artifact      (string, optional)  Name of the OS image artifact (OS boot only).
  os_boot_device   (string, optional)  Device the OS image was attached as (OS boot only).
  image_metadata   (string, optional)  Path to the OS image metadata JSON (OS boot only).

Copyright (c) Microsoft Corporation.
SPDX-License-Identifier: Apache-2.0
"""

import json
import pathlib
import sys

SCHEMA_VERSION = 1


def _read_json(path: pathlib.Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def build_result(config: dict) -> dict:
    outcome = config["outcome"]
    if outcome == "success":
        result = "success"
    elif outcome == "unavailable":
        result = "unavailable"
    else:
        result = "failure"

    log_path = pathlib.Path(config["log_file"])
    result_data = {
        "schema_version": SCHEMA_VERSION,
        "kind": config["kind"],
        "platform": config["platform"],
        "target": config["target"],
        "result": result,
        "reason": config.get("reason", ""),
    }

    timing = _read_json(log_path.with_suffix(".timing.json")) or {}
    for key in ("elapsed_seconds", "qemu_run_seconds"):
        if isinstance(timing.get(key), (int, float)):
            result_data[key] = timing[key]

    try:
        result_data["timed_out"] = b"timed out after" in log_path.read_bytes()
    except OSError:
        result_data["timed_out"] = False

    if config["kind"] == "os-boot":
        result_data["os_artifact"] = config.get("os_artifact", "")
        result_data["os_boot_device"] = config.get("os_boot_device", "")
        metadata = _read_json(pathlib.Path(config["image_metadata"])) if config.get("image_metadata") else None
        if isinstance(metadata, dict):
            result_data["os_family"] = metadata.get("os_family", "")
            result_data["os_version"] = metadata.get("os_version", "")
            result_data["bootloader"] = metadata.get("bootloader")
    else:
        test_results = _read_json(log_path.with_suffix(".test-results.json"))
        if isinstance(test_results, dict):
            result_data["apps"] = test_results.get("apps", [])

    return result_data


def main() -> int:
    config = json.loads(sys.argv[1])
    output = pathlib.Path(config["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_result(config), indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
