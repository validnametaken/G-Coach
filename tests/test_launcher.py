"""Tests for the G-Coach command-line launcher."""

import contextlib
import io
import unittest
from unittest.mock import patch

import gcoach


class TestLauncher(unittest.TestCase):
    def test_help_exits_cleanly_without_launching_ui(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                gcoach.main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("--log-level", output.getvalue())

    def test_main_returns_desktop_exit_code(self):
        with patch("core.ui.window.main", return_value=7) as run_desktop_app:
            self.assertEqual(gcoach.main(["--log-level", "debug"]), 7)

        run_desktop_app.assert_called_once_with()

    def test_startup_error_returns_nonzero(self):
        with patch("core.ui.window.main", side_effect=RuntimeError("startup failed")):
            self.assertEqual(gcoach.main([]), 1)


if __name__ == "__main__":
    unittest.main()
