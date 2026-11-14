"""
Unit tests for G-Coach UI Presenter and state formatting - Phase 6
"""

import unittest
from core.analysis import Finding
from core.monitoring import MonitorState
from core.correction.target import CorrectionTarget
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
        from PyQt6.QtWidgets import QApplication, QSplitter
        from PyQt6.QtCore import QSize

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
            def __init__(
                self,
                findings,
                current_index,
                target,
                on_accept,
                on_ignore,
                on_navigate=None,
                on_add_to_dict=None,
                parent=None,
                on_accept_all=None,
            ):
                self.parent_arg = parent
                self.findings = list(findings)
                self.current_index = current_index
                self.target = target
                self.on_accept = on_accept
                self.on_ignore = on_ignore
                self.on_navigate = on_navigate
                self.on_add_to_dict = on_add_to_dict
                self.on_accept_all = on_accept_all
                self.shown_x = 0
                self.shown_y = 0
                self.closed = False

            @property
            def finding(self):
                return self.findings[self.current_index]

            def set_findings(self, findings, current_index=0):
                self.findings = list(findings)
                self.current_index = current_index

            def sizeHint(self):
                return QSize(260, 120)

            def show_at(self, x: int, y: int):
                self.shown_x = x
                self.shown_y = y

            def close(self):
                self.closed = True

        window = GCoachWindow(monitor)
        try:
            splitter = window.findChild(QSplitter, "mainSplitter")
            self.assertIsNotNone(splitter)
            self.assertFalse(splitter.childrenCollapsible())
            self.assertFalse(splitter.isCollapsible(0))
            self.assertFalse(splitter.isCollapsible(1))
            self.assertEqual(splitter.widget(0).minimumWidth(), 300)
            self.assertEqual(splitter.widget(1).minimumWidth(), 400)
            window.resize(700, 500)
            self.assertGreaterEqual(window.width(), 760)
            self.assertGreaterEqual(window.height(), 560)

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
                # 验证 findings 出现时弹窗是否被正确同步创建并配置（验证传入的 parent 是否为 None，确保其为顶级独立窗口）
                self.assertIsNotNone(window.active_popup)
                self.assertIsInstance(window.active_popup, MockPopup)
                self.assertIsNone(window.active_popup.parent_arg)
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

    def test_floating_popup_survives_uia_control_type_change_but_closes_on_app_switch(self):
        """UIA child identity changes must not dismiss the popup; foreground app changes must."""
        from core.ui.window import PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

        from core.analysis import AnalysisPipeline, AnalysisResolver
        from core.monitoring import MockTextSource, LiveTextMonitor
        from core.ui.window import GCoachWindow
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if not app:
            app = QApplication([])

        monitor = LiveTextMonitor(
            text_source=MockTextSource(initial_text="The students was happy."),
            pipeline=AnalysisPipeline(),
            resolver=AnalysisResolver(),
        )

        class PopupStub:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        window = GCoachWindow(monitor)
        try:
            editor_state = MonitorState(
                text="The students was happy.",
                status="ready",
                app_name="notepad.exe",
                control_id="uia-edit-1",
                control_type="EditControl",
                metadata={
                    "foreground_hwnd": 100,
                    "foreground_process_id": 4321,
                    "foreground_app_name": "notepad.exe",
                    "foreground_identity": "pid:4321",
                },
            )
            window._update_ignored_context(editor_state)
            popup = PopupStub()
            window.active_popup = popup

            # Simulate the reported transient UIA change while Notepad remains foreground.
            list_item_state = MonitorState(
                text="The students was happy.",
                status="waiting",
                app_name="ListItemControl",
                control_id="uia-list-item-2",
                control_type="ListItemControl",
                metadata={
                    "foreground_hwnd": 100,
                    "foreground_process_id": 4321,
                    "foreground_app_name": "notepad.exe",
                    "foreground_identity": "pid:4321",
                },
            )
            window._update_ignored_context(list_item_state)
            self.assertIs(window.active_popup, popup)
            self.assertFalse(popup.closed)

            # Interacting with a G-Coach-owned popup/dropdown changes the
            # foreground HWND/PID, but it is not an external app switch.
            gcoach_popup_state = MonitorState(
                text="",
                status="unsupported",
                app_name="python.exe",
                control_id="",
                control_type="ListItemControl",
                metadata={
                    "foreground_hwnd": 33162584,
                    "foreground_process_id": 19520,
                    "foreground_app_name": "python.exe",
                    "foreground_identity": "pid:19520",
                    "foreground_is_self": True,
                },
            )
            window._update_ignored_context(gcoach_popup_state)
            self.assertIs(window.active_popup, popup)
            self.assertFalse(popup.closed)

            # A different foreground process is a genuine application switch.
            other_app_state = MonitorState(
                text="The students was happy.",
                status="waiting",
                app_name="winword.exe",
                control_id="uia-list-item-2",
                control_type="ListItemControl",
                metadata={
                    "foreground_hwnd": 200,
                    "foreground_process_id": 8765,
                    "foreground_app_name": "winword.exe",
                    "foreground_identity": "pid:8765",
                },
            )
            window._update_ignored_context(other_app_state)
            self.assertTrue(popup.closed)
            self.assertIsNone(window.active_popup)
        finally:
            window.close()
            monitor.stop()

    def test_popup_reuse_with_semantic_signature(self):
        """回归测试：验证当 findings 内容相同但 id 不同（每次分析重新实例化）时，_sync_floating_popup 会复用现有的 active_popup 而不重新创建"""
        from core.ui.window import PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

        from unittest.mock import patch
        from core.analysis import AnalysisPipeline, AnalysisResolver, HarperAnalysisEngine
        from core.monitoring import MockTextSource, LiveTextMonitor
        from core.ui.window import GCoachWindow
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QSize

        app = QApplication.instance()
        if not app:
            app = QApplication([])

        pipeline = AnalysisPipeline()
        pipeline.register_engine(HarperAnalysisEngine())
        resolver = AnalysisResolver()
        text_source = MockTextSource(initial_text="The students was happy.")
        monitor = LiveTextMonitor(
            text_source=text_source,
            pipeline=pipeline,
            resolver=resolver,
            debounce_interval=0.01,
            poll_interval=0.01,
        )

        class MockPopup:
            def __init__(
                self,
                findings,
                current_index,
                target,
                on_accept,
                on_ignore,
                on_navigate=None,
                on_add_to_dict=None,
                parent=None,
                on_accept_all=None,
            ):
                self.findings = list(findings)
                self.current_index = current_index
                self.on_accept_all = on_accept_all
                self.shown = False
                self.closed = False

            @property
            def finding(self):
                return self.findings[self.current_index]

            def set_findings(self, findings, current_index=0):
                self.findings = list(findings)
                self.current_index = current_index

            def sizeHint(self):
                return QSize(260, 120)

            def show_at(self, x: int, y: int):
                self.shown = True

            def close(self):
                self.closed = True

        window = GCoachWindow(monitor)
        try:
            with patch("core.ui.window.FloatingCorrectionPopup", MockPopup):
                f1 = Finding(
                    source="Harper",
                    category="grammar",
                    message="Agreement",
                    original="was",
                    replacement="were",
                    start=13,
                    end=16,
                )
                state = MonitorState(generation=1, text="The students was happy.", findings=[f1], status="ready")
                window._sync_floating_popup([f1], state)
                popup1 = window.active_popup
                self.assertIsNotNone(popup1)

                # 模拟第二次轮询，生成具有相同语义内容但新随机 id 的 Finding
                f2 = Finding(
                    source="Harper",
                    category="grammar",
                    message="Agreement",
                    original="was",
                    replacement="were",
                    start=13,
                    end=16,
                )
                self.assertNotEqual(f1.id, f2.id)

                window._sync_floating_popup([f2], state)
                popup2 = window.active_popup
                # 验证弹窗被复用，而不是被关闭重建
                self.assertEqual(popup1, popup2)
                self.assertFalse(popup1.closed)
        finally:
            window.close()
            monitor.stop()


    def test_floating_correction_popup_has_no_native_event_and_uses_qt_non_activation(self):
        """回归测试：验证 FloatingCorrectionPopup 不再定义任何自定义 nativeEvent，且具备正确的 Qt 无激活标志与属性"""
        from core.ui.floating_correction import FloatingCorrectionPopup, PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

        self.assertFalse("nativeEvent" in FloatingCorrectionPopup.__dict__)

        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
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
        popup = FloatingCorrectionPopup(
            findings=[finding],
            current_index=0,
            target=target,
            on_accept=lambda f, t: None,
            on_ignore=lambda f: None,
            parent=None,
        )
        self.assertIsNone(popup.parent())
        self.assertTrue(popup.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
        self.assertTrue(popup.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus)
        popup.close()

    def test_floating_correction_popup_accept_click_triggers_callback(self):
        """回归测试：验证点击 FloatingCorrectionPopup 的 Accept 按钮能够正确触发 _handle_accept 并调用上层 on_accept 回调"""
        from core.ui.floating_correction import FloatingCorrectionPopup, PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

        from PyQt6.QtWidgets import QApplication, QPushButton
        app = QApplication.instance()
        if not app:
            app = QApplication([])

        finding = Finding(
            source="Harper",
            category="grammar",
            message="Agreement",
            original="was",
            replacement="were",
            start=0,
            end=3,
        )
        target = CorrectionTarget()
        accepted_findings = []
        accepted_targets = []

        def on_accept(f, t):
            accepted_findings.append(f)
            accepted_targets.append(t)

        popup = FloatingCorrectionPopup(
            findings=[finding],
            current_index=0,
            target=target,
            on_accept=on_accept,
            on_ignore=lambda f: None,
            parent=None,
        )

        buttons = popup.findChildren(QPushButton)
        accept_btn = None
        for btn in buttons:
            if "Accept" in btn.text():
                accept_btn = btn
                break

        self.assertIsNotNone(accept_btn)
        accept_btn.click()

        self.assertEqual(len(accepted_findings), 1)
        self.assertEqual(accepted_findings[0], finding)
        self.assertEqual(accepted_targets[0], target)
        popup.close()

    def test_harper_alternative_selection_is_applied_without_mutating_finding(self):
        """Accept must apply the selected Harper alternative, not always the default."""
        from core.ui.floating_correction import FloatingCorrectionPopup, PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if not app:
            app = QApplication([])

        finding = Finding(
            source="harper",
            category="grammar",
            message="Subject-verb agreement",
            original="was",
            replacement="were",
            start=13,
            end=16,
            metadata={"replacements": ["were", "had been", "would be"]},
        )
        target = CorrectionTarget()
        accepted = []

        def on_accept(selected, selected_target):
            selected.status = "accepted"
            accepted.append((selected, selected_target))

        popup = FloatingCorrectionPopup(
            findings=[finding],
            current_index=0,
            target=target,
            on_accept=on_accept,
            on_ignore=lambda _finding: None,
        )

        self.assertFalse(popup.replacement_combo.isHidden())
        self.assertEqual(
            [popup.replacement_combo.itemText(i) for i in range(popup.replacement_combo.count())],
            ["were", "had been", "would be"],
        )
        self.assertEqual(popup.replacement_combo.currentData(), "were")

        popup.replacement_combo.setCurrentIndex(1)
        self.assertIn('to "had been"', popup.title_label.text())
        popup.accept_btn.click()

        self.assertEqual(len(accepted), 1)
        selected_finding, selected_target = accepted[0]
        self.assertEqual(selected_finding.replacement, "had been")
        self.assertEqual(selected_finding.id, finding.id)
        self.assertIsNot(selected_finding, finding)
        self.assertEqual(finding.replacement, "had been")
        self.assertEqual(finding.status, "accepted")
        self.assertIs(selected_target, target)
        popup.close()

    def test_non_activating_dropdown_preserves_native_mouse_click(self):
        """A dropdown click must be delivered without activating its popup window."""
        import ctypes
        import platform
        from ctypes import wintypes
        from core.ui import floating_correction

        if not floating_correction.PYQT_AVAILABLE or platform.system() != "Windows":
            self.skipTest("The native popup mouse filter is Windows/PyQt-specific.")

        event_filter = floating_correction._NonActivatingPopupMouseFilter()
        popup_hwnd = 0x1234
        owner_hwnd = 0x4321
        event_filter.set_popup_hwnd(popup_hwnd, owner_hwnd)

        message = wintypes.MSG()
        message.hWnd = popup_hwnd
        message.message = event_filter.WM_MOUSEACTIVATE
        result = event_filter.nativeEventFilter(
            b"windows_generic_MSG",
            ctypes.addressof(message),
        )
        self.assertEqual(result, (True, event_filter.MA_NOACTIVATE))

        # An owned Qt popup can report its root owner (the floating correction
        # window) as the top-level parent in WM_MOUSEACTIVATE.
        message.hWnd = 0x5678
        message.wParam = owner_hwnd
        result = event_filter.nativeEventFilter(
            b"windows_generic_MSG",
            ctypes.addressof(message),
        )
        self.assertEqual(result, (True, event_filter.MA_NOACTIVATE))

        # Also handle the native case where a child reports the dropdown as
        # the top-level parent that would otherwise be activated.
        message.hWnd = 0x5678
        message.wParam = popup_hwnd
        result = event_filter.nativeEventFilter(
            b"windows_generic_MSG",
            ctypes.addressof(message),
        )
        self.assertEqual(result, (True, event_filter.MA_NOACTIVATE))

        message.message = 0x0201  # WM_LBUTTONDOWN is not an activation query.
        self.assertEqual(
            event_filter.nativeEventFilter(
                b"windows_generic_MSG",
                ctypes.addressof(message),
            ),
            (False, 0),
        )

        message.message = event_filter.WM_MOUSEACTIVATE
        message.wParam = 0x9999
        self.assertEqual(
            event_filter.nativeEventFilter(
                b"windows_generic_MSG",
                ctypes.addressof(message),
            ),
            (False, 0),
        )

    def test_alternative_dropdown_is_non_activating_and_keeps_popup_open(self):
        """Selecting an alternative must not activate G-Coach or dismiss its floating popup."""
        from core.ui.floating_correction import FloatingCorrectionPopup, PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

        from PyQt6.QtCore import QEventLoop, QTimer, Qt
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QApplication, QWidget

        app = QApplication.instance()
        if not app:
            app = QApplication([])

        # Represents the editor which must remain in the foreground while the
        # non-activating correction popup's alternative list is being used.
        editor = QWidget()
        editor.setWindowTitle("Notepad focus test")
        editor.show()
        editor.activateWindow()
        app.processEvents()

        editor_hwnd = None
        native_user32 = None
        foreground_events = []
        foreground_callback = None
        foreground_hook = None
        if __import__("platform").system() == "Windows":
            import ctypes
            from ctypes import wintypes

            native_user32 = ctypes.WinDLL("user32", use_last_error=True)
            native_user32.GetForegroundWindow.restype = ctypes.c_void_p
            editor_hwnd = int(editor.winId())
            if int(native_user32.GetForegroundWindow() or 0) != editor_hwnd:
                editor.close()
                self.skipTest("Windows did not grant the test editor foreground activation.")

            # A final GetForegroundWindow() check can miss a brief activation
            # followed by an automatic return to the editor. Observe every
            # foreground transition while the popup and its dropdown are shown.
            callback_type = ctypes.WINFUNCTYPE(
                None,
                wintypes.HWND,
                wintypes.DWORD,
                wintypes.HWND,
                wintypes.LONG,
                wintypes.LONG,
                wintypes.DWORD,
                wintypes.DWORD,
            )

            def record_foreground(hwnd, *_args):
                foreground_events.append(int(hwnd or 0))

            foreground_callback = callback_type(record_foreground)
            native_user32.SetWinEventHook.argtypes = (
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.HMODULE,
                callback_type,
                wintypes.DWORD,
                wintypes.DWORD,
                wintypes.DWORD,
            )
            native_user32.SetWinEventHook.restype = wintypes.HANDLE
            foreground_hook = native_user32.SetWinEventHook(
                0x0003,  # EVENT_SYSTEM_FOREGROUND
                0x0003,
                None,
                foreground_callback,
                0,
                0,
                0,  # WINEVENT_OUTOFCONTEXT
            )
            self.assertTrue(foreground_hook, "Could not install the foreground-event regression hook.")
            native_user32.SendMessageW.argtypes = (
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            )
            native_user32.SendMessageW.restype = ctypes.c_ssize_t

        finding = Finding(
            source="harper",
            category="grammar",
            message="Subject-verb agreement",
            original="was",
            replacement="were",
            start=0,
            end=3,
            metadata={"replacements": ["were", "had been", "would be"]},
        )
        popup = FloatingCorrectionPopup(
            findings=[finding],
            current_index=0,
            target=CorrectionTarget(),
            on_accept=lambda _finding, _target: None,
            on_ignore=lambda _finding: None,
        )

        try:
            popup.show_at(100, 100)
            QTest.qWait(50)
            if native_user32 is not None:
                get_window_long = native_user32.GetWindowLongPtrW
                get_window_long.argtypes = (ctypes.c_void_p, ctypes.c_int)
                get_window_long.restype = ctypes.c_ssize_t
                popup_hwnd = int(popup.winId())
                popup_ex_style = get_window_long(popup_hwnd, -20)
                self.assertTrue(
                    popup_ex_style & 0x08000000,
                    "Floating popup HWND must have WS_EX_NOACTIVATE before interaction.",
                )
                self.assertTrue(
                    popup_ex_style & 0x00000008,
                    "Floating popup must be topmost through its non-activating native z-order.",
                )
                self.assertEqual(
                    int(native_user32.GetForegroundWindow() or 0),
                    editor_hwnd,
                    "Showing the floating popup must not change the foreground window.",
                )
                self.assertFalse(
                    [hwnd for hwnd in foreground_events if hwnd != editor_hwnd],
                    "Showing the floating popup caused a transient foreground activation.",
                )
            combo = popup.replacement_combo
            event_loop = QEventLoop()
            failures = []

            def select_alternative():
                try:
                    self.assertTrue(editor.isActiveWindow())
                    # Exercise both non-default rows and the selection update.
                    # Native WM_MOUSEACTIVATE ownership is covered above; this
                    # Qt test remains deterministic and does not move the user's
                    # desktop cursor.
                    for attempt in range(10):
                        option_index, expected = (
                            (1, "had been") if attempt % 2 == 0 else (2, "would be")
                        )
                        if not combo.view().isVisible():
                            combo.showPopup()
                            QTest.qWait(250)

                        dropdown_window = combo.view().window()
                        self.assertTrue(combo.view().isVisible())
                        self.assertTrue(
                            dropdown_window.windowFlags()
                            & Qt.WindowType.WindowDoesNotAcceptFocus
                        )
                        if native_user32 is not None:
                            self.assertEqual(
                                combo._mouse_activation_filter._popup_hwnd,
                                int(dropdown_window.winId()),
                            )
                            viewport_hwnd = int(combo.view().viewport().winId())
                            self.assertTrue(
                                combo._mouse_activation_filter._is_popup_related(viewport_hwnd),
                                "The native activation filter must recognize child HWNDs inside the dropdown.",
                            )
                            native_message = wintypes.MSG()
                            native_message.hWnd = viewport_hwnd
                            native_message.message = combo._mouse_activation_filter.WM_MOUSEACTIVATE
                            self.assertEqual(
                                combo._mouse_activation_filter.nativeEventFilter(
                                    b"windows_generic_MSG",
                                    ctypes.addressof(native_message),
                                ),
                                (True, combo._mouse_activation_filter.MA_NOACTIVATE),
                                "A child dropdown HWND must receive the non-activating mouse response.",
                            )
                        item_rect = combo.view().visualRect(combo.model().index(option_index, 0))
                        self.assertTrue(item_rect.isValid() and item_rect.isNull() is False)
                        self.assertTrue(combo.view().viewport().rect().contains(item_rect.center()))
                        if native_user32 is not None:
                            viewport_hwnd = int(combo.view().viewport().winId())
                            dropdown_hwnd = int(dropdown_window.winId())
                            device_ratio = combo.view().viewport().devicePixelRatioF()
                            native_x = round(item_rect.center().x() * device_ratio)
                            native_y = round(item_rect.center().y() * device_ratio)
                            point_lparam = ((native_y & 0xFFFF) << 16) | (native_x & 0xFFFF)
                            activate_lparam = (0x0201 << 16) | 1  # HTCLIENT + WM_LBUTTONDOWN
                            native_user32.SendMessageW(
                                viewport_hwnd,
                                0x0021,  # WM_MOUSEACTIVATE
                                dropdown_hwnd,
                                activate_lparam,
                            )
                            native_user32.SendMessageW(
                                viewport_hwnd,
                                0x0201,  # WM_LBUTTONDOWN
                                0x0001,  # MK_LBUTTON
                                point_lparam,
                            )
                            native_user32.SendMessageW(
                                viewport_hwnd,
                                0x0202,  # WM_LBUTTONUP
                                0,
                                point_lparam,
                            )
                            app.processEvents()
                        else:
                            QTest.mouseClick(
                                combo.view().viewport(),
                                Qt.MouseButton.LeftButton,
                                pos=item_rect.center(),
                            )
                        self.assertEqual(combo.currentData(), expected)
                        self.assertTrue(popup.isVisible())
                        self.assertTrue(editor.isActiveWindow())
                        if native_user32 is not None:
                            QTest.qWait(50)
                            self.assertEqual(
                                int(native_user32.GetForegroundWindow() or 0),
                                editor_hwnd,
                                "Using the alternative dropdown must not change the foreground window.",
                            )
                            self.assertFalse(
                                [hwnd for hwnd in foreground_events if hwnd != editor_hwnd],
                                "Opening or selecting an alternative caused a transient foreground activation.",
                            )
                        self.assertIn(f'to "{expected}"', popup.title_label.text())
                except AssertionError as exc:
                    failures.append(exc)
                finally:
                    event_loop.quit()

            def open_alternatives():
                combo.showPopup()
                QTimer.singleShot(250, select_alternative)

            QTimer.singleShot(0, open_alternatives)
            QTimer.singleShot(2000, event_loop.quit)
            event_loop.exec()
            if failures:
                raise failures[0]
        finally:
            if native_user32 is not None and foreground_hook:
                native_user32.UnhookWinEvent.argtypes = (wintypes.HANDLE,)
                native_user32.UnhookWinEvent.restype = wintypes.BOOL
                native_user32.UnhookWinEvent(foreground_hook)
            popup.close()
            editor.close()

    def test_non_harper_findings_do_not_show_metadata_replacements_as_alternatives(self):
        """Alternative selection is limited to Harper's ordered replacement suggestions."""
        from core.ui.floating_correction import FloatingCorrectionPopup, PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if not app:
            app = QApplication([])

        finding = Finding(
            source="symspell",
            category="spelling",
            message="Spelling",
            original="teh",
            replacement="the",
            start=0,
            end=3,
            metadata={"replacements": ["the", "ten"]},
        )
        popup = FloatingCorrectionPopup(
            findings=[finding],
            current_index=0,
            target=CorrectionTarget(),
            on_accept=lambda _finding, _target: None,
            on_ignore=lambda _finding: None,
        )

        self.assertTrue(popup.replacement_combo.isHidden())
        self.assertTrue(popup.alternatives_label.isHidden())
        popup.close()

    def test_accept_all_uses_the_selected_alternative_for_the_current_finding(self):
        """The bulk action must not silently discard the replacement currently selected by the user."""
        from core.ui.floating_correction import FloatingCorrectionPopup, PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if not app:
            app = QApplication([])

        findings = [
            Finding(
                source="harper",
                category="grammar",
                message="Agreement",
                original="was",
                replacement="were",
                start=4,
                end=7,
                metadata={"replacements": ["were", "had been"]},
            ),
            Finding("symspell", "spelling", "Spelling", "teh", "the", 12, 15),
        ]
        calls = []

        def on_accept_all(batch, target):
            for item in batch:
                item.status = "accepted"
            calls.append((batch, target))

        popup = FloatingCorrectionPopup(
            findings=findings,
            current_index=0,
            target=CorrectionTarget(),
            on_accept=lambda _finding, _target: None,
            on_ignore=lambda _finding: None,
            on_accept_all=on_accept_all,
        )

        popup.replacement_combo.setCurrentIndex(1)
        popup.accept_all_btn.click()

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0][0].replacement, "had been")
        self.assertEqual(calls[0][0][1], findings[1])
        self.assertEqual(findings[0].replacement, "had been")
        self.assertEqual(findings[0].status, "accepted")
        popup.close()

    def test_floating_popup_batch_button_passes_the_complete_findings_set(self):
        """The optional batch action is visible for multiple findings and calls its handler once."""
        from core.ui.floating_correction import FloatingCorrectionPopup, PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if not app:
            app = QApplication([])

        findings = [
            Finding("symspell", "spelling", "First", "teh", "the", 0, 3),
            Finding("symspell", "spelling", "Second", "wrod", "word", 8, 12),
        ]
        target = CorrectionTarget()
        calls = []
        popup = FloatingCorrectionPopup(
            findings=findings,
            current_index=0,
            target=target,
            on_accept=lambda f, t: None,
            on_ignore=lambda f: None,
            on_accept_all=lambda batch, batch_target: calls.append((batch, batch_target)),
        )

        self.assertFalse(popup.accept_all_btn.isHidden())
        popup.accept_all_btn.click()

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], findings)
        self.assertIs(calls[0][1], target)
        self.assertFalse(popup.isVisible())
        popup.close()

    def test_spelling_suggestion_popup_shows_accept_dictionary_and_ignore(self):
        """A spelling suggestion must offer all three choices when a replacement exists."""
        from core.ui.floating_correction import FloatingCorrectionPopup, PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if not app:
            app = QApplication([])

        finding = Finding(
            source="symspell",
            category="spelling",
            message="Possible spelling mistake",
            original="doiing",
            replacement="doing",
            start=0,
            end=6,
        )
        popup = FloatingCorrectionPopup(
            findings=[finding],
            current_index=0,
            target=CorrectionTarget(),
            on_accept=lambda f, t: None,
            on_ignore=lambda f: None,
            on_add_to_dict=lambda f: None,
        )

        self.assertFalse(popup.accept_btn.isHidden())
        self.assertFalse(popup.add_to_dict_btn.isHidden())
        self.assertFalse(popup.ignore_btn.isHidden())
        self.assertTrue(popup.accept_btn.isEnabled())
        self.assertTrue(popup.add_to_dict_btn.isEnabled())
        self.assertTrue(popup.ignore_btn.isEnabled())
        popup.close()

    def test_unknown_word_without_replacement_does_not_show_accept(self):
        """An unknown word without a replacement offers dictionary and ignore only."""
        from core.ui.floating_correction import FloatingCorrectionPopup, PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if not app:
            app = QApplication([])

        finding = Finding(
            source="harper",
            category="spelling",
            message="Unknown word",
            original="Ichinomiya",
            replacement="",
            start=0,
            end=10,
        )
        popup = FloatingCorrectionPopup(
            findings=[finding],
            current_index=0,
            target=CorrectionTarget(),
            on_accept=lambda f, t: None,
            on_ignore=lambda f: None,
            on_add_to_dict=lambda f: None,
        )

        self.assertTrue(popup.accept_btn.isHidden())
        self.assertFalse(popup.add_to_dict_btn.isHidden())
        self.assertFalse(popup.ignore_btn.isHidden())
        popup.close()

    def test_main_window_enables_accept_and_dictionary_for_spelling_suggestion(self):
        """The main findings panel must offer the same spelling choices as the popup."""
        from core.ui.window import PYQT_AVAILABLE, GCoachWindow
        if not PYQT_AVAILABLE:
            return

        from core.analysis import AnalysisPipeline, AnalysisResolver
        from core.monitoring import LiveTextMonitor, MockTextSource
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication, QListWidgetItem

        app = QApplication.instance()
        if not app:
            app = QApplication([])

        monitor = LiveTextMonitor(
            text_source=MockTextSource(initial_text="doiing"),
            pipeline=AnalysisPipeline(),
            resolver=AnalysisResolver(),
        )
        window = GCoachWindow(monitor)
        try:
            finding = Finding(
                source="symspell",
                category="spelling",
                message="Possible spelling mistake",
                original="doiing",
                replacement="doing",
                start=0,
                end=6,
            )
            window.current_findings = [finding]
            item = QListWidgetItem("doiing → doing")
            item.setData(Qt.ItemDataRole.UserRole, finding)
            window.findings_list_widget.addItem(item)
            window.findings_list_widget.setCurrentItem(item)
            window._on_finding_selected()

            self.assertTrue(window.btn_accept.isEnabled())
            self.assertTrue(window.btn_add_to_dict.isEnabled())
            self.assertTrue(window.btn_ignore.isEnabled())
        finally:
            window.close()
            monitor.stop()

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
        popup = FloatingCorrectionPopup([finding], 0, target, lambda f, t: None, lambda f: None)
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
            popup = FloatingCorrectionPopup([finding], 0, target, lambda f, t: None, lambda f: None)
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
            popup = FloatingCorrectionPopup([finding], 0, target, lambda f, t: None, lambda f: None)
            self.assertIsNotNone(popup)
            flags = popup.windowFlags()
            self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
            self.assertEqual(
                flags & Qt.WindowType.WindowType_Mask,
                Qt.WindowType.Tool,
            )
            popup.show_at(100, 100)
            popup.close()
        finally:
            if old_test_env is not None:
                os.environ["GCOACH_POPUP_TEST"] = old_test_env
            else:
                os.environ.pop("GCOACH_POPUP_TEST", None)

    def test_phase_8e_popup_config_j(self):
        """测试 Phase 8E 诊断配置 J 是否能够正确设置 FramelessWindowHint | WindowStaysOnTopHint 标志且不调用 Win32 代码"""
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
        os.environ["GCOACH_POPUP_TEST"] = "J"
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
            popup = FloatingCorrectionPopup([finding], 0, target, lambda f, t: None, lambda f: None)
            self.assertIsNotNone(popup)
            flags = popup.windowFlags()
            self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
            self.assertTrue(bool(flags & Qt.WindowType.WindowStaysOnTopHint))
            popup.show_at(100, 100)
            popup.close()
        finally:
            if old_test_env is not None:
                os.environ["GCOACH_POPUP_TEST"] = old_test_env
            else:
                os.environ.pop("GCOACH_POPUP_TEST", None)

    def test_phase_8e_popup_config_k(self):
        """测试 Phase 8E 诊断配置 K 是否能够正确设置 FramelessWindowHint | WindowStaysOnTopHint | WindowDoesNotAcceptFocus 标志且不调用 Win32 代码"""
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
        os.environ["GCOACH_POPUP_TEST"] = "K"
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
            popup = FloatingCorrectionPopup([finding], 0, target, lambda f, t: None, lambda f: None)
            self.assertIsNotNone(popup)
            flags = popup.windowFlags()
            self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
            self.assertTrue(bool(flags & Qt.WindowType.WindowStaysOnTopHint))
            self.assertTrue(bool(flags & Qt.WindowType.WindowDoesNotAcceptFocus))
            popup.show_at(100, 100)
            popup.close()
        finally:
            if old_test_env is not None:
                os.environ["GCOACH_POPUP_TEST"] = old_test_env
            else:
                os.environ.pop("GCOACH_POPUP_TEST", None)

    def test_phase_8e_popup_config_l(self):
        """测试 Phase 8E 诊断配置 L 是否包含正确的 Qt 标志与 WA_ShowWithoutActivating 属性且不包含 Qt.Tool"""
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
        os.environ["GCOACH_POPUP_TEST"] = "L"
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
            popup = FloatingCorrectionPopup([finding], 0, target, lambda f, t: None, lambda f: None)
            self.assertIsNotNone(popup)
            flags = popup.windowFlags()
            self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
            self.assertTrue(bool(flags & Qt.WindowType.WindowStaysOnTopHint))
            self.assertTrue(bool(flags & Qt.WindowType.WindowDoesNotAcceptFocus))
            self.assertNotEqual(
                flags & Qt.WindowType.WindowType_Mask,
                Qt.WindowType.Tool,
            )
            self.assertTrue(popup.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
            popup.show_at(100, 100)
            popup.close()
        finally:
            if old_test_env is not None:
                os.environ["GCOACH_POPUP_TEST"] = old_test_env
            else:
                os.environ.pop("GCOACH_POPUP_TEST", None)

    def test_phase_8e_popup_config_m(self):
        """测试 Phase 8E 诊断配置 M 是否包含正确的 Qt 标志、WA_ShowWithoutActivating 属性以及安全的 winId 调用"""
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
        os.environ["GCOACH_POPUP_TEST"] = "M"
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
            popup = FloatingCorrectionPopup([finding], 0, target, lambda f, t: None, lambda f: None)
            self.assertIsNotNone(popup)
            flags = popup.windowFlags()
            self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
            self.assertTrue(bool(flags & Qt.WindowType.WindowStaysOnTopHint))
            self.assertTrue(bool(flags & Qt.WindowType.WindowDoesNotAcceptFocus))
            self.assertNotEqual(
                flags & Qt.WindowType.WindowType_Mask,
                Qt.WindowType.Tool,
            )
            self.assertTrue(popup.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
            popup.show_at(100, 100)
            popup.close()
        finally:
            if old_test_env is not None:
                os.environ["GCOACH_POPUP_TEST"] = old_test_env
            else:
                os.environ.pop("GCOACH_POPUP_TEST", None)

    def test_phase_8e_popup_config_n(self):
        """测试 Phase 8E 诊断配置 N 是否包含正确的 Qt 标志、WA_ShowWithoutActivating 属性以及非干预性 nativeEvent 观察能力"""
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
        os.environ["GCOACH_POPUP_TEST"] = "N"
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
            popup = FloatingCorrectionPopup([finding], 0, target, lambda f, t: None, lambda f: None)
            self.assertIsNotNone(popup)
            flags = popup.windowFlags()
            self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
            self.assertTrue(bool(flags & Qt.WindowType.WindowStaysOnTopHint))
            self.assertTrue(bool(flags & Qt.WindowType.WindowDoesNotAcceptFocus))
            self.assertNotEqual(
                flags & Qt.WindowType.WindowType_Mask,
                Qt.WindowType.Tool,
            )
            self.assertTrue(popup.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
            popup.show_at(100, 100)
            popup.close()
        finally:
            if old_test_env is not None:
                os.environ["GCOACH_POPUP_TEST"] = old_test_env
            else:
                os.environ.pop("GCOACH_POPUP_TEST", None)

    def test_phase_8e_popup_config_o(self):
        """测试 Phase 8E 诊断配置 O 是否包含正确的 Qt 标志、WA_ShowWithoutActivating 属性以及安全的 windowHandle 调用"""
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
        os.environ["GCOACH_POPUP_TEST"] = "O"
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
            popup = FloatingCorrectionPopup([finding], 0, target, lambda f, t: None, lambda f: None)
            self.assertIsNotNone(popup)
            flags = popup.windowFlags()
            self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
            self.assertTrue(bool(flags & Qt.WindowType.WindowStaysOnTopHint))
            self.assertTrue(bool(flags & Qt.WindowType.WindowDoesNotAcceptFocus))
            self.assertNotEqual(
                flags & Qt.WindowType.WindowType_Mask,
                Qt.WindowType.Tool,
            )
            self.assertTrue(popup.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
            popup.show_at(100, 100)
            popup.close()
        finally:
            if old_test_env is not None:
                os.environ["GCOACH_POPUP_TEST"] = old_test_env
            else:
                os.environ.pop("GCOACH_POPUP_TEST", None)

    def test_phase_8e_popup_config_p(self):
        """测试 Phase 8E 诊断配置 P 是否包含正确的 Qt 标志、WA_ShowWithoutActivating 属性以及在 show 之后安全的 windowHandle 获取"""
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
        os.environ["GCOACH_POPUP_TEST"] = "P"
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
            popup = FloatingCorrectionPopup([finding], 0, target, lambda f, t: None, lambda f: None)
            self.assertIsNotNone(popup)
            flags = popup.windowFlags()
            self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
            self.assertTrue(bool(flags & Qt.WindowType.WindowStaysOnTopHint))
            self.assertTrue(bool(flags & Qt.WindowType.WindowDoesNotAcceptFocus))
            self.assertNotEqual(
                flags & Qt.WindowType.WindowType_Mask,
                Qt.WindowType.Tool,
            )
            self.assertTrue(popup.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
            popup.show_at(100, 100)
            popup.close()
        finally:
            if old_test_env is not None:
                os.environ["GCOACH_POPUP_TEST"] = old_test_env
            else:
                os.environ.pop("GCOACH_POPUP_TEST", None)

    def test_phase_8e_popup_config_q(self):
        """测试 Phase 8E 诊断配置 Q 是否包含正确的 Qt 标志、WA_ShowWithoutActivating 属性以及真实的 Accept/Ignore 交互连接"""
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
        os.environ["GCOACH_POPUP_TEST"] = "Q"
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
            accepted = []
            ignored = []
            popup = FloatingCorrectionPopup(
                [finding],
                0,
                target,
                lambda f, t: accepted.append((f, t)),
                lambda f: ignored.append(f)
            )
            self.assertIsNotNone(popup)
            flags = popup.windowFlags()
            self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
            self.assertTrue(bool(flags & Qt.WindowType.WindowStaysOnTopHint))
            self.assertTrue(bool(flags & Qt.WindowType.WindowDoesNotAcceptFocus))
            self.assertNotEqual(
                flags & Qt.WindowType.WindowType_Mask,
                Qt.WindowType.Tool,
            )
            self.assertTrue(popup.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))

            # Simulate Accept click and Ignore click
            popup._handle_accept()
            self.assertEqual(len(accepted), 1)

            popup._handle_ignore()
            self.assertEqual(len(ignored), 1)

            popup.show_at(100, 100)
            popup.close()
        finally:
            if old_test_env is not None:
                os.environ["GCOACH_POPUP_TEST"] = old_test_env
            else:
                os.environ.pop("GCOACH_POPUP_TEST", None)


if __name__ == "__main__":
    unittest.main()
