import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GW = str(Path(__file__).resolve().parent.parent / "skills" / "gemini-writer" / "scripts" / "gw.py")


def run_gw(args, env_overrides=None, agy=True):
    """在受控环境跑 gw.py：HOME 指向空临时目录，agy=True 时放一个假 agy 和登录痕迹。"""
    with tempfile.TemporaryDirectory() as fake_home:
        bin_dir = Path(fake_home) / "bin"
        bin_dir.mkdir()
        if agy:
            (bin_dir / "agy").write_text("#!/bin/sh\n")
            (bin_dir / "agy").chmod(0o755)
            (Path(fake_home) / ".gemini" / "antigravity-cli").mkdir(parents=True)
        env = {
            "HOME": fake_home,
            "PATH": f"{bin_dir}:{Path(sys.executable).parent}",
            "LC_ALL": "C.UTF-8",
            "LANG": "C.UTF-8",
        }
        env.update(env_overrides or {})
        return subprocess.run(
            [sys.executable, GW, *args], capture_output=True, text=True, env=env, timeout=30
        )


class TestDryRun(unittest.TestCase):
    def test_agy_unavailable_exits_1_with_fix(self):
        r = run_gw(["写一段话", "--dry-run"], agy=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("brew install --cask antigravity-cli", r.stderr)

    def test_api_key_alone_is_not_a_channel(self):
        r = run_gw(["写一段话", "--dry-run"], {"GEMINI_API_KEY": "fake-key"}, agy=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Antigravity CLI", r.stderr)

    def test_old_backend_cli_flag_still_works(self):
        # Codex 的历史调用里常带 --backend cli
        r = run_gw(["写一段话", "--dry-run", "--backend", "cli"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("backend=cli", r.stdout)

    def test_api_backend_is_rejected(self):
        r = run_gw(["写一段话", "--dry-run", "--backend", "api"])
        self.assertEqual(r.returncode, 2)

    def test_default_is_flash_at_high(self):
        r = run_gw(["写一段话", "--dry-run"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("model=gemini-3.8-flash-high ", r.stdout)

    def test_argon_alias(self):
        r = run_gw(["写一段话", "--dry-run", "--model", "argon"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("model=gemini-4-argon-high ", r.stdout)

    def test_default_timeout_leaves_room_for_argon(self):
        # Argon high 写长文实测 225 秒到 300 秒以上，300 秒不够余量
        r = run_gw(["写一段话", "--dry-run", "--model", "argon"])
        self.assertIn("timeout=600", r.stdout)

    def test_timeout_clamped_in_dryrun_output(self):
        r = run_gw(["写一段话", "--dry-run", "--timeout", "9999"])
        self.assertIn("timeout=600", r.stdout)

    def test_context_file_counted(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("素材内容")
            fname = f.name
        try:
            r = run_gw(["写一段话", "--dry-run", "--context", fname])
            self.assertIn("context_files=1", r.stdout)
        finally:
            os.unlink(fname)

    def test_missing_context_file_errors(self):
        r = run_gw(["写", "--dry-run", "--context", "/nonexistent/素材.md"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("素材文件不存在", r.stderr)


if __name__ == "__main__":
    unittest.main()
