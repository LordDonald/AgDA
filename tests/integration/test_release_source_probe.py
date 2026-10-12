"""Offline source-probe safety checks using an isolated, committed Git fixture."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools import build_release_probe as builder


class ReleaseSourceProbeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="agda-release-probe-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        self.output = self.root / "probe.py"
        self.git("init", "--quiet")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "user.name", "Probe Test")
        self.git("config", "user.email", "probe@example.invalid")
        for relative, content in {
            "packages/core.py": b"contract = 'wave5_v1'\r\n",
            "apps/api/app.py": b"ready = True\n",
            "data/releases/wave5/manifest.json": b'{"stable":true}\n',
            "pyproject.toml": b"[project]\n",
            "requirements.txt": b"package==1\n",
            "requirements-production.txt": b"package==1\n",
            "apps/web/package.json": b'{"name":"web"}\n',
            "apps/web/src/page.ts": b"export const page = 1;\n",
            "docs/notes.md": b"Documentation excluded from runtime proof.\n",
        }.items():
            path = self.checkout / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "probe fixture")
        self.revision = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.checkout), *args], stderr=subprocess.DEVNULL).decode()

    def build(self, scope="api"):
        count = builder.build_probe(self.checkout, self.revision, self.output, scope)
        namespace = {"__name__": "generated_probe_test"}
        exec(compile(self.output.read_text(encoding="utf-8"), str(self.output), "exec"), namespace)
        return count, namespace

    def run_probe(self, namespace, environment=None, argv=None, root=None):
        output = io.StringIO()
        with (redirect_stdout(output), patch.dict(os.environ, environment or {}, clear=True),
              patch.object(Path, "cwd", return_value=root or self.checkout)):
            status = namespace["main"](argv if argv is not None else ["--expected-environment", "staging"])
        return status, json.loads(output.getvalue())

    def test_exact_tracked_checkout_bytes_pass_and_exclude_unrelated_files(self):
        count, probe = self.build()
        self.assertEqual(count, 6)
        self.assertNotIn("docs/notes.md", probe["MANIFEST"])
        self.assertNotIn("apps/web/package.json", probe["MANIFEST"])
        status, result = self.run_probe(probe, {"AGDA_ENV": "staging"})
        self.assertEqual(status, 0)
        self.assertEqual(result["revision"], self.revision)
        self.assertEqual(result["mismatch_paths"], [])

    def test_dirty_or_wrong_revision_checkout_is_refused_without_output(self):
        with self.assertRaises(builder.ProbeBuildError):
            builder.build_probe(self.checkout, "0" * 40, self.output)
        (self.checkout / "untracked.txt").write_text("untracked")
        with self.assertRaises(builder.ProbeBuildError):
            self.build()
        self.assertFalse(self.output.exists())

    def test_output_inside_release_checkout_is_refused(self):
        with self.assertRaises(builder.ProbeBuildError):
            builder.build_probe(self.checkout, self.revision, self.checkout / "probe.py")
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_index_flags_cannot_hide_changed_release_source(self):
        path = self.checkout / "packages/core.py"
        original = path.read_bytes()
        for flag, reset in (("--assume-unchanged", "--no-assume-unchanged"),
                            ("--skip-worktree", "--no-skip-worktree")):
            with self.subTest(flag=flag):
                self.git("update-index", flag, "packages/core.py")
                path.write_text("hidden-change")
                self.assertEqual(self.git("status", "--porcelain"), "")
                with self.assertRaises(builder.ProbeBuildError):
                    self.build()
                path.write_bytes(original)
                self.git("update-index", reset, "packages/core.py")
        self.assertFalse(self.output.exists())

    def test_changed_and_missing_source_emit_only_relative_mismatch_paths(self):
        _, probe = self.build()
        (self.checkout / "packages/core.py").write_text("secret-changed-source")
        (self.checkout / "apps/api/app.py").unlink()
        status, result = self.run_probe(probe, {"AGDA_ENV": "production"},
                                        ["--expected-environment", "production"])
        self.assertEqual(status, 1)
        self.assertEqual(result["mismatch_paths"], ["apps/api/app.py", "packages/core.py"])
        self.assertNotIn("secret-changed-source", json.dumps(result))
        self.assertNotIn(str(self.checkout), json.dumps(result))

    def test_missing_wrong_or_conflicting_environment_refuses_before_file_reads(self):
        _, probe = self.build()
        for environment, argv in (
            ({}, ["--expected-environment", "staging"]),
            ({"AGDA_ENV": "production"}, ["--expected-environment", "staging"]),
            ({"AGDA_ENV": "staging", "RAILWAY_ENVIRONMENT_NAME": "production"}, ["--expected-environment", "staging"]),
            ({"AGDA_ENV": "staging"}, []),
        ):
            with self.subTest(environment=environment, argv=argv), patch.object(Path, "open") as file_open:
                status, result = self.run_probe(probe, environment, argv)
                self.assertEqual(status, 2)
                self.assertEqual(result["status"], "environment_refused")
                file_open.assert_not_called()

    def test_web_scope_uses_web_root_and_railway_environment_fallback(self):
        count, probe = self.build("web")
        self.assertEqual(count, 2)
        self.assertEqual(set(probe["MANIFEST"]), {"package.json", "src/page.ts"})
        status, result = self.run_probe(probe, {"RAILWAY_ENVIRONMENT_NAME": "staging"}, root=self.checkout / "apps/web")
        self.assertEqual(status, 0)
        self.assertEqual(result["file_count"], 2)

    @unittest.skipUnless(shutil.which("node"), "Node is unavailable")
    def test_node_stdin_verifier_passes_and_refuses_environment_or_source_mismatch(self):
        builder.build_probe(self.checkout, self.revision, self.output, "web", "node")
        source = self.output.read_text(encoding="utf-8")
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("AGDA_ENV", "RAILWAY_ENVIRONMENT_NAME")}
        environment["RAILWAY_ENVIRONMENT_NAME"] = "staging"

        def run(expected):
            result = subprocess.run([shutil.which("node"), "-", "--expected-environment", expected],
                                    input=source, text=True, capture_output=True, check=False,
                                    cwd=self.checkout / "apps/web", env=environment)
            self.assertEqual(result.stderr, "")
            return result.returncode, json.loads(result.stdout)

        status, result = run("staging")
        self.assertEqual(status, 0)
        self.assertEqual(result["file_count"], 2)
        status, result = run("production")
        self.assertEqual(status, 2)
        self.assertEqual(result["status"], "environment_refused")
        self.assertEqual(result["file_count"], 0)
        (self.checkout / "apps/web/src/page.ts").write_text("private-changed-content")
        status, result = run("staging")
        self.assertEqual(status, 1)
        self.assertEqual(result["mismatch_paths"], ["src/page.ts"])
        self.assertNotIn("private-changed-content", json.dumps(result))


if __name__ == "__main__":
    unittest.main(verbosity=2)
