"""
Unit tests for Text Capture abstraction and Windows UI Automation capture - Phase 5
"""

import unittest
from core.monitoring import TextSnapshot, MockTextSource, WindowsUIAccessibilityTextSource


class TestTextCapture(unittest.TestCase):
    """测试文本捕获抽象、Mock 文本源以及 Windows UI Automation 降级处理"""

    def test_text_snapshot_defaults(self):
        snapshot = TextSnapshot(text="Hello", generation=1)
        self.assertEqual(snapshot.text, "Hello")
        self.assertEqual(snapshot.generation, 1)
        self.assertEqual(snapshot.status, "idle")

    def test_mock_text_source(self):
        source = MockTextSource(initial_text="Initial text")
        snapshot1 = source.get_current_text()
        self.assertEqual(snapshot1.text, "Initial text")
        self.assertEqual(snapshot1.status, "ready")

        source.set_text("Updated text")
        snapshot2 = source.get_current_text()
        self.assertEqual(snapshot2.text, "Updated text")
        self.assertEqual(snapshot2.generation, 1)

    def test_windows_uia_text_source_non_windows_fallback(self):
        # 在非 Windows 环境下应当优雅地返回 unsupported 状态
        source = WindowsUIAccessibilityTextSource()
        snapshot = source.get_current_text()
        # 如果是在 Linux/macOS 容器中，status 应为 unsupported
        import platform
        if platform.system() != "Windows":
            self.assertEqual(snapshot.status, "unsupported")
            self.assertIsNotNone(snapshot.error_message)


if __name__ == "__main__":
    unittest.main()
