"""
Wrapper for build_and_run_rust_binary.py that routes streams as follows:

  - stdout: log file only (not forwarded to the console)
  - stderr: log file and the console (stderr)

This provides clean CI output where only errors surface to the console while
the full execution trace is preserved in the log file.

Configuration is supplied as a single JSON argument (inline string or file).

Usage:
  python run_qemu_validation.py '<json_string>'
  python run_qemu_validation.py --config <path_to_json_file>

JSON keys:
  build_target        (string, optional)  Build target (e.g. "DEBUG" or
                      "RELEASE"). Default: "DEBUG".
  fw_patch_repo       (string, required)  Path to the patina-fw-patcher
                      repository.
  log_file            (string, required)  Absolute path to the output log file.
  no_build            (bool, optional)    Skip building the firmware.
                      Default: false.
  patina_dxe_core_repo (string, required) Path to the patina-dxe-core-qemu
                      repository.
  patina_qemu_repo    (string, required)  Path to the patina-qemu repository
                      containing build_and_run_rust_binary.py.
  platform            (string, required)  QEMU platform name (e.g. "Q35" or
                      "SBSA").
  pre_compiled_rom    (string, required)  Path to the pre-compiled firmware ROM
                      file.
  qemu_path           (string, optional)  Path to the QEMU executable. Only
                      needed on Windows when QEMU is not on PATH. Default: "".
  shutdown_after_run  (bool, optional)    Shut down QEMU after running.
                      Default: false.
  toolchain           (string, required)  Rust toolchain tag (e.g. "GCC5" or
                      "VS2022").
"""

import argparse
import json
import os
import pathlib
import signal
import subprocess
import sys
import threading
import time
from typing import IO

# Maximum time in seconds to wait for build_and_run_rust_binary.py to complete.
SUBPROCESS_TIMEOUT_SECONDS = 300  # 5 minutes

# Maximum time in seconds to wait for stream reader threads to finish after
# the subprocess exits or is killed. This is to prevent indefinite hangs when
# grandchild processes (e.g. QEMU) keep pipe handles open.
THREAD_JOIN_TIMEOUT_SECONDS = 15

# Default values applied when a key is absent in the JSON input.
_DEFAULTS = {
    "build_target": "DEBUG",
    "qemu_path": "",
    "no_build": False,
    "shutdown_after_run": False,
}


def _coerce_bool(value: "bool | str") -> bool:
    """Normalize a boolean that may arrive as a JSON bool or a string."""
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


def _load_config() -> dict:
    """Load configuration from a JSON string argument or a JSON file.

    Supported invocations:

        python run_qemu_validation.py '<json_string>'
        python run_qemu_validation.py --config path/to/config.json

    When ``--config`` is given, the file is loaded as JSON. Otherwise the
    first positional argument is parsed as an inline JSON string.
    """
    parser = argparse.ArgumentParser(
        description="Run QEMU validation with JSON configuration.",
    )
    parser.add_argument(
        "json_config",
        nargs="?",
        default=None,
        help="Inline JSON configuration string.",
    )
    parser.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="Path to a JSON configuration file.",
    )
    args = parser.parse_args()

    if args.config:
        with open(args.config, encoding="utf-8") as f:
            raw = json.load(f)
    elif args.json_config:
        raw = json.loads(args.json_config)
    else:
        parser.error("Provide a JSON string argument or --config <path>.")

    for key, default in _DEFAULTS.items():
        raw.setdefault(key, default)

    raw["no_build"] = _coerce_bool(raw["no_build"])
    raw["shutdown_after_run"] = _coerce_bool(raw["shutdown_after_run"])

    return raw


def _stream_reader(
    stream: IO[bytes],
    log_file_handle: IO[bytes],
    forward_to: "IO[bytes] | None",
) -> None:
    """Read all lines from stream, write to log file, and optionally forward."""
    for line in iter(stream.readline, b""):
        log_file_handle.write(line)
        log_file_handle.flush()
        if forward_to is not None:
            forward_to.write(line)
            forward_to.flush()
    stream.close()


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """Kill a process and all of its descendants.

    On Windows, ``process.kill()`` only terminates the immediate child. If
    that child spawned long-running grandchildren (e.g. QEMU), those keep
    running and hold inherited pipe handles open, which causes the stream
    reader threads to hang indefinitely. This helper uses ``taskkill /T``
    on Windows to tear down the entire tree. On POSIX systems it kills the
    process group when the subprocess was started in its own session.
    """
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            capture_output=True,
        )
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _write_timing(log_path: pathlib.Path, elapsed_seconds: float) -> None:
    """Write a timing JSON file alongside the log for downstream consumption.

    The file is written to ``<log_stem>.timing.json`` in the same directory
    as the log file.  It will automatically be picked up in the log artifact
    upload step.
    """
    timing_path = log_path.with_suffix(".timing.json")
    minutes, secs = divmod(elapsed_seconds, 60)
    timing_data = {
        "elapsed_seconds": round(elapsed_seconds, 2),
        "elapsed_display": (
            f"{int(minutes)}m {secs:.0f}s" if minutes >= 1
            else f"{secs:.1f}s"
        ),
    }
    timing_path.write_text(json.dumps(timing_data), encoding="utf-8")


def main() -> int:
    config = _load_config()

    script = pathlib.Path(config["patina_qemu_repo"]) / "build_and_run_rust_binary.py"
    log_path = pathlib.Path(config["log_file"])
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(script),
        "--build-target", config["build_target"],
        "--fw-patch-repo", config["fw_patch_repo"],
        "--patina-dxe-core-repo", config["patina_dxe_core_repo"],
        "--platform", config["platform"],
        "--pre-compiled-rom", config["pre_compiled_rom"],
        "--toolchain", config["toolchain"],
    ]

    if config.get("qemu_path"):
        cmd += ["--qemu-path", config["qemu_path"]]
    cmd.append("--headless")
    if config.get("no_build"):
        cmd.append("--no-build")
    if config.get("shutdown_after_run"):
        cmd.append("--shutdown-after-run")

    start_time = time.monotonic()

    with log_path.open("ab") as log_fh:
        # Start the subprocess in its own process group / session so that
        # the entire tree (including QEMU) can be killed on timeout.
        popen_kwargs: dict = {}
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **popen_kwargs,
        )

        # stdout: write to log file only, not forwarded to the console.
        stdout_thread = threading.Thread(
            target=_stream_reader,
            args=(process.stdout, log_fh, None),
        )
        # stderr: write to log file and forward to the console.
        stderr_thread = threading.Thread(
            target=_stream_reader,
            args=(process.stderr, log_fh, sys.stderr.buffer),
        )

        stdout_thread.start()
        stderr_thread.start()

        timed_out = False
        try:
            return_code = process.wait(timeout=SUBPROCESS_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_process_tree(process)
            try:
                return_code = process.wait(
                    timeout=THREAD_JOIN_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                return_code = 1
        finally:
            # Prevent orphaned grandchild processes from holding pipe handles
            # that cause threads to hang forever.
            stdout_thread.join(timeout=THREAD_JOIN_TIMEOUT_SECONDS)
            stderr_thread.join(timeout=THREAD_JOIN_TIMEOUT_SECONDS)

    elapsed_seconds = time.monotonic() - start_time
    _write_timing(log_path, elapsed_seconds)

    if timed_out:
        timeout_msg = (
            f"ERROR: build_and_run_rust_binary.py timed out after "
            f"{SUBPROCESS_TIMEOUT_SECONDS} seconds.\n"
        ).encode()
        sys.stderr.buffer.write(timeout_msg)
        sys.stderr.buffer.flush()
        with log_path.open("ab") as log_fh:
            log_fh.write(timeout_msg)
        return 1

    if config.get("shutdown_after_run"):
        shutdown_drive = pathlib.Path(config["patina_qemu_repo"]) / "Build" / "shutdown_drive"
        if shutdown_drive.exists():
            uefi_logs = shutdown_drive / "UefiLogs"
            if not uefi_logs.exists():
                failure_msg = (
                    f"ERROR: Boot did not succeed: UefiLogs directory not found in "
                    f"'{shutdown_drive}'.\n"
                ).encode()
                sys.stderr.buffer.write(failure_msg)
                sys.stderr.buffer.flush()
                with log_path.open("ab") as log_fh:
                    log_fh.write(failure_msg)
                return 1

    return return_code


if __name__ == "__main__":
    sys.exit(main())
