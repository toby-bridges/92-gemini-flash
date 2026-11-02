import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "gemini-writer" / "scripts"))
import gw


class TestBuildPrompt(unittest.TestCase):
    def test_contains_brief_and_no_tools_instruction(self):
        p = gw.build_prompt("写一篇关于猫的散文", [])
        self.assertIn("写一篇关于猫的散文", p)
        self.assertIn("不要使用任何工具", p)
        self.assertIn("只输出正文", p)

    def test_context_files_are_embedded_with_filenames(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            f1 = os.path.join(d, "素材A.md")
            Path(f1).write_text("猫有九条命的传说", encoding="utf-8")
            p = gw.build_prompt("写猫", [f1])
            self.assertIn("素材A.md", p)
            self.assertIn("猫有九条命的传说", p)


class TestResolveModel(unittest.TestCase):
    def test_default_is_flash_at_high(self):
        self.assertEqual(gw.resolve_model(None), "gemini-3.8-flash-high")

    def test_argon_alias(self):
        self.assertEqual(gw.resolve_model("argon"), "gemini-4-argon-high")

    def test_builtin_base_name_gets_default_thinking(self):
        # 基础名直传 agy 会落到服务端默认的 medium
        self.assertEqual(gw.resolve_model("gemini-4-argon"), "gemini-4-argon-high")

    def test_explicit_model_passthrough(self):
        self.assertEqual(gw.resolve_model("gemini-4-argon-medium"), "gemini-4-argon-medium")


class TestRunCli(unittest.TestCase):
    OK = json.dumps({"status": "SUCCESS", "response": "正文"})

    def test_pins_model_by_slug(self):
        done = subprocess.CompletedProcess([], 0, stdout=self.OK, stderr="")
        with mock.patch.object(gw.subprocess, "run", return_value=done) as run:
            self.assertEqual(gw.run_cli("p", "gemini-4-argon-high", 5), ("正文", "gemini-4-argon-high"))
        cmd = run.call_args[0][0]
        self.assertEqual(cmd[cmd.index("--model") + 1], "gemini-4-argon-high")
        self.assertNotIn("--effort", cmd)

    def test_fallback_keeps_default_thinking(self):
        failed = subprocess.CompletedProcess([], 1, stdout="", stderr="unknown model")
        done = subprocess.CompletedProcess([], 0, stdout=self.OK, stderr="")
        with mock.patch.object(gw.subprocess, "run", side_effect=[failed, done]) as run:
            self.assertEqual(gw.run_cli("p", "gone-model", 5), ("正文", "agy-default(unknown)"))
        cmd = run.call_args[0][0]
        self.assertNotIn("--model", cmd)
        self.assertEqual(cmd[cmd.index("--effort") + 1], "high")

    def test_never_hands_api_key_to_agy(self):
        # agy 支持 GEMINI_API_KEY 会话，这里保证只走会员 OAuth
        done = subprocess.CompletedProcess([], 0, stdout=self.OK, stderr="")
        with mock.patch.dict(gw.os.environ, {"GEMINI_API_KEY": "fake-key", "HOME": "/fake-home"}), \
                mock.patch.object(gw.subprocess, "run", return_value=done) as run:
            gw.run_cli("p", "gemini-3.8-flash-high", 5)
        env = run.call_args.kwargs["env"]
        self.assertNotIn("GEMINI_API_KEY", env)
        self.assertEqual(env["HOME"], "/fake-home")

    def test_sandbox_failure_points_at_escalation(self):
        # Codex 沙箱不让 agy 写日志，修复建议不能是重装
        failed = subprocess.CompletedProcess([], 1, stdout="", stderr="open cli.log: operation not permitted")
        with mock.patch.object(gw.subprocess, "run", return_value=failed), \
                mock.patch("sys.stderr", new=io.StringIO()) as err, \
                self.assertRaises(SystemExit):
            gw.run_cli("p", "gemini-3.8-flash-high", 5)
        self.assertIn("require_escalated", err.getvalue())
        self.assertNotIn("brew install", err.getvalue())

    def test_other_failure_keeps_install_fix(self):
        failed = subprocess.CompletedProcess([], 1, stdout="", stderr="not logged in")
        with mock.patch.object(gw.subprocess, "run", return_value=failed), \
                mock.patch("sys.stderr", new=io.StringIO()) as err, \
                self.assertRaises(SystemExit):
            gw.run_cli("p", "gemini-3.8-flash-high", 5)
        self.assertIn("brew install", err.getvalue())


class TestClampTimeout(unittest.TestCase):
    def test_default_passthrough(self):
        self.assertEqual(gw.clamp_timeout(300), 300)

    def test_caps_at_600(self):
        self.assertEqual(gw.clamp_timeout(9999), 600)

    def test_floor_at_1(self):
        self.assertEqual(gw.clamp_timeout(0), 1)


if __name__ == "__main__":
    unittest.main()
