#!/usr/bin/env python3
"""Test the Node policy without downloading runtimes or starting containers."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import re
import subprocess
import sys
import unittest
import hashlib
from pathlib import Path
from unittest.mock import patch
from datetime import date, datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("node_policy", ROOT / "scripts/check-node-security.py")
assert spec is not None and spec.loader is not None
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
POLICY_TEST_DATE = date(2026, 10, 21)
verify_spec = importlib.util.spec_from_file_location("source_verifier", ROOT / "scripts/verify-source.py")
assert verify_spec is not None and verify_spec.loader is not None
verifier = importlib.util.module_from_spec(verify_spec)
verify_spec.loader.exec_module(verifier)


class ActionRuntimeBindingTests(unittest.TestCase):
    def setUp(self):
        self.canonical = (ROOT / "scripts/action-runtime.ps1").read_bytes()
        self.workflow = (ROOT / ".github/workflows/source-security.yml").read_text()

    def test_first_step_binds_exact_vetted_source_bytes(self):
        self.assertEqual(hashlib.sha256(self.canonical).hexdigest(),
                         "1e078b8a740865abfea7c5d3310b5930a5c7e135f02f89e5f9d09dd0e37cf38d")
        self.assertTrue(verifier.action_runtime_binding_matches(self.canonical, self.workflow))
        block = self.workflow.removeprefix(verifier.WORKFLOW_PREFIX).removesuffix(verifier.WORKFLOW_SUFFIX)
        self.assertEqual("".join(line[10:] for line in block.splitlines(keepends=True)).encode(), self.canonical)

    def test_editing_inline_and_canonical_together_cannot_replace_vetted_probe(self):
        changed = self.canonical.replace(b"24.22.1", b"24.21.0")
        self.assertFalse(verifier.action_runtime_binding_matches(changed, self.workflow.replace("24.22.1", "24.21.0")))

    def test_node20_unknown_runtime_and_skip_override_mutations_fail(self):
        mutations = (
            self.workflow.replace("@('node24')", "@('node20')"),
            self.workflow.replace("@('node24')", "@('node99')"),
            self.workflow.replace("        id: action-runtime\n", "        id: action-runtime\n        if: false\n"),
            self.workflow.replace("    steps:\n", "    env:\n      ACTIONS_RUNNER_FORCE_ACTIONS_NODE_VERSION: node20\n    steps:\n"),
            self.workflow.replace("d23441a48e516b6c34aea4fa41551a30e30af803", "unreviewed"),
        )
        for changed in mutations:
            with self.subTest(changed=changed[:80]):
                self.assertNotEqual(changed, self.workflow)
                self.assertFalse(verifier.action_runtime_binding_matches(self.canonical, changed))

    def test_early_expressions_diagnostics_extra_jobs_and_containers_fail(self):
        mutations = (
            self.workflow.replace("    steps:\n", "    env:\n      EARLY: ${{ hashFiles('**') }}\n    steps:\n"),
            self.workflow + "      - uses: unreviewed/diagnostics@main\n        if: always()\n",
            self.workflow + "  other-job:\n    runs-on: ubuntu-24.04\n    steps: []\n",
            self.workflow.replace("    steps:\n", "    container: node:20\n    steps:\n"),
            self.workflow.replace("    steps:\n", "    steps:\n      - run: echo unreviewed\n"),
        )
        for changed in mutations:
            with self.subTest(changed=changed[:80]):
                self.assertFalse(verifier.action_runtime_binding_matches(self.canonical, changed))


class ComposeBindSerializationTests(unittest.TestCase):
    def probe(self, disabled, enabled, defaulted):
        return {"services": {name: {"volumes": [volume]} for name, volume in
                             (("disabled", disabled), ("enabled", enabled), ("defaulted", defaulted))}}

    def test_old_serializer_omitted_false_is_accepted_only_as_disabled(self):
        disabled = {"type": "bind", "bind": {}}
        enabled = {"type": "bind", "bind": {"create_host_path": True}}
        defaulted = {"type": "bind"}
        signature = verifier.disabled_bind_signature(self.probe(disabled, enabled, defaulted))
        self.assertTrue(verifier.bind_disables_creation(disabled, signature))
        self.assertFalse(verifier.bind_disables_creation(enabled, signature))
        self.assertFalse(verifier.bind_disables_creation(defaulted, signature))

    def test_new_serializer_omitted_true_is_rejected(self):
        disabled = {"type": "bind", "bind": {"create_host_path": False}}
        enabled = {"type": "bind", "bind": {}}
        signature = verifier.disabled_bind_signature(self.probe(disabled, enabled, enabled))
        self.assertTrue(verifier.bind_disables_creation(disabled, signature))
        self.assertFalse(verifier.bind_disables_creation(enabled, signature))

    def test_probe_must_distinguish_false_from_true_and_default(self):
        disabled = {"type": "bind", "bind": {}}
        enabled = {"type": "bind", "bind": {"create_host_path": True}}
        for probe in (self.probe(disabled, disabled, enabled), self.probe(disabled, enabled, disabled)):
            with self.subTest(probe=probe), self.assertRaises(ValueError):
                verifier.disabled_bind_signature(probe)

    def test_present_non_boolean_or_malformed_bind_options_fail(self):
        signature = (True, True, False)
        for options in ({"create_host_path": True}, {"create_host_path": None}, {"create_host_path": "false"}, {"create_host_path": 0}, None, [], "false"):
            with self.subTest(options=options):
                self.assertFalse(verifier.bind_disables_creation({"type": "bind", "bind": options}, signature))
        self.assertFalse(verifier.bind_disables_creation({"type": "bind"}, signature))
        self.assertFalse(verifier.bind_disables_creation({"type": "volume"}, signature))
        self.assertFalse(verifier.bind_disables_creation({}, signature))
        self.assertFalse(verifier.bind_disables_creation({"type": "bind", "bind": {"create_host_path": False}}, None))

    def test_missing_or_malformed_probe_fails_closed(self):
        for probe in (None, {}, {"services": []}, {"services": {}}, {"services": {"disabled": {"volumes": []}}}):
            with self.subTest(probe=probe), self.assertRaises(ValueError):
                verifier.disabled_bind_signature(probe)


class VersionPolicyTests(unittest.TestCase):
    def test_affected_releases_fail(self):
        for version in ("22.23.2", "22.23.3", "v24.19.0", "24.21.0", "24.22.0", "26.12.0"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                policy.check_version(version, today=POLICY_TEST_DATE)

    def test_fixed_supported_releases_pass(self):
        for version in ("22.23.4", "v24.22.1", "26.12.1", "22.24.0", "24.22.2", "26.13.0"):
            with self.subTest(version=version):
                policy.check_version(version, today=POLICY_TEST_DATE)

    def test_unsupported_and_eol_fail(self):
        for version in ("18.20.8", "20.20.2", "23.11.0", "25.9.0", "27.0.0", "28.0.0"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                policy.check_version(version, today=POLICY_TEST_DATE)

    def test_malformed_prerelease_and_ranges_fail(self):
        for version in ("", "22", "22.23", ">=22.23.4", "24.x", "24.22.1-rc.1", "24.22.1+build", " 24.22.1", "24.22.1\n", "024.22.1", "v24.22.1\njunk"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                policy.check_version(version, today=POLICY_TEST_DATE)

    def test_each_supported_line_expires_on_its_utc_date(self):
        for version, expiry in (("22.23.4", date(2027, 4, 30)), ("24.22.1", date(2028, 4, 30)), ("26.12.1", date(2029, 4, 30))):
            with self.subTest(version=version):
                policy.check_version(version, today=expiry.replace(day=29))
                for today in (expiry, expiry.replace(month=5, day=1)):
                    with self.assertRaisesRegex(ValueError, "expired Node major"):
                        policy.check_version(version, today=today)

    def test_default_clock_uses_utc_and_enforces_expiry(self):
        with patch.object(policy, "datetime") as clock:
            clock.now.return_value = datetime(2027, 4, 30, 0, 0, tzinfo=timezone.utc)
            with self.assertRaisesRegex(ValueError, "expired Node major 22"):
                policy.check_version("22.23.4")
            clock.now.assert_called_once_with(timezone.utc)


class ActualExecutableTests(unittest.TestCase):
    def invoke(self, result=None, error=None, argv=None):
        with patch.object(sys, "argv", argv or ["check-node-security.py"]), \
             patch.object(policy.subprocess, "run", return_value=result, side_effect=error) as run, \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            status = policy.main()
        return status, run

    def test_actual_executable_is_queried(self):
        status, run = self.invoke(subprocess.CompletedProcess([], 0, "v22.23.4\n", ""))
        self.assertEqual(status, 0)
        run.assert_called_once_with(["node", "--version"], stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=10, check=True)

    def test_actual_affected_and_invalid_output_fail(self):
        for output in ("v22.23.2\n", "v24.22.0\n", "v24.22.1\njunk\n", "v24.22.1 \n"):
            with self.subTest(output=output):
                status, _ = self.invoke(subprocess.CompletedProcess([], 0, output, ""))
                self.assertEqual(status, 1)

    def test_missing_failed_and_timed_out_node_fail(self):
        for error in (FileNotFoundError("node"), subprocess.CalledProcessError(1, ["node"]), subprocess.TimeoutExpired(["node"], 10)):
            with self.subTest(error=type(error).__name__):
                status, _ = self.invoke(error=error)
                self.assertEqual(status, 1)

    def test_cli_version_override_is_refused(self):
        status, run = self.invoke(argv=["check-node-security.py", "--version", "24.22.1"])
        self.assertEqual(status, 1)
        run.assert_not_called()

    def test_cli_date_override_is_refused(self):
        status, run = self.invoke(argv=["check-node-security.py", "--date", "2026-10-21"])
        self.assertEqual(status, 1)
        run.assert_not_called()

    def test_actual_runtime_fails_after_utc_expiry(self):
        with patch.object(policy, "datetime") as clock:
            clock.now.return_value = datetime(2027, 4, 30, tzinfo=timezone.utc)
            status, _ = self.invoke(subprocess.CompletedProcess([], 0, "v22.23.4\n", ""))
        self.assertEqual(status, 1)


class ImageContractTests(unittest.TestCase):
    def test_both_images_use_incident_specific_ubuntu_ca_fix(self):
        for name in ("Dockerfile.dev", "Dockerfile.proxy"):
            with self.subTest(dockerfile=name):
                dockerfile = (ROOT / name).read_text()
                self.assertIn("ca-certificates=20260816ubuntu0.24.04.1", dockerfile)
                self.assertNotIn("ca-certificates=20260601~24.04.1", dockerfile)

    def test_pinned_release_has_not_expired_in_current_utc(self):
        dockerfile = (ROOT / "Dockerfile.dev").read_text()
        version = re.search(r'^ARG NODE_VERSION=(.*)$', dockerfile, re.MULTILINE)
        self.assertIsNotNone(version)
        policy.check_version(version.group(1))

    def test_build_arg_override_fails_before_download(self):
        dockerfile = (ROOT / "Dockerfile.dev").read_text()
        match = re.search(r'^RUN (test "\$\{NODE_VERSION\}" = "22\.23\.4")$', dockerfile, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertLess(dockerfile.index(match.group(0)), dockerfile.index("RUN curl"))
        bash = (Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/bin/bash.exe") if os.name == "nt" else Path("/bin/bash")
        for value in ("22.23.2", "24.19.0", "24.21.0", "24.22.0", "24.22.1", "22.23.4", "22.23.4; exit 0", ""):
            environment = os.environ.copy()
            environment.pop("BASH_ENV", None)
            environment.pop("ENV", None)
            environment["NODE_VERSION"] = value
            result = subprocess.run([str(bash), "--noprofile", "--norc", "-c", match.group(1)],
                                    env=environment, stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
            with self.subTest(version=value):
                self.assertEqual(result.returncode == 0, value == "22.23.4", result.stderr.decode(errors="replace"))

    def test_archive_and_actual_runtime_are_checked(self):
        dockerfile = (ROOT / "Dockerfile.dev").read_text()
        self.assertIn("ARG NODE_VERSION=22.23.4\n", dockerfile)
        self.assertIn("1805bcd35e6815559bd2eb97db438d3fdb0eb3a5e6a977b7c1badca76337e9ce  /tmp/node.tar.xz", dockerfile)
        self.assertLess(dockerfile.index("sha256sum --check --strict"), dockerfile.index("tar -xJf /tmp/node.tar.xz"))
        self.assertNotIn('"node@${NODE_VERSION}"', dockerfile)
        self.assertLess(dockerfile.index("/usr/local/bin/habitat-python /usr/local/lib/habitat/check-node-security.py"), dockerfile.index("RUN corepack enable"))
        self.assertIn('ENTRYPOINT ["/bin/bash", "/usr/local/bin/habitat-entrypoint"]', dockerfile)

    def test_corepack_and_global_tools_keep_user_writable_paths(self):
        dockerfile = (ROOT / "Dockerfile.dev").read_text()
        self.assertIn('RUN corepack enable --install-directory "${PNPM_HOME}/bin"', dockerfile)
        self.assertLess(dockerfile.index("USER ubuntu"), dockerfile.index("RUN corepack enable"))
        self.assertIn("/home/ubuntu/.local/share/pnpm/bin:/home/ubuntu/.local/share/pnpm:", dockerfile)

    def test_startup_guard_precedes_command_and_new_image_is_required(self):
        entrypoint = (ROOT / "scripts/habitat-entrypoint.sh").read_text()
        self.assertEqual(entrypoint, '#!/usr/bin/env bash\nset -euo pipefail\n\n/usr/local/bin/habitat-python /usr/local/lib/habitat/check-node-security.py\nexec "$@"\n')
        self.assertIn("image: habitat-vivary/dev:2026-10-21-node22.23.4", (ROOT / "compose.yaml").read_text())
        self.assertIn("image: habitat-vivary/proxy:2026-10-21-emudhra", (ROOT / "compose.yaml").read_text())

    def test_guard_python_link_tracks_the_build_pin_before_user_switch(self):
        dockerfile = (ROOT / "Dockerfile.dev").read_text()
        link = 'RUN ln -s "${MISE_DATA_DIR}/installs/python/${PYTHON_VERSION}/bin/python" /usr/local/bin/habitat-python'
        self.assertIn(link, dockerfile)
        self.assertLess(dockerfile.index(link), dockerfile.index("USER ubuntu"))
        self.assertIn('test "$(/usr/local/bin/habitat-python --version)" = "Python ${PYTHON_VERSION}"', dockerfile)

    def run_entrypoint_fixture(self, entrypoint, guard_status=0):
        bash = (Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/bin/bash.exe") if os.name == "nt" else Path("/bin/bash")
        environment = os.environ.copy()
        environment.pop("BASH_ENV", None)
        environment.pop("ENV", None)
        # Model an unavailable project-selected Python without executing mise.
        fixture = '''function python { printf 'project Python is not installed\\n' >&2; return 127; }
function /usr/local/bin/habitat-python {
    [[ "$#" -eq 1 && "$1" == /usr/local/lib/habitat/check-node-security.py ]] || return 99
    printf 'guard\\n'
    return GUARD_STATUS
}
set -- /usr/bin/printf 'command:%s\\n' 'argument with spaces'
'''.replace("GUARD_STATUS", str(guard_status))
        return subprocess.run([str(bash), "--noprofile", "--norc", "-c", fixture + entrypoint],
                              env=environment, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=10)

    def test_project_python_shim_old_fails_and_pinned_guard_reaches_command(self):
        entrypoint = (ROOT / "scripts/habitat-entrypoint.sh").read_text()
        old_entrypoint = entrypoint.replace("/usr/local/bin/habitat-python ", "python ", 1)
        self.assertNotEqual(old_entrypoint, entrypoint)
        old = self.run_entrypoint_fixture(old_entrypoint)
        self.assertEqual(old.returncode, 127)
        self.assertIn("project Python is not installed", old.stderr)
        self.assertEqual(old.stdout, "")
        fixed = self.run_entrypoint_fixture(entrypoint)
        self.assertEqual(fixed.returncode, 0, fixed.stderr)
        self.assertEqual(fixed.stdout, "guard\ncommand:argument with spaces\n")
        self.assertEqual(fixed.stderr, "")

    def test_pinned_guard_failure_still_blocks_requested_command(self):
        result = self.run_entrypoint_fixture((ROOT / "scripts/habitat-entrypoint.sh").read_text(), guard_status=9)
        self.assertEqual(result.returncode, 9)
        self.assertEqual(result.stdout, "guard\n")
        self.assertEqual(result.stderr, "")

    def test_only_reviewed_scripts_enter_build_context(self):
        self.assertEqual((ROOT / ".dockerignore").read_text(), "**\n!Dockerfile.dev\n!Dockerfile.proxy\n!squid.conf\n!scripts/\nscripts/**\n!scripts/check-node-security.py\n!scripts/habitat-entrypoint.sh\n")

    def test_ci_runs_all_source_controls_without_publishing(self):
        workflow = (ROOT / ".github/workflows/source-security.yml").read_text()
        for command in ("python3 scripts/test-node-security.py", "python3 scripts/verify-source.py", "python3 scripts/test-cli.py"):
            self.assertIn(command, workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("continue-on-error", workflow)
        self.assertNotIn("push: true", workflow)
        self.assertNotIn("packages: write", workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
