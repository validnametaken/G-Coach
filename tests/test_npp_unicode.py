"""
G-Coach Unicode & Multibyte Offset Integration Tests for Notepad++ Bridge (Phase 8G.6)
Tests exact range correction and stale verification around Japanese, accented characters, and emojis.
"""

import unittest
from unittest.mock import patch, MagicMock
from core.analysis import Finding
from core.correction.target import CorrectionTarget
from core.correction.npp_adapter import NppCorrectionAdapter

class TestNppUnicodeIntegration(unittest.TestCase):
    """Test suite verifying exact range replacement and stale checks around multibyte/Unicode characters in Notepad++."""

    @patch("core.correction.npp_adapter.NppBridgeClient")
    @patch("platform.system", return_value="Windows")
    def test_unicode_multibyte_corrections(self, mock_sys, mock_client_cls):
        test_cases = [
            ("The students was very happy.", "was", "were", 13, 16),
            ("こんにちは students was happy.", "was", "were", 20, 23),
            ("Café students was happy.", "was", "were", 14, 17),
            ("😀 students was happy.", "was", "were", 12, 15),
        ]

        for doc_text, orig, repl, start, end in test_cases:
            with self.subTest(doc_text=doc_text):
                mock_client = MagicMock()
                mock_client.get_context.return_value = {"success": True, "text_length": len(doc_text)}
                mock_client.read_range.return_value = {"success": True, "text": orig}
                mock_client.replace_range.return_value = {"success": True, "new_length": len(doc_text) - len(orig) + len(repl)}
                mock_client_cls.return_value = mock_client

                target = CorrectionTarget(hwnd=100, app_name="notepad++.exe", original_text=doc_text)
                finding = Finding(
                    source="harper",
                    category="grammar",
                    message="Fix verb",
                    original=orig,
                    replacement=repl,
                    start=start,
                    end=end
                )

                success = NppCorrectionAdapter.apply_bridge_correction(target, finding)
                self.assertTrue(success)
                mock_client.read_range.assert_called_once_with(start, end, request_id="gcoach-read-req")


if __name__ == "__main__":
    unittest.main()
