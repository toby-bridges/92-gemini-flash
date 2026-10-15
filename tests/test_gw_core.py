import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "gemini-writer" / "scripts"))
import gw


class TestSelectBackend(unittest.TestCase):
    def test_auto_prefers_cli_when_both_available(self):
        self.assertEqual(gw.select_backend(None, None, True, True), ("cli", None))

    def test_auto_falls_to_api_when_cli_missing(self):
        self.assertEqual(gw.select_backend("auto", None, False, True), ("api", None))

    def test_auto_errors_when_nothing_available(self):
        backend, err = gw.select_backend(None, None, False, False)
        self.assertIsNone(backend)
        self.assertIn("brew install --cask antigravity-cli", err)
        self.assertIn("aistudio.google.com/apikey", err)

    def test_env_var_overrides_auto(self):
        self.assertEqual(gw.select_backend("auto", "api", True, True), ("api", None))

    def test_explicit_flag_beats_env(self):
        self.assertEqual(gw.select_backend("cli", "api", True, True), ("cli", None))

    def test_forced_cli_unavailable_errors_with_fix(self):
        backend, err = gw.select_backend("cli", None, False, True)
        self.assertIsNone(backend)
        self.assertIn("brew install --cask antigravity-cli", err)

    def test_forced_api_without_key_errors_with_fix(self):
        backend, err = gw.select_backend("api", None, True, False)
        self.assertIsNone(backend)
        self.assertIn("GEMINI_API_KEY", err)


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
    def test_cli_default_gets_thinking_suffix(self):
        self.assertEqual(gw.resolve_model(None, "cli"), "gemini-3.8-flash-medium")

    def test_api_default_plain(self):
        self.assertEqual(gw.resolve_model(None, "api"), "gemini-3.7-flash")

    def test_explicit_model_passthrough(self):
        self.assertEqual(gw.resolve_model("gemini-3.7-flash-high", "cli"), "gemini-3.7-flash-high")


class TestClampTimeout(unittest.TestCase):
    def test_default_passthrough(self):
        self.assertEqual(gw.clamp_timeout(300), 300)

    def test_caps_at_600(self):
        self.assertEqual(gw.clamp_timeout(9999), 600)

    def test_floor_at_1(self):
        self.assertEqual(gw.clamp_timeout(0), 1)


if __name__ == "__main__":
    unittest.main()
