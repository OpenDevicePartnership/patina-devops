"""Test OS boot and test-app Markdown summaries using synthetic result artifacts.

Covers result validation, missing results, durations, and escaping untrusted text.
Run with: python -m unittest test_render_os_boot_and_tests

Copyright (c) Microsoft Corporation.
SPDX-License-Identifier: Apache-2.0
"""

import json
import pathlib
import tempfile
import unittest

import render_os_boot_and_tests as render


def write_result(root: pathlib.Path, artifact: str, **fields) -> None:
    directory = root / artifact
    directory.mkdir()
    (directory / "result.json").write_text(json.dumps({"schema_version": 1, **fields}), encoding="utf-8")


def os_boot(root, platform, target, family, result="success", seconds=72.0, **extra):
    artifact_name = f"{family}-{'x64' if platform == 'Q35' else 'aarch64'}-image"
    write_result(
        root,
        f"qemu-os-boot-{platform}-{target}-{family}",
        kind="os-boot",
        platform=platform,
        target=target,
        result=result,
        qemu_run_seconds=seconds,
        os_artifact=artifact_name,
        **extra,
    )


class RenderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_os_boot_table(self):
        ubuntu = {"os_version": "24.04.2", "bootloader": {"name": "GRUB", "version": "2.12-1", "shim_version": "15.8"}}
        os_boot(self.root, "Q35", "DEBUG", "ubuntu", seconds=72, **ubuntu)
        os_boot(self.root, "Q35", "RELEASE", "ubuntu", result="failure", timed_out=True, **ubuntu)
        os_boot(self.root, "Q35", "DEBUG", "windows", seconds=125)

        markdown = render.render_os_boot(render.load_results(self.root, "os-boot"))

        self.assertIn("| Q35 | Ubuntu 24.04.2 (x64) | GRUB 2.12-1, shim 15.8 | :white_check_mark: 1m 12s | :x: timed out |", markdown)
        self.assertIn("| Q35 | Windows Validation OS (x64) | — | :white_check_mark: 2m 5s | :grey_question: no result |", markdown)
        self.assertIn("| ArmVirt | Ubuntu (aarch64) | — | :grey_question: no result | :grey_question: no result |", markdown)

    def test_test_apps_failures_and_unavailable(self):
        apps = [
            {"name": "GoodTestApp.efi", "result_found": True, "cases": [{"name": "a", "result": "pass", "message": ""}]},
            {
                "name": "BadTestApp.efi",
                "result_found": True,
                "cases": [{"name": "b", "result": "fail", "message": "expected 1"}],
            },
            {"name": "MissingTestApp.efi", "result_found": False, "cases": []},
        ]
        write_result(
            self.root, "qemu-test-apps-Q35-DEBUG", kind="test-apps", platform="Q35", target="DEBUG",
            result="failure", qemu_run_seconds=38.2, apps=apps,
        )
        write_result(
            self.root, "qemu-test-apps-Q35-RELEASE", kind="test-apps", platform="Q35", target="RELEASE",
            result="unavailable", reason="The patina-qemu release does not include test apps.",
        )

        markdown = render.render_test_apps(render.load_results(self.root, "test-apps"), "v6.1.0")

        self.assertIn("| Q35 | DEBUG | :x: | 3 | 1 | 2 | 38.2s |", markdown)
        self.assertIn("| Q35 | RELEASE | :grey_question: unavailable |", markdown)
        self.assertIn("`BadTestApp.efi` b: expected 1", markdown)
        self.assertIn("`MissingTestApp.efi`: no result file was produced", markdown)
        self.assertIn("releases/tag/v6.1.0", markdown)

    def test_untrusted_text_cannot_inject_markdown_or_mentions(self):
        apps = [
            {
                "name": "EvilTestApp.efi",
                "result_found": True,
                "cases": [{"name": "[x](http://evil)", "result": "fail", "message": "@octocat |<img src=x> #1\n# heading"}],
            },
            {"name": "bad name|with pipe.efi", "result_found": True, "cases": []},
        ]
        write_result(
            self.root, "qemu-test-apps-Q35-DEBUG", kind="test-apps", platform="Q35", target="DEBUG",
            result="failure", apps=apps,
        )

        markdown = render.render_test_apps(render.load_results(self.root, "test-apps"), "")

        self.assertNotIn("@octocat", markdown)
        self.assertIn("\\<img src=x\\>", markdown)
        self.assertNotIn("](http", markdown)
        self.assertNotIn("bad name", markdown)
        self.assertNotIn("\n# heading", markdown)

    def test_invalid_results_are_ignored(self):
        write_result(self.root, "qemu-test-apps-Q35-DEBUG", kind="os-boot", platform="Q35", target="DEBUG", result="success")
        write_result(self.root, "qemu-test-apps-Q35-RELEASE", kind="test-apps", platform="Q35", target="RELEASE", result="passed")
        write_result(self.root, "qemu-test-apps-ArmVirt-DEBUG", kind="test-apps", platform="Evil", target="DEBUG", result="success")
        write_result(
            self.root, "qemu-os-boot-Q35-DEBUG-ubuntu", kind="os-boot", platform="Q35", target="DEBUG",
            result="success", os_artifact="../../etc/passwd",
        )

        self.assertEqual(render.load_results(self.root, "test-apps"), {})
        self.assertEqual(render.load_results(self.root, "os-boot"), {})

    def test_durations_reject_bad_numbers(self):
        os_boot(self.root, "Q35", "DEBUG", "windows", seconds=float("inf"), elapsed_seconds=-5)

        result = render.load_results(self.root, "os-boot")[("Q35", "DEBUG", "windows")]

        self.assertIsNone(result["seconds"])


if __name__ == "__main__":
    unittest.main()
