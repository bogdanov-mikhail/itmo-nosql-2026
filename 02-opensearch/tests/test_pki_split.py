import os
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMAGE = os.environ.get("PKI_TEST_IMAGE")
PASSWORDS = ("OPENSEARCH_INITIAL_ADMIN_PASSWORD", "KIBANASERVER_PASSWORD",
             "LOGSHIPPER_PASSWORD", "ANALYST_PASSWORD", "METRICSAGENT_PASSWORD")


class ComposePkiTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("docker"), "нужен Docker Compose")
    def test_node_security_volumes_do_not_copy_default_users(self):
        result = subprocess.run(
            ["docker", "compose", "config", "--format", "json"],
            cwd=ROOT, capture_output=True, text=True, check=True, timeout=30,
        )
        services = json.loads(result.stdout)["services"]
        for name in ("os-hot", "os-warm"):
            with self.subTest(node=name):
                mount = next(v for v in services[name]["volumes"]
                             if v["target"] == "/usr/share/opensearch/config/opensearch-security")
                self.assertTrue(mount.get("volume", {}).get("nocopy", False))


@unittest.skipUnless(IMAGE, "укажите PKI_TEST_IMAGE для изолированных тестов PKI")
class PkiSplitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        for name in ("pki", "security", "hot", "warm"):
            (self.dir / name).mkdir()

    def run_stage(self, script, password="OnlyForLocalTestsAa9!"):
        env = os.environ.copy()
        env.update({key: password for key in PASSWORDS})
        command = [
            "docker", "run", "--rm", "--network", os.environ.get("PKI_TEST_NETWORK", "none"),
            "-v", f"{self.dir}:/certs",
            "-v", f"{ROOT / 'certs'}:/source/certs:ro",
            "-v", f"{ROOT / 'setup'}:/source/setup:ro",
            "-e", "PKI_DATA_HOT=/certs/hot", "-e", "PKI_DATA_WARM=/certs/warm",
            "-e", "PKI_STATE=/source/certs/pki-state.sh",
        ]
        for key in PASSWORDS:
            command.extend(("-e", key))
        command.extend((IMAGE, "sh", f"/source/{script}"))
        return subprocess.run(command, env=env, capture_output=True, text=True, timeout=90)

    def stage_ok(self, script):
        result = self.run_stage(script)
        self.assertEqual(result.returncode, 0, result.stderr)

    def snapshot(self):
        return {str(p.relative_to(self.dir)): p.read_bytes()
                for p in self.dir.rglob("*") if p.is_file()}

    def test_first_launch_interrupted_between_stages_and_repeat(self):
        self.stage_ok("certs/make-certs.sh")
        self.assertFalse((self.dir / "security/internal_users.yml").exists())
        verify = subprocess.run([
            "docker", "run", "--rm", "--network", "none",
            "-v", f"{self.dir / 'pki'}:/pki:ro", "--entrypoint", "openssl",
            os.environ.get("PKI_VERIFY_IMAGE", IMAGE), "verify", "-CAfile", "/pki/root-ca.crt", "-verify_hostname",
            "os-hot", "/pki/os-hot.crt",
        ], capture_output=True, text=True, timeout=20)
        self.assertEqual(verify.returncode, 0, verify.stderr)
        before = self.snapshot()
        self.stage_ok("certs/make-certs.sh")
        self.assertEqual(before, self.snapshot())
        self.stage_ok("setup/make-users.sh")
        after = self.snapshot()
        self.assertIn("security/internal_users.yml", after)
        self.stage_ok("certs/make-certs.sh")
        self.stage_ok("setup/make-users.sh")
        result = self.run_stage("setup/make-users.sh", "DifferentLocalTestBb8!")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(after, self.snapshot())
        self.assertEqual((self.dir / "pki/os-hot.key").stat().st_mode & 0o777, 0o600)

    def test_incomplete_or_existing_data_fail_without_writes(self):
        for relative in ("pki/root-ca.crt", "security/internal_users.yml", "hot/existing"):
            with self.subTest(relative=relative):
                for name in ("pki", "security", "hot", "warm"):
                    shutil.rmtree(self.dir / name)
                    (self.dir / name).mkdir()
                (self.dir / relative).write_text("existing")
                before = self.snapshot()
                self.assertNotEqual(self.run_stage("certs/make-certs.sh").returncode, 0)
                self.assertEqual(before, self.snapshot())

    def test_interrupted_user_creation_and_missing_existing_users_fail(self):
        self.stage_ok("certs/make-certs.sh")
        (self.dir / "pki/.users-started").touch()
        before = self.snapshot()
        self.assertNotEqual(self.run_stage("setup/make-users.sh").returncode, 0)
        self.assertEqual(before, self.snapshot())

    def test_unexpected_seed_file_blocks_user_creation(self):
        self.stage_ok("certs/make-certs.sh")
        (self.dir / "security/unexpected.yml").write_text("existing")
        before = self.snapshot()
        self.assertNotEqual(self.run_stage("setup/make-users.sh").returncode, 0)
        self.assertEqual(before, self.snapshot())

    def test_missing_and_corrupt_seed_are_not_regenerated(self):
        self.stage_ok("certs/make-certs.sh")
        self.stage_ok("setup/make-users.sh")
        users = self.dir / "security/internal_users.yml"
        users.unlink()
        before = self.snapshot()
        self.assertNotEqual(self.run_stage("certs/make-certs.sh").returncode, 0)
        self.assertNotEqual(self.run_stage("setup/make-users.sh").returncode, 0)
        self.assertEqual(before, self.snapshot())
        users.write_text('admin:\n  hash: "incomplete"\n')
        before = self.snapshot()
        self.assertNotEqual(self.run_stage("certs/make-certs.sh").returncode, 0)
        self.assertNotEqual(self.run_stage("setup/make-users.sh").returncode, 0)
        self.assertEqual(before, self.snapshot())

    def test_complete_legacy_seed_without_markers_is_unchanged(self):
        self.stage_ok("certs/make-certs.sh")
        self.stage_ok("setup/make-users.sh")
        for marker in (".pki-pending", ".users-started", ".users-done"):
            (self.dir / "pki" / marker).unlink()
        before = self.snapshot()
        self.stage_ok("certs/make-certs.sh")
        self.stage_ok("setup/make-users.sh")
        self.assertEqual(before, self.snapshot())

    def test_hash_under_wrong_user_is_rejected(self):
        self.stage_ok("certs/make-certs.sh")
        self.stage_ok("setup/make-users.sh")
        users = self.dir / "security/internal_users.yml"
        lines = users.read_text().splitlines(keepends=True)
        index = next(i for i, line in enumerate(lines) if line == "admin:\n")
        displaced = lines.pop(index + 1)
        lines.append(displaced)
        users.write_text("".join(lines))
        before = self.snapshot()
        self.assertNotEqual(self.run_stage("certs/make-certs.sh").returncode, 0)
        self.assertEqual(before, self.snapshot())

    def test_missing_node_certificate_is_not_recreated(self):
        self.stage_ok("certs/make-certs.sh")
        self.stage_ok("setup/make-users.sh")
        (self.dir / "pki/os-hot.crt").unlink()
        before = self.snapshot()
        self.assertNotEqual(self.run_stage("certs/make-certs.sh").returncode, 0)
        self.assertNotEqual(self.run_stage("setup/make-users.sh").returncode, 0)
        self.assertEqual(before, self.snapshot())

    def test_missing_legacy_users_are_not_recreated(self):
        self.stage_ok("certs/make-certs.sh")
        self.stage_ok("setup/make-users.sh")
        for marker in (".pki-pending", ".users-started", ".users-done"):
            (self.dir / "pki" / marker).unlink()
        (self.dir / "security/internal_users.yml").unlink()
        before = self.snapshot()
        self.assertNotEqual(self.run_stage("certs/make-certs.sh").returncode, 0)
        self.assertNotEqual(self.run_stage("setup/make-users.sh").returncode, 0)
        self.assertEqual(before, self.snapshot())

    def test_inconsistent_markers_fail_closed(self):
        self.stage_ok("certs/make-certs.sh")
        self.stage_ok("setup/make-users.sh")
        (self.dir / "pki/.users-started").unlink()
        before = self.snapshot()
        self.assertNotEqual(self.run_stage("certs/make-certs.sh").returncode, 0)
        self.assertNotEqual(self.run_stage("setup/make-users.sh").returncode, 0)
        self.assertEqual(before, self.snapshot())
