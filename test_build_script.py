import unittest
from pathlib import Path


class TestBuildScript(unittest.TestCase):
    def test_pyinstaller_includes_logo_data(self):
        build_bat = Path(__file__).resolve().parent / "build.bat"
        content = build_bat.read_text(encoding="utf-8")
        self.assertIn('--add-data "%~dp0logo.png;."', content)


if __name__ == "__main__":
    unittest.main()
