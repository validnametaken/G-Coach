"""
G-Coach Notepad++ Integration Tests
Tests Notepad++ correction routing and clipboard-based fallback replacement.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from core.analysis import Finding
from core.correction.target import CorrectionTarget
from core.correction.npp_adapter import NppCorrectionAdapter
from core.correction.engine import BackgroundCorrectionEngine


class TestNppCorrectionIntegration(unittest.TestCase):
    """Test suite for Notepad++ correction handling."""

    def test_is_notepad_target(self):
        target = CorrectionTarget(hwnd=100, app_name="notepad++.exe", original_text="test")
        self.assertTrue(NppCorrectionAdapter.is_notepad_target(target))

        target_lower = CorrectionTarget(hwnd=100, app_name="Notepad++", original_text="test")
        self.assertTrue(NppCorrectionAdapter.is_notepad_target(target_lower))

        other_target = CorrectionTarget(hwnd=100, app_name="wordcraft.exe", original_text="test")
        self.assertFalse(NppCorrectionAdapter.is_notepad_target(other_target))

    @patch("core.correction.npp_adapter.NppCorrectionAdapter.apply_bridge_correction")
    @patch("core.correction.engine.BackgroundCorrectionEngine._get_focused_target_element")
    @patch("core.correction.engine.BackgroundCorrectionEngine._read_text_pattern")
    @patch("core.correction.engine.BackgroundCorrectionEngine._build_exact_range")
    @patch("platform.system", return_value="Windows")
    def test_engine_routes_notepad_target(self, mock_sys, mock_build_range, mock_read_pattern, mock_get_element, mock_apply_bridge):
        mock_apply_bridge.return_value = True
        mock_get_element.return_value = MagicMock()
        text_range_mock = MagicMock()
        text_range_mock.GetText.return_value = "a"
        pattern_mock = MagicMock()
        selected_range_mock = MagicMock()
        selected_range_mock.GetText.return_value = "a"
        pattern_mock.GetSelection.return_value = [selected_range_mock]
        mock_read_pattern.return_value = (pattern_mock, text_range_mock, "a")
        mock_build_range.return_value = text_range_mock
        target = CorrectionTarget(hwnd=100, app_name="notepad++.exe", original_text="a")
        finding = Finding(source="harper", category="test", message="test", original="a", replacement="b", start=0, end=1)

        success = BackgroundCorrectionEngine.apply_correction_to_target(target, finding)
        self.assertTrue(success)
        mock_apply_bridge.assert_called_once_with(target, finding)


if __name__ == "__main__":
    unittest.main()
