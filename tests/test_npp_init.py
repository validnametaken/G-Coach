"""
G-Coach Notepad++ Plugin Initialization Tests
Verifies that npp_bridge.cpp contains setInfo starting the server and no longer relies on NPPN_READY.
"""

import unittest
import os

class TestNppPluginInitialization(unittest.TestCase):
    """Test suite verifying plugin initialization architecture in npp_bridge.cpp."""

    def test_setInfo_starts_server_and_no_nppn_ready(self):
        cpp_path = os.path.join("plugins", "npp_bridge", "npp_bridge.cpp")
        self.assertTrue(os.path.exists(cpp_path))
        
        with open(cpp_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Verify setInfo calls StartNamedPipeServer
        self.assertIn("void setInfo(NPP_DATA notepadData)", content)
        self.assertIn("StartNamedPipeServer();", content)
        
        # Verify NPPN_READY constant definition is removed or no longer handled in beNotified
        self.assertNotIn("notification->nmhdr.code == NPPN_READY", content)


if __name__ == "__main__":
    unittest.main()
