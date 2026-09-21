"""
Unit tests for Text Capture abstraction and Windows UI Automation capture - Phase 5
"""

import unittest
from core.monitoring import TextSnapshot, MockTextSource, MultiControlMockTextSource, WindowsUIAccessibilityTextSource


class TestTextCapture(unittest.TestCase):
    """测试文本捕获抽象、Mock 文本源、多控件切换与隔离以及 Windows UI Automation 降级处理"""

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

    def test_multi_control_mock_text_source_switching_and_isolation(self):
        """测试多控件切换与隔离（Phase 8A 核心要求）"""
        controls = [
            {
                "control_id": "ctrl-notepad-1",
                "app_name": "notepad.exe",
                "control_type": "DocumentControl",
                "text": "Hello from Notepad",
                "is_editable": True,
            },
            {
                "control_id": "ctrl-word-2",
                "app_name": "WINWORD.EXE",
                "control_type": "DocumentControl",
                "text": "Hello from Word",
                "is_editable": True,
            },
            {
                "control_id": "ctrl-readonly-3",
                "app_name": "calc.exe",
                "control_type": "TextControl",
                "text": "Readonly text",
                "is_editable": False,
            }
        ]
        source = MultiControlMockTextSource(controls)

        # 1. 初始控件 (Notepad)
        snap1 = source.get_current_text()
        self.assertEqual(snap1.control_id, "ctrl-notepad-1")
        self.assertEqual(snap1.app_name, "notepad.exe")
        self.assertEqual(snap1.text, "Hello from Notepad")
        self.assertTrue(snap1.is_editable)
        self.assertEqual(snap1.status, "ready")

        # 2. 切换到第二个控件 (Word)
        source.select_control(1)
        snap2 = source.get_current_text()
        self.assertEqual(snap2.control_id, "ctrl-word-2")
        self.assertEqual(snap2.app_name, "WINWORD.EXE")
        self.assertEqual(snap2.text, "Hello from Word")
        self.assertNotEqual(snap2.text, snap1.text)

        # 3. 切换到不可编辑控件 (Readonly)
        source.select_control(2)
        snap3 = source.get_current_text()
        self.assertEqual(snap3.control_id, "ctrl-readonly-3")
        self.assertFalse(snap3.is_editable)
        self.assertEqual(snap3.status, "unsupported")

    def test_identical_text_different_controls_distinguishable(self):
        """测试两个不同控件拥有完全相同的文本时，依然可通过 control_id 严格区分"""
        controls = [
            {"control_id": "ctrl-app-A", "app_name": "AppA", "text": "Same text", "is_editable": True},
            {"control_id": "ctrl-app-B", "app_name": "AppB", "text": "Same text", "is_editable": True},
        ]
        source = MultiControlMockTextSource(controls)
        
        snap_a = source.get_current_text()
        source.select_control(1)
        snap_b = source.get_current_text()

        self.assertEqual(snap_a.text, snap_b.text)
        self.assertNotEqual(snap_a.control_id, snap_b.control_id)
        self.assertNotEqual(snap_a.app_name, snap_b.app_name)

    def test_windows_uia_text_source_non_windows_fallback(self):
        source = WindowsUIAccessibilityTextSource()
        snapshot = source.get_current_text()
        import platform
        if platform.system() != "Windows":
            self.assertEqual(snapshot.status, "unsupported")
            self.assertIsNotNone(snapshot.error_message)


if __name__ == "__main__":
    unittest.main()
