"""
G-Coach Phase 8G.6 NPP Correction Integration Unit Tests
Tests NppCorrectionAdapter routing, stale rejection, bridge communication, and application separation.
"""

import unittest
from unittest.mock import patch, MagicMock
from core.analysis import Finding
from core.correction.target import CorrectionTarget
from core.correction.npp_adapter import NppCorrectionAdapter
from core.correction.engine import BackgroundCorrectionEngine

class TestNppCorrectionIntegration(unittest.TestCase):
    """Test suite for Phase 8G.6 Notepad++ bridge integration into BackgroundCorrectionEngine."""

    def test_is_notepad_target(self):
        t_npp = CorrectionTarget(hwnd=123, app_name="notepad++.exe", original_text="test")
        t_npp_cap = CorrectionTarget(hwnd=123, app_name="Notepad++.exe", original_text="test")
        t_tg = CorrectionTarget(hwnd=456, app_name="Telegram.exe", original_text="test")
        t_ff = CorrectionTarget(hwnd=789, app_name="firefox.exe", original_text="test")

        self.assertTrue(NppCorrectionAdapter.is_notepad_target(t_npp))
        self.assertTrue(NppCorrectionAdapter.is_notepad_target(t_npp_cap))
        self.assertFalse(NppCorrectionAdapter.is_notepad_target(t_tg))
        self.assertFalse(NppCorrectionAdapter.is_notepad_target(t_ff))

    @patch("core.correction.npp_adapter.NppBridgeClient")
    @patch("platform.system", return_value="Windows")
    def test_apply_bridge_correction_success(self, mock_sys, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get_context.return_value = {"success": True, "text_length": 30}
        mock_client.read_range.return_value = {"success": True, "text": "was"}
        mock_client.replace_range.return_value = {"success": True, "new_length": 31}
        mock_client_cls.return_value = mock_client

        target = CorrectionTarget(hwnd=100, app_name="notepad++.exe", original_text="The students was happy.")
        finding = Finding(
            source="harper",
            category="grammar",
            message="Fix verb",
            original="was",
            replacement="were",
            start=13,
            end=16
        )

        success = NppCorrectionAdapter.apply_bridge_correction(target, finding)
        self.assertTrue(success)
        mock_client.get_context.assert_called_once()
        mock_client.read_range.assert_called_once_with(13, 16, request_id="gcoach-read-req")
        mock_client.replace_range.assert_called_once()

    @patch("core.correction.npp_adapter.NppBridgeClient")
    @patch("platform.system", return_value="Windows")
    def test_apply_bridge_correction_stale_rejection(self, mock_sys, mock_client_cls):
        mock_client = MagicMock()
        mock_client.get_context.return_value = {"success": True, "text_length": 30}
        mock_client.read_range.return_value = {"success": True, "text": "were"} # already changed
        mock_client_cls.return_value = mock_client

        target = CorrectionTarget(hwnd=100, app_name="notepad++.exe", original_text="The students was happy.")
        finding = Finding(
            source="harper",
            category="grammar",
            message="Fix verb",
            original="was",
            replacement="were",
            start=13,
            end=16
        )

        success = NppCorrectionAdapter.apply_bridge_correction(target, finding)
        self.assertFalse(success)
        mock_client.replace_range.assert_not_called()

    @patch("core.correction.npp_adapter.NppCorrectionAdapter.apply_bridge_correction")
    def test_engine_routes_notepad_target(self, mock_apply_bridge):
        mock_apply_bridge.return_value = True
        target = CorrectionTarget(hwnd=100, app_name="notepad++.exe", original_text="test")
        finding = Finding(source="harper", category="test", message="test", original="a", replacement="b", start=0, end=1)

        success = BackgroundCorrectionEngine.apply_correction_to_target(target, finding)
        self.assertTrue(success)
        mock_apply_bridge.assert_called_once_with(target, finding)


if __name__ == "__main__":
    unittest.main()
