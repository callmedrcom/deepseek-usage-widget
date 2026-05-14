import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def _install_fake_tkinter():
    if "tkinter" not in sys.modules:
        fake_tk = types.ModuleType("tkinter")
        for name in (
            "Tk", "Toplevel", "Frame", "Label", "Button",
            "Entry", "Canvas", "Menu", "StringVar", "BooleanVar",
        ):
            setattr(fake_tk, name, type(name, (), {}))
        fake_tk.ttk = types.ModuleType("ttk")
        sys.modules["tkinter"] = fake_tk

    if "tkinter.font" not in sys.modules:
        fake_font = types.ModuleType("tkinter.font")
        fake_font.families = lambda: []
        sys.modules["tkinter.font"] = fake_font


class TestLogoCandidatePaths(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _install_fake_tkinter()
        cls.widget = importlib.import_module("deepseek_usage_widget.widget")

    def test_candidates_include_pyinstaller_temp_path(self):
        with patch.object(self.widget.sys, "_MEIPASS", "/tmp/fake_meipass", create=True):
            candidates = self.widget._brand_logo_candidates()
        self.assertIn(Path("/tmp/fake_meipass/logo.png"), candidates)

    def test_candidates_start_from_config_logo(self):
        candidates = self.widget._brand_logo_candidates()
        self.assertEqual(candidates[0], self.widget.LOGO_FILE)


if __name__ == "__main__":
    unittest.main()
