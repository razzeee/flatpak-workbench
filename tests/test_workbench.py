import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flatpak_workbench import cargo
from flatpak_workbench.cli import parser
from flatpak_workbench.feedback import check, lint_result, probe
from flatpak_workbench.generate import generate
from flatpak_workbench.inspect import inspect_checkout
from flatpak_workbench.process import WorkbenchError


@unittest.skipUnless(shutil.which("cargo") and shutil.which("git"), "requires Cargo and Git")
class CheckoutTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "upstream"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.org")
        self.git("remote", "add", "origin", "https://example.org/upstream.git")
        (self.root / "Cargo.toml").write_text('[workspace]\nmembers=["app"]\nresolver="2"\n')
        (self.root / "app/src").mkdir(parents=True)
        (self.root / "app/Cargo.toml").write_text('[package]\nname="app"\nversion="0.1.0"\nedition="2021"\n')
        (self.root / "app/src/main.rs").write_text('fn main() {}\n')
        subprocess.run(["cargo", "generate-lockfile", "--offline"], cwd=self.root, check=True, capture_output=True)
        self.commit()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True).stdout.strip()

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")

    def arguments(self):
        generator = self.base / "generator.py"
        generator.write_text("# placeholder; generator process is stubbed in unit tests\n")
        return parser().parse_args([
            "init", str(self.root), "--app-id", "org.example.App", "--runtime", "org.freedesktop.Platform",
            "--runtime-version", "26.08", "--sdk", "org.freedesktop.Sdk", "--cargo-generator", str(generator),
            "--output", str(self.base / "package"),
        ])

    def test_workspace_selection_and_pinned_export(self):
        def generator(directory, name, argv, cwd, timeout=None):
            (directory / "cargo-sources.json").write_text("[]\n")
            return {"exit_code": 0}, ""
        args = self.arguments()
        with patch("flatpak_workbench.generate.recorded_run", side_effect=generator):
            result = generate(args)
        manifest = json.loads(Path(result["manifest"]).read_text())
        module = manifest["modules"][0]
        self.assertEqual(module["sources"][0]["commit"], self.git("rev-parse", "HEAD"))
        self.assertIn("--package app --bin app", module["build-commands"][0])
        self.assertIn("--offline --locked", module["build-commands"][0])
        self.assertEqual(self.git("status", "--porcelain"), "")
        with self.assertRaisesRegex(WorkbenchError, "new output"):
            generate(args)

    def test_mixed_project_preserves_evidence_and_refuses_cargo_shortcut(self):
        (self.root / "meson.build").write_text("project('app')\n")
        (self.root / "app.metainfo.xml.in.in").write_text("<component><id>org.example.App</id></component>")
        self.commit()
        evidence = inspect_checkout(self.root)
        self.assertEqual({item["kind"] for item in evidence["build_systems"]}, {"cargo", "meson"})
        self.assertEqual(evidence["metadata"][0]["app_id"], "org.example.App")
        with self.assertRaisesRegex(WorkbenchError, "outer build system"):
            generate(self.arguments())

    def test_dirty_checkout_is_not_exported(self):
        (self.root / "untracked.txt").write_text("local changes")
        with self.assertRaisesRegex(WorkbenchError, "clean, committed"):
            generate(self.arguments())

    def test_unsupported_lock_source_is_not_silently_omitted(self):
        with (self.root / "Cargo.lock").open("a") as lock:
            lock.write('\n[[package]]\nname="external"\nversion="1.0.0"\nsource="git+https://example.org/lib#abc"\n')
        with self.assertRaisesRegex(WorkbenchError, "Unsupported Cargo source"):
            cargo.validate(self.root, "app", "app")

    def test_ambiguous_binaries_require_selection(self):
        (self.root / "app/src/bin").mkdir()
        (self.root / "app/src/bin/other.rs").write_text("fn main() {}")
        with self.assertRaisesRegex(WorkbenchError, "Select one executable"):
            cargo.validate(self.root, None, None)
        self.assertEqual(cargo.validate(self.root, "app", "other")[1]["name"], "other")


class FeedbackTests(unittest.TestCase):
    def test_linter_empty_success_and_non_json_failure(self):
        self.assertEqual(lint_result({"exit_code": 0}, "")["status"], "passed")
        self.assertEqual(lint_result({"exit_code": 1}, "Traceback")["status"], "tool-error")
        result = lint_result({"exit_code": 1}, '{"errors":["bad-id"],"future":true}')
        self.assertTrue(result["findings"]["future"])

    def test_probe_does_not_misclassify_launch_failure_as_missing(self):
        def execute(argv, timeout=120):
            code = 0 if argv[1] == "info" else {"zlib": 0, "missing": 42, "broken": 1}[argv[-1]]
            return subprocess.CompletedProcess(argv, code, "identity-or-version", "")
        with patch("flatpak_workbench.feedback.run", side_effect=execute):
            result = probe("org.example.Sdk//1", ["zlib", "missing", "broken"])
        self.assertEqual([item["status"] for item in result["requirements"]], ["present", "missing", "unknown"])

    def test_probe_timeout_reports_unknown(self):
        identity = subprocess.CompletedProcess([], 0, "sdk-commit", "")
        with patch("flatpak_workbench.feedback.run", side_effect=[identity, WorkbenchError("Timed out")]):
            result = probe("org.example.Sdk//1", ["zlib"])
        self.assertEqual(result["requirements"][0]["status"], "unknown")

    def test_missing_sdk_retains_lint_and_blocks_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "org.example.App.json"
            manifest.write_text(json.dumps({"sdk": "org.example.Sdk", "runtime": "org.example.Platform", "runtime-version": "1"}))
            def execute(directory, name, argv, cwd=None, timeout=120):
                if name == "build":
                    self.fail("build should not run without SDK")
                return {"exit_code": 1 if name == "sdk" else 0}, ""
            with patch("flatpak_workbench.feedback.recorded_run", side_effect=execute):
                result = check(manifest, root / "runs")
            self.assertEqual(result["build"]["status"], "blocked")
            self.assertEqual(result["manifest-lint"]["status"], "passed")
            self.assertFalse(result["success"])
            self.assertTrue((Path(result["run_directory"]) / "result.json").is_file())

    def test_failed_build_retains_logs_without_linting_incomplete_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "org.example.App.json"
            manifest.write_text(json.dumps({"sdk": "org.example.Sdk", "runtime": "org.example.Platform", "runtime-version": "1"}))
            def execute(argv, cwd=None, timeout=120):
                if any(arg.startswith("--repo=") for arg in argv):
                    return subprocess.CompletedProcess(argv, 23, "compiler output", "missing header")
                return subprocess.CompletedProcess(argv, 0, "", "")
            with patch("flatpak_workbench.process.run", side_effect=execute):
                result = check(manifest, root / "runs")
            directory = Path(result["run_directory"])
            self.assertEqual(result["build"]["status"], "failed")
            self.assertEqual(result["build"]["exit_code"], 23)
            self.assertEqual((directory / "build.stdout").read_text(), "compiler output")
            self.assertEqual((directory / "build.stderr").read_text(), "missing header")
            self.assertNotIn("repo-lint", result)


if __name__ == "__main__":
    unittest.main()
