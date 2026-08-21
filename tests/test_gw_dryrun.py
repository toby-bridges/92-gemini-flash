import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GW = str(Path(__file__).resolve().parent.parent / "skills" / "gemini-writer" / "scripts" / "gw.py")


def run_gw(args, env_overrides):
    """在受控环境跑 gw.py：HOME 指向空临时目录（无 CLI 凭据），PATH 只留 python 所在目录（找不到 gemini）。"""
    with tempfile.TemporaryDirectory() as fake_home:
        env = {
            "HOME": fake_home,
            "PATH": str(Path(sys.executable).parent),
            "LC_ALL": "C.UTF-8",
            "LANG": "C.UTF-8",
        }
        env.update(env_overrides)
        return subprocess.run(
            [sys.executable, GW, *args], capture_output=True, text=True, env=env, timeout=30
        )


class TestDryRun(unittest.TestCase):
    def test_no_backend_available_exits_1_with_both_fixes(self):
        r = run_gw(["写一段话", "--dry-run"], {})
        self.assertEqual(r.returncode, 1)
        self.assertIn("brew install --cask antigravity-cli", r.stderr)
        self.assertIn("aistudio.google.com/apikey", r.stderr)

    def test_key_present_selects_api(self):
        r = run_gw(["写一段话", "--dry-run"], {"GEMINI_API_KEY": "fake-key"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("dry-run backend=api", r.stdout)
        self.assertIn("model=gemini-3.7-flash", r.stdout)

    def test_forced_cli_without_cli_fails(self):
        r = run_gw(["写一段话", "--dry-run", "--backend", "cli"], {"GEMINI_API_KEY": "fake-key"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("Antigravity CLI", r.stderr)

    def test_env_gw_backend_api_wins_over_auto(self):
        r = run_gw(["写一段话", "--dry-run"], {"GEMINI_API_KEY": "fake-key", "GW_BACKEND": "api"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("dry-run backend=api", r.stdout)

    def test_timeout_clamped_in_dryrun_output(self):
        r = run_gw(["写一段话", "--dry-run", "--timeout", "9999"], {"GEMINI_API_KEY": "fake-key"})
        self.assertIn("timeout=600", r.stdout)

    def test_context_file_counted(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("素材内容")
            fname = f.name
        try:
            r = run_gw(["写一段话", "--dry-run", "--context", fname], {"GEMINI_API_KEY": "fake-key"})
            self.assertIn("context_files=1", r.stdout)
        finally:
            os.unlink(fname)

    def test_missing_context_file_errors(self):
        r = run_gw(["写", "--dry-run", "--context", "/nonexistent/素材.md"], {"GEMINI_API_KEY": "fake-key"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("素材文件不存在", r.stderr)


if __name__ == "__main__":
    unittest.main()
