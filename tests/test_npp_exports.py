"""
G-Coach Notepad++ Plugin Export Verification Tests
Verifies that npp_bridge.cpp contains the mandatory isUnicode() export required by Notepad++ 8.x.
"""

import unittest
import os

class TestNppPluginExports(unittest.TestCase):
    """Test suite verifying mandatory Notepad++ plugin exports in source code."""

    def test_is_unicode_export_present(self):
        cpp_path = os.path.join("plugins", "npp_bridge", "npp_bridge.cpp")
        self.assertTrue(os.path.exists(cpp_path), "npp_bridge.cpp must exist")
        
        with open(cpp_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("isUnicode", content, "npp_bridge.cpp must implement isUnicode()")
        self.assertIn("extern \"C\" __declspec(dllexport) BOOL isUnicode()", content)
        self.assertIn("return TRUE;", content)


if __name__ == "__main__":
    unittest.main()
