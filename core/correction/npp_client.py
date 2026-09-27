"""
G-Coach Notepad++ Bridge Python Client & Test Harness (Phase 8G.5)
Provides a clean Python interface to communicate with the G-Coach Notepad++ C++ plugin bridge via Named Pipes.
"""

import json
import os
import platform
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class NppBridgeClient:
    """G-Coach Notepad++ Named Pipe Client"""

    def __init__(self, pipe_name: str = r"\\.\pipe\gcoach_npp_bridge_session"):
        self.pipe_name = pipe_name
        self._is_windows = platform.system() == "Windows"

    def send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON request to the Notepad++ bridge plugin via Windows Named Pipe."""
        if not self._is_windows:
            return {"success": False, "error": "NPP Bridge named pipes are only available on Windows."}

        try:
            import win32file
            import win32pipe
            import pywintypes

            # Open named pipe connection
            handle = win32file.CreateFile(
                self.pipe_name,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )

            # Set message mode
            win32pipe.SetNamedPipeHandleState(
                handle,
                win32pipe.PIPE_READMODE_MESSAGE,
                None,
                None
            )

            req_bytes = json.dumps(payload).encode("utf-8")
            win32file.WriteFile(handle, req_bytes)

            _, resp_bytes = win32file.ReadFile(handle, 4096)
            win32file.CloseHandle(handle)

            return json.loads(resp_bytes.decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to communicate with Notepad++ bridge plugin: {e}")
            return {"success": False, "error": str(e)}

    def get_context(self, request_id: str = "req-ctx-1") -> Dict[str, Any]:
        """Request active document context from Notepad++."""
        return self.send_request({
            "request_id": request_id,
            "command": "get_context",
            "protocol_version": 1
        })

    def read_range(self, start: int, end: int, request_id: str = "req-read-1") -> Dict[str, Any]:
        """Read exact range [start:end] from active document."""
        return self.send_request({
            "request_id": request_id,
            "command": "read_range",
            "protocol_version": 1,
            "start": start,
            "end": end
        })

    def replace_range(self, start: int, end: int, expected_original: str, replacement: str, request_id: str = "req-rep-1") -> Dict[str, Any]:
        """Perform verified exact-range replacement with stale check."""
        return self.send_request({
            "request_id": request_id,
            "command": "replace_range",
            "protocol_version": 1,
            "start": start,
            "end": end,
            "expected_original": expected_original,
            "replacement": replacement
        })
