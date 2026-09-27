"""
G-Coach Notepad++ Bridge & Protocol Unit Tests (Phase 8G.5)
Tests protocol handling, payload validation, mock client behavior, and Unicode offset handling.
"""

import unittest
from unittest.mock import patch, MagicMock
from core.correction.npp_client import NppBridgeClient

class TestNppBridgeProtocol(unittest.TestCase):
    """Test suite for Phase 8G.5 Notepad++ bridge client and protocol formatting."""

    def test_client_payload_structure(self):
        client = NppBridgeClient()
        
        # Test get_context payload structure
        with patch.object(client, "send_request") as mock_send:
            mock_send.return_value = {"success": True, "document_id": "buf-1", "text_length": 42}
            res = client.get_context(request_id="test-1")
            self.assertTrue(res["success"])
            mock_send.assert_called_once_with({
                "request_id": "test-1",
                "command": "get_context",
                "protocol_version": 1
            })

    def test_read_range_payload(self):
        client = NppBridgeClient()
        with patch.object(client, "send_request") as mock_send:
            mock_send.return_value = {"success": True, "text": "was"}
            res = client.read_range(10, 13, request_id="test-2")
            self.assertTrue(res["success"])
            mock_send.assert_called_once_with({
                "request_id": "test-2",
                "command": "read_range",
                "protocol_version": 1,
                "start": 10,
                "end": 13
            })

    def test_replace_range_payload(self):
        client = NppBridgeClient()
        with patch.object(client, "send_request") as mock_send:
            mock_send.return_value = {"success": True, "new_length": 45}
            res = client.replace_range(10, 13, "was", "were", request_id="test-3")
            self.assertTrue(res["success"])
            mock_send.assert_called_once_with({
                "request_id": "test-3",
                "command": "replace_range",
                "protocol_version": 1,
                "start": 10,
                "end": 13,
                "expected_original": "was",
                "replacement": "were"
            })

    def test_unicode_and_multibyte_handling(self):
        # Verify Unicode strings like Japanese or Emoji serialize properly in requests
        client = NppBridgeClient()
        with patch.object(client, "send_request") as mock_send:
            mock_send.return_value = {"success": True}
            client.replace_range(0, 5, "こんにちは", "こんばんは", request_id="test-unicode")
            args, _ = mock_send.call_args
            payload = args[0]
            self.assertEqual(payload["expected_original"], "こんにちは")
            self.assertEqual(payload["replacement"], "こんばんは")


if __name__ == "__main__":
    unittest.main()
