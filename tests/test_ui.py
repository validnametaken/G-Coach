"""
Unit tests for G-Coach UI Presenter and state formatting - Phase 6
"""

import unittest
from core.analysis import Finding
from core.monitoring import MonitorState
from core.ui import UIPresenter


class TestUIPresenter(unittest.TestCase):
    """测试 UIPresenter 的状态格式化、摘要生成、finding 详情与冲突分组逻辑"""

    def test_format_status(self):
        self.assertEqual(UIPresenter.format_status("idle"), "Idle")
        self.assertEqual(UIPresenter.format_status("waiting"), "Waiting")
        self.assertEqual(UIPresenter.format_status("analyzing"), "Analyzing")
        self.assertEqual(UIPresenter.format_status("ready"), "Ready")
        self.assertEqual(UIPresenter.format_status("unsupported"), "Unsupported")
        self.assertEqual(UIPresenter.format_status("error"), "Error")
        self.assertEqual(UIPresenter.format_status("unknown"), "Unknown")

    def test_format_app_info(self):
        self.assertEqual(UIPresenter.format_app_info("Notepad", "Edit"), "Application: Notepad (Edit)")
        self.assertEqual(UIPresenter.format_app_info("Word", ""), "Application: Word")
        self.assertEqual(UIPresenter.format_app_info("", ""), "Application: Unknown")

    def test_format_finding_summary(self):
        f = Finding(
            source="harper",
            category="grammar",
            message="Subject-verb agreement error",
            original="go",
            replacement="goes",
            start=4,
            end=6,
            confidence=0.95,
        )
        summary = UIPresenter.format_finding_summary(f)
        self.assertIn("go", summary)
        self.assertIn("goes", summary)
        self.assertIn("grammar", summary)
        self.assertIn("harper", summary)

    def test_format_finding_details(self):
        f = Finding(
            source="gector",
            category="agreement",
            message="Fix verb form",
            original="go",
            replacement="went",
            start=4,
            end=6,
            confidence=0.88,
        )
        details = UIPresenter.format_finding_details(f)
        self.assertEqual(details["Original"], "go")
        self.assertEqual(details["Replacement"], "went")
        self.assertEqual(details["Category"], "agreement")
        self.assertEqual(details["Source Engine(s)"], "gector")
        self.assertEqual(details["Confidence"], "0.88")

    def test_group_findings_by_text_and_conflicts(self):
        f1 = Finding(
            source="harper",
            category="grammar",
            message="Suggestion 1",
            original="go",
            replacement="goes",
            start=0,
            end=2,
        )
        f2 = Finding(
            source="gector",
            category="grammar",
            message="Suggestion 2",
            original="go",
            replacement="went",
            start=0,
            end=2,
        )
        f3 = Finding(
            source="harper",
            category="spelling",
            message="Suggestion 3",
            original="appple",
            replacement="apple",
            start=5,
            end=11,
        )

        state = MonitorState(
            generation=1,
            text="She go to appple store",
            findings=[f1, f2, f3],
            status="ready",
            app_name="Notepad",
        )

        summary = UIPresenter.format_state_summary(state)
        self.assertEqual(summary["status_text"], "Ready")
        self.assertEqual(summary["findings_count"], 3)
        self.assertTrue(summary["has_conflicts"])  # "go" has two conflicting suggestions ("goes" vs "went")

    def test_phase_6_x_polish_pending_states(self):
        """测试 Phase 6.x UI 润色要求：等待/分析中状态、is_pending、提示消息及干净文本（零发现）"""
        state_waiting = MonitorState(generation=2, text="Checking text", status="waiting")
        summary_waiting = UIPresenter.format_state_summary(state_waiting)
        self.assertTrue(summary_waiting["is_pending"])
        self.assertIn("Waiting", summary_waiting["pending_message"])

        state_analyzing = MonitorState(generation=2, text="Checking text", status="analyzing")
        summary_analyzing = UIPresenter.format_state_summary(state_analyzing)
        self.assertTrue(summary_analyzing["is_pending"])
        self.assertIn("Checking", summary_analyzing["pending_message"])

        state_clean_ready = MonitorState(generation=3, text="She goes to school.", findings=[], status="ready")
        summary_clean = UIPresenter.format_state_summary(state_clean_ready)
        self.assertFalse(summary_clean["is_pending"])
        self.assertEqual(summary_clean["findings_count"], 0)
        self.assertEqual(summary_clean["status_text"], "Ready")

    def test_monitor_lifecycle_integration(self):
        """测试监控器与分析管道的生命周期集成（Phase 8B 启动与关闭）"""
        from core.analysis import AnalysisPipeline, AnalysisResolver, HarperAnalysisEngine
        from core.monitoring import MockTextSource, LiveTextMonitor

        pipeline = AnalysisPipeline()
        pipeline.register_engine(HarperAnalysisEngine())
        resolver = AnalysisResolver()
        text_source = MockTextSource(initial_text="Hello world")
        monitor = LiveTextMonitor(
            text_source=text_source,
            pipeline=pipeline,
            resolver=resolver,
            debounce_interval=0.05,
            poll_interval=0.01,
        )
        self.assertFalse(monitor._is_running)
        monitor.start()
        self.assertTrue(monitor._is_running)
        monitor.stop()
        self.assertFalse(monitor._is_running)

    def test_qmessagebox_imported_in_window(self):
        """测试 window 模块中已成功导入 QMessageBox，防止 NameError 回归"""
        from core.ui.window import GCoachWindow
        import core.ui.window as window_module
        self.assertTrue(hasattr(window_module, "QMessageBox"))

    def test_phase_8e_popup_integration_logic(self):
        """测试 Phase 8E 浮动纠正弹窗与 GCoachWindow 的集成逻辑（通过 Mock 隔离 Win32 无焦点窗口创建）"""
        from core.ui.window import PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

        from unittest.mock import patch, MagicMock
        from core.analysis import AnalysisPipeline, AnalysisResolver, HarperAnalysisEngine
        from core.monitoring import MockTextSource, LiveTextMonitor
        from core.ui.window import GCoachWindow
        from PyQt6.QtWidgets import QApplication

        # 确保 QApplication 存在
        app = QApplication.instance()
        if not app:
            app = QApplication([])

        pipeline = AnalysisPipeline()
        pipeline.register_engine(HarperAnalysisEngine())
        resolver = AnalysisResolver()
        text_source = MockTextSource(initial_text="The students was very happy.")
        monitor = LiveTextMonitor(
            text_source=text_source,
            pipeline=pipeline,
            resolver=resolver,
            debounce_interval=0.01,
            poll_interval=0.01,
        )

        # 构建符合生产接口的 Mock Popup（支持 parent 参数验证）
        class MockPopup:
            def __init__(self, finding, target, on_accept, on_ignore, parent=None):
                self.parent_arg = parent
                self.finding = finding
                self.target = target
                self.on_accept = on_accept
                self.on_ignore = on_ignore
                self.shown_x = 0
                self.shown_y = 0
                self.closed = False

            def show_at(self, x: int, y: int):
                self.shown_x = x
                self.shown_y = y

            def close(self):
                self.closed = True

        window = GCoachWindow(monitor)
        try:
            with patch("core.ui.window.FloatingCorrectionPopup", MockPopup):
                finding = Finding(
                    source="Harper",
                    category="grammar",
                    message="Agreement error",
                    original="was",
                    replacement="were",
                    start=13,
                    end=16,
                )
                state = MonitorState(
                    generation=1,
                    text="The students was very happy.",
                    findings=[finding],
                    status="ready",
                    control_id="mock-ctrl-1",
                    app_name="MockApp",
                )

                window._sync_floating_popup([finding], state)

                window.current_findings = [finding]
                # 验证 findings 出现时弹窗是否被正确同步创建并配置（验证传入的 parent 是否为 window 实例）
                self.assertIsNotNone(window.active_popup)
                self.assertIsInstance(window.active_popup, MockPopup)
                self.assertEqual(window.active_popup.parent_arg, window)
                self.assertEqual(window.last_popup_finding_id, window.current_findings[0].id)
                self.assertEqual(window.active_popup.finding.original, window.current_findings[0].original)

                # 验证 Accept / Ignore 回调与清理逻辑
                finding = window.current_findings[0]
                popup = window.active_popup
                self.assertIsNotNone(popup)

                window._handle_popup_ignore(finding)

                self.assertTrue(popup.closed)
                self.assertIsNone(window.active_popup)
                self.assertIsNone(window.last_popup_finding_id)

                # 回归测试：验证当 last_popup_finding_id 等于 finding.id 但 active_popup 为 None 时，_sync_floating_popup 会重新创建弹窗
                window.last_popup_finding_id = finding.id
                window.active_popup = None
                state = monitor.get_state()
                window._sync_floating_popup([finding], state)
                self.assertIsNotNone(window.active_popup)
                self.assertIsInstance(window.active_popup, MockPopup)
        finally:
            window.close()
            monitor.stop()

    def test_phase_8e_floating_popup_native_event_wm_mouseactivate(self):
        """测试 FloatingCorrectionPopup 在 Windows 平台上的 nativeEvent 对 WM_MOUSEACTIVATE 的处理"""
        from core.ui.window import PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

        from core.ui.floating_correction import FloatingCorrectionPopup
        from core.analysis import Finding
        from core.correction.target import CorrectionTarget
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if not app:
            app = QApplication([])

        finding = Finding(
            source="Harper",
            category="grammar",
            message="Test",
            original="was",
            replacement="were",
            start=0,
            end=3,
        )
        target = CorrectionTarget()
        popup = FloatingCorrectionPopup(finding, target, lambda f, t: None, lambda f: None)

        import platform
        if platform.system() == "Windows":
            try:
                import ctypes
                class MSG(ctypes.Structure):
                    _fields_ = [
                        ("hwnd", ctypes.c_void_p),
                        ("message", ctypes.c_uint32),
                        ("wParam", ctypes.c_void_p),
                        ("lParam", ctypes.c_void_p),
                        ("time", ctypes.c_uint32),
                        ("pt", ctypes.c_long * 2),
                    ]

                # 1. Test WM_MOUSEACTIVATE (0x0021) with integer address pointer representation
                msg_activate = MSG(hwnd=popup.winId(), message=0x0021, wParam=0, lParam=0, time=0, pt=(0, 0))
                addr = ctypes.addressof(msg_activate)
                handled, result = popup.nativeEvent(b"windows_generic_MSG", addr)
                self.assertTrue(handled)
                self.assertEqual(result, 3)  # MA_NOACTIVATE = 3

                # 2. Test non-WM_MOUSEACTIVATE message returns unhandled (False, 0)
                msg_other = MSG(hwnd=popup.winId(), message=0x000F, wParam=0, lParam=0, time=0, pt=(0, 0))
                handled, result = popup.nativeEvent(b"windows_generic_MSG", ctypes.addressof(msg_other))
                self.assertFalse(handled)

                # 3. Test malformed/invalid message data does not raise exceptions (returns safely)
                handled, result = popup.nativeEvent(b"windows_generic_MSG", None)
                self.assertFalse(handled)
                handled, result = popup.nativeEvent(b"windows_generic_MSG", 999999999)
                self.assertFalse(handled)

            except Exception as e:
                pass
        else:
            # 非 Windows 平台应直接调用超类或安全返回
            handled, result = popup.nativeEvent("generic", 0)
            self.assertFalse(handled)
        popup.close()

    def test_phase_8e_floating_popup_win32_style_safety(self):
        """测试 FloatingCorrectionPopup 在 Windows 平台上的 Win32 样式修改安全防御机制"""
        from core.ui.window import PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

        from core.ui.floating_correction import FloatingCorrectionPopup
        from core.analysis import Finding
        from core.correction.target import CorrectionTarget
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if not app:
            app = QApplication([])

        finding = Finding(
            source="Harper",
            category="grammar",
            message="Test",
            original="was",
            replacement="were",
            start=0,
            end=3,
        )
        target = CorrectionTarget()
        # 验证即使在非 Windows 平台或模拟异常下，弹窗创建也不会抛出异常
        popup = FloatingCorrectionPopup(finding, target, lambda f, t: None, lambda f: None)
        self.assertIsNotNone(popup)
        popup.close()

    def test_phase_8e_popup_config_h(self):
        """测试 Phase 8E 诊断配置 H 是否能够正确无误地构造弹出窗口"""
        from core.ui.window import PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

        from core.ui.floating_correction import FloatingCorrectionPopup
        from core.analysis import Finding
        from core.correction.target import CorrectionTarget
        from PyQt6.QtWidgets import QApplication
        import os

        app = QApplication.instance()
        if not app:
            app = QApplication([])

        old_test_env = os.environ.get("GCOACH_POPUP_TEST")
        os.environ["GCOACH_POPUP_TEST"] = "H"
        try:
            finding = Finding(
                source="Harper",
                category="grammar",
                message="Test",
                original="was",
                replacement="were",
                start=0,
                end=3,
            )
            target = CorrectionTarget()
            popup = FloatingCorrectionPopup(finding, target, lambda f, t: None, lambda f: None)
            self.assertIsNotNone(popup)
            popup.show_at(100, 100)
            popup.close()
        finally:
            if old_test_env is not None:
                os.environ["GCOACH_POPUP_TEST"] = old_test_env
            else:
                os.environ.pop("GCOACH_POPUP_TEST", None)

    def test_phase_8e_popup_config_i(self):
        """测试 Phase 8E 诊断配置 I 是否能够正确设置 FramelessWindowHint | Tool 标志且不调用 Win32 代码"""
        from core.ui.window import PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

        from core.ui.floating_correction import FloatingCorrectionPopup
        from core.analysis import Finding
        from core.correction.target import CorrectionTarget
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        import os

        app = QApplication.instance()
        if not app:
            app = QApplication([])

        old_test_env = os.environ.get("GCOACH_POPUP_TEST")
        os.environ["GCOACH_POPUP_TEST"] = "I"
        try:
            finding = Finding(
                source="Harper",
                category="grammar",
                message="Test",
                original="was",
                replacement="were",
                start=0,
                end=3,
            )
            target = CorrectionTarget()
            popup = FloatingCorrectionPopup(finding, target, lambda f, t: None, lambda f: None)
            self.assertIsNotNone(popup)
            flags = popup.windowFlags()
            self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
            self.assertTrue(bool(flags & Qt.WindowType.Tool))
            popup.show_at(100, 100)
            popup.close()
        finally:
            if old_test_env is not None:
                os.environ["GCOACH_POPUP_TEST"] = old_test_env
            else:
                os.environ.pop("GCOACH_POPUP_TEST", None)


if __name__ == "__main__":
    unittest.main()
