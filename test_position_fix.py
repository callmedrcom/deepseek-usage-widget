"""
Unit tests for window position preservation during compact/expand mode toggling.

These tests verify that:
- _pre_toggle_x / _pre_toggle_y are initialised to None in __init__
- _toggle_compact snapshots winfo_x()/winfo_y() *before* layout changes
- _fit_compact_window uses the saved position (not stale winfo values)
- _fit_window_to_content uses the saved position when expanding
- Both fit functions clear the saved position after consuming it
- Coordinate 0 (top-left corner) is treated as a valid saved position
- Negative x values that would result from naive expansion are clamped to >= 0

Run:
    python -m pytest test_position_fix.py -v
"""
import importlib
import inspect
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# ── helpers ──────────────────────────────────────────────────────────────────

def _install_fake_tkinter():
    """Install minimal stub tkinter modules so widget.py can be imported headlessly."""
    if "tkinter" not in sys.modules:
        fake_tk = types.ModuleType("tkinter")
        for name in (
            "Tk", "Toplevel", "Frame", "Label", "Button",
            "Entry", "Canvas", "Menu", "StringVar", "BooleanVar",
        ):
            setattr(fake_tk, name, type(name, (), {}))
        fake_tk.ttk = types.ModuleType("tkinter.ttk")
        sys.modules["tkinter"] = fake_tk

    if "tkinter.font" not in sys.modules:
        fake_font = types.ModuleType("tkinter.font")
        fake_font.families = lambda: []
        sys.modules["tkinter.font"] = fake_font

    if "tkinter.ttk" not in sys.modules:
        sys.modules["tkinter.ttk"] = types.ModuleType("tkinter.ttk")


def _make_mock_widget(
    *,
    screen_w=1920, screen_h=1080,
    win_x=800, win_y=300,
    win_w=940, win_h=736,
    compact_req_w=380, compact_req_h=36,
    left_req_h=700, right_req_h=700,
    left_req_w=460, right_req_w=460,
    pre_toggle_x=None, pre_toggle_y=None,
    compact_mode=False,
    closing=False,
):
    """Return a MagicMock shaped like DeepSeekWidget for unit-testing position methods."""
    w = MagicMock()
    w._closing = closing
    w._compact_mode = compact_mode
    w._pre_toggle_x = pre_toggle_x
    w._pre_toggle_y = pre_toggle_y

    w.winfo_screenwidth.return_value = screen_w
    w.winfo_screenheight.return_value = screen_h
    w.winfo_x.return_value = win_x
    w.winfo_y.return_value = win_y
    w.winfo_width.return_value = win_w
    w.winfo_height.return_value = win_h

    compact_shell = MagicMock()
    compact_shell.winfo_reqwidth.return_value = compact_req_w
    compact_shell.winfo_reqheight.return_value = compact_req_h
    w._compact_shell = compact_shell

    left_panel = MagicMock()
    left_panel.winfo_reqheight.return_value = left_req_h
    left_panel.winfo_reqwidth.return_value = left_req_w
    right_panel = MagicMock()
    right_panel.winfo_reqheight.return_value = right_req_h
    right_panel.winfo_reqwidth.return_value = right_req_w
    w.left_panel = left_panel
    w.right_panel = right_panel

    return w


def _parse_geometry(geo_str):
    """Parse a geometry string like '940x736+800+300' into (w, h, x, y)."""
    size, _, rest = geo_str.partition("+")
    x_str, _, y_str = rest.partition("+")
    ww, _, hh = size.partition("x")
    return int(ww), int(hh), int(x_str), int(y_str)


# ── test cases ────────────────────────────────────────────────────────────────

class TestPreToggleAttributeInit(unittest.TestCase):
    """_pre_toggle_x / _pre_toggle_y must be initialised to None in __init__."""

    @classmethod
    def setUpClass(cls):
        _install_fake_tkinter()
        cls.wm = importlib.import_module("deepseek_usage_widget.widget")

    def test_init_sets_pre_toggle_x_to_none(self):
        src = inspect.getsource(self.wm.DeepSeekWidget.__init__)
        self.assertIn("_pre_toggle_x", src, "_pre_toggle_x should be set in __init__")
        # Confirm the assignment is '= None'
        for line in src.splitlines():
            if "_pre_toggle_x" in line and "=" in line:
                self.assertIn("None", line,
                              "_pre_toggle_x initialisation should assign None")
                break

    def test_init_sets_pre_toggle_y_to_none(self):
        src = inspect.getsource(self.wm.DeepSeekWidget.__init__)
        self.assertIn("_pre_toggle_y", src, "_pre_toggle_y should be set in __init__")
        for line in src.splitlines():
            if "_pre_toggle_y" in line and "=" in line:
                self.assertIn("None", line,
                              "_pre_toggle_y initialisation should assign None")
                break


class TestFitCompactWindow(unittest.TestCase):
    """Tests for _fit_compact_window position logic."""

    @classmethod
    def setUpClass(cls):
        _install_fake_tkinter()
        cls.wm = importlib.import_module("deepseek_usage_widget.widget")

    def _call(self, mock):
        """Call _fit_compact_window as an unbound function with mock as self."""
        self.wm.DeepSeekWidget._fit_compact_window(mock)

    # -- saved position is used -----------------------------------------------

    def test_uses_saved_position_when_set(self):
        """Compact window should land at the pre-toggle coordinates."""
        mock = _make_mock_widget(
            win_x=500, win_y=200,               # stale / wrong winfo values
            pre_toggle_x=100, pre_toggle_y=50,  # true saved position
        )
        self._call(mock)
        mock.geometry.assert_called_once()
        _, _, x, y = _parse_geometry(mock.geometry.call_args[0][0])
        self.assertEqual(x, 100)
        self.assertEqual(y, 50)

    def test_falls_back_to_winfo_when_no_saved_position(self):
        """Without saved position, winfo_x/y values should be used."""
        mock = _make_mock_widget(win_x=700, win_y=400,
                                 pre_toggle_x=None, pre_toggle_y=None)
        self._call(mock)
        mock.geometry.assert_called_once()
        _, _, x, y = _parse_geometry(mock.geometry.call_args[0][0])
        self.assertEqual(x, 700)
        self.assertEqual(y, 400)

    # -- coordinate 0 is valid ------------------------------------------------

    def test_saved_position_zero_is_valid(self):
        """x=0/y=0 (top-left corner) must NOT fall back to winfo."""
        mock = _make_mock_widget(
            win_x=800, win_y=600,      # would be wrong if used
            pre_toggle_x=0, pre_toggle_y=0,
            screen_w=1920, screen_h=1080,
            compact_req_w=352, compact_req_h=36,
        )
        self._call(mock)
        _, _, x, y = _parse_geometry(mock.geometry.call_args[0][0])
        self.assertEqual(x, 0)
        self.assertEqual(y, 0)

    # -- saved position is cleared --------------------------------------------

    def test_clears_saved_position_after_call(self):
        mock = _make_mock_widget(pre_toggle_x=100, pre_toggle_y=50)
        self._call(mock)
        self.assertIsNone(mock._pre_toggle_x)
        self.assertIsNone(mock._pre_toggle_y)

    def test_clears_saved_position_when_it_was_none(self):
        mock = _make_mock_widget(pre_toggle_x=None, pre_toggle_y=None)
        self._call(mock)
        self.assertIsNone(mock._pre_toggle_x)
        self.assertIsNone(mock._pre_toggle_y)

    # -- closing guard --------------------------------------------------------

    def test_returns_immediately_when_closing(self):
        mock = _make_mock_widget(closing=True)
        self._call(mock)
        mock.geometry.assert_not_called()

    # -- screen clamping ------------------------------------------------------

    def test_saved_position_clamped_to_screen(self):
        """A saved x/y beyond the screen edge must be clamped in."""
        mock = _make_mock_widget(
            screen_w=1920, screen_h=1080,
            pre_toggle_x=1900, pre_toggle_y=1060,
            compact_req_w=352, compact_req_h=36,
        )
        self._call(mock)
        w, h, x, y = _parse_geometry(mock.geometry.call_args[0][0])
        self.assertLessEqual(x + w, 1920)
        self.assertLessEqual(y + h, 1080)


class TestFitWindowToContent(unittest.TestCase):
    """Tests for _fit_window_to_content position logic."""

    @classmethod
    def setUpClass(cls):
        _install_fake_tkinter()
        cls.wm = importlib.import_module("deepseek_usage_widget.widget")

    def _call(self, mock):
        self.wm.DeepSeekWidget._fit_window_to_content(mock)

    def _make_expand_mock(self, **kwargs):
        """Widget in compact-size state (small window) about to expand."""
        defaults = dict(
            win_w=100, win_h=100,   # small/compact dimensions force resize
            win_x=100, win_y=200,
            screen_w=1920, screen_h=1080,
            left_req_h=0, right_req_h=0,
            left_req_w=0, right_req_w=0,
        )
        defaults.update(kwargs)
        return _make_mock_widget(**defaults)

    # -- saved position is used -----------------------------------------------

    def test_uses_saved_position_when_expanding(self):
        """Expanded window restores the pre-toggle x/y."""
        mock = self._make_expand_mock(pre_toggle_x=300, pre_toggle_y=150)
        self._call(mock)
        mock.geometry.assert_called_once()
        _, _, x, y = _parse_geometry(mock.geometry.call_args[0][0])
        self.assertEqual(x, 300)
        self.assertEqual(y, max(10, 150))

    def test_saved_position_zero_is_valid_on_expand(self):
        """x=0 (top-left) must be preserved when expanding."""
        mock = self._make_expand_mock(
            pre_toggle_x=0, pre_toggle_y=0,
            win_x=999, win_y=999,   # live winfo should NOT be used
        )
        self._call(mock)
        _, _, x, _ = _parse_geometry(mock.geometry.call_args[0][0])
        self.assertEqual(x, 0)

    # -- negative x guard -----------------------------------------------------

    def test_no_negative_x_when_no_saved_position(self):
        """Without saved position, x in geometry string must be >= 0."""
        # compact at x=10, expanding from 100 → 940: naive = 10-(940-100) = -830
        mock = self._make_expand_mock(
            win_x=10, win_y=200,
            win_w=100, win_h=100,
            pre_toggle_x=None, pre_toggle_y=None,
        )
        self._call(mock)
        if mock.geometry.called:
            _, _, x, _ = _parse_geometry(mock.geometry.call_args[0][0])
            self.assertGreaterEqual(x, 0)

    # -- saved position is cleared --------------------------------------------

    def test_clears_saved_position_after_expand(self):
        mock = self._make_expand_mock(pre_toggle_x=300, pre_toggle_y=150)
        self._call(mock)
        self.assertIsNone(mock._pre_toggle_x)
        self.assertIsNone(mock._pre_toggle_y)

    # -- closing guard --------------------------------------------------------

    def test_returns_immediately_when_closing(self):
        mock = self._make_expand_mock(closing=True)
        self._call(mock)
        mock.geometry.assert_not_called()

    # -- compact_mode redirect ------------------------------------------------

    def test_redirects_to_fit_compact_when_compact_mode(self):
        """If called while compact_mode is True it must delegate to _fit_compact_window."""
        mock = self._make_expand_mock(compact_mode=True)
        # _fit_window_to_content calls self._fit_compact_window() which, on the
        # MagicMock, resolves to the mock's own auto-attribute – check that.
        self._call(mock)
        mock._fit_compact_window.assert_called_once()
        mock.geometry.assert_not_called()


class TestToggleCompactSavesPosition(unittest.TestCase):
    """_toggle_compact must save position BEFORE any layout mutations."""

    @classmethod
    def setUpClass(cls):
        _install_fake_tkinter()
        cls.wm = importlib.import_module("deepseek_usage_widget.widget")

    def _make_toggle_mock(self, compact_mode=False):
        m = MagicMock()
        m._compact_mode = compact_mode
        m._pre_toggle_x = None
        m._pre_toggle_y = None
        m.config = {}

        # Track call order to verify position is saved before layout changes
        m._call_order = []

        def track_winfo_x():
            m._call_order.append("winfo_x")
            return 350
        def track_winfo_y():
            m._call_order.append("winfo_y")
            return 120

        m.winfo_x.side_effect = track_winfo_x
        m.winfo_y.side_effect = track_winfo_y

        def track_pack_forget():
            m._call_order.append("pack_forget")

        m._main_shell.pack_forget.side_effect = track_pack_forget
        m._compact_shell.pack_forget.side_effect = track_pack_forget
        return m

    def test_position_saved_before_layout_changes_to_compact(self):
        """winfo_x/y must be called before pack_forget when entering compact mode."""
        mock = self._make_toggle_mock(compact_mode=False)
        with patch("deepseek_usage_widget.widget.save_config"):
            self.wm.DeepSeekWidget._toggle_compact(mock)

        order = mock._call_order
        self.assertIn("winfo_x", order)
        self.assertIn("pack_forget", order)
        self.assertLess(order.index("winfo_x"), order.index("pack_forget"),
                        "winfo_x must be called before pack_forget")

    def test_position_saved_before_layout_changes_to_full(self):
        """winfo_x/y must be called before pack_forget when expanding."""
        mock = self._make_toggle_mock(compact_mode=True)
        with patch("deepseek_usage_widget.widget.save_config"):
            self.wm.DeepSeekWidget._toggle_compact(mock)

        order = mock._call_order
        self.assertIn("winfo_x", order)
        self.assertIn("pack_forget", order)
        self.assertLess(order.index("winfo_x"), order.index("pack_forget"),
                        "winfo_x must be called before pack_forget")

    def test_toggle_compact_saves_correct_coordinates(self):
        """Coordinates reported by winfo_x/y must appear in _pre_toggle_x/y."""
        mock = self._make_toggle_mock(compact_mode=False)
        with patch("deepseek_usage_widget.widget.save_config"):
            self.wm.DeepSeekWidget._toggle_compact(mock)
        self.assertEqual(mock._pre_toggle_x, 350)
        self.assertEqual(mock._pre_toggle_y, 120)

    def test_toggle_expand_saves_correct_coordinates(self):
        """Expanding (compact→full) also saves position."""
        mock = self._make_toggle_mock(compact_mode=True)
        with patch("deepseek_usage_widget.widget.save_config"):
            self.wm.DeepSeekWidget._toggle_compact(mock)
        self.assertEqual(mock._pre_toggle_x, 350)
        self.assertEqual(mock._pre_toggle_y, 120)


if __name__ == "__main__":
    unittest.main()
