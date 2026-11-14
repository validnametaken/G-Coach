"""
Unit tests for LiveTextMonitor, debounce, generation tracking, and stale result protection - Phase 5
"""

import time
import threading
import unittest
from core.analysis import AnalysisPipeline, AnalysisResolver, Finding, BaseAnalysisEngine
from core.monitoring import MockTextSource, MultiControlMockTextSource, LiveTextMonitor, TextSnapshot


class DummyAnalysisEngine(BaseAnalysisEngine):
    """用于测试的虚拟分析引擎"""
    def __init__(self, name="dummy", delay=0.0):
        super().__init__(name=name, version="1.0.0", is_local=True)
        self.delay = delay

    def analyze(self, text: str):
        if self.delay > 0:
            time.sleep(self.delay)
        if "error" in text:
            return [
                Finding(
                    source=self.name,
                    category="grammar",
                    message="Dummy error",
                    original="error",
                    replacement="fixed",
                    start=text.index("error"),
                    end=text.index("error") + 5,
                    confidence=0.99,
                )
            ]
        return []


class FailingAnalysisEngine(BaseAnalysisEngine):
    """故意抛出异常的分析引擎，用于测试异常恢复"""
    def __init__(self):
        super().__init__(name="fail", version="1.0.0")

    def analyze(self, text: str):
        raise RuntimeError("Intentional analysis failure")


class TestLiveTextMonitor(unittest.TestCase):
    """测试 LiveTextMonitor 的防抖、代数追踪、过期结果丢弃、线程安全与生命周期"""

    def setUp(self):
        self.text_source = MockTextSource(initial_text="Hello world")
        self.pipeline = AnalysisPipeline()
        self.pipeline.register_engine(DummyAnalysisEngine())
        self.resolver = AnalysisResolver()
        
        # 使用较短的 debounce 方便测试
        self.monitor = LiveTextMonitor(
            text_source=self.text_source,
            pipeline=self.pipeline,
            resolver=self.resolver,
            debounce_interval=0.1,
            poll_interval=0.02,
        )

    def tearDown(self):
        self.monitor.stop()

    def test_initial_state(self):
        state = self.monitor.get_state()
        self.assertEqual(state.status, "idle")
        self.assertEqual(state.generation, 0)
        self.assertEqual(state.findings, [])

    def test_monitor_state_preserves_correction_target_identity(self):
        """The UI-facing state must retain identity captured for safe UIA edits."""
        from core.correction.target import CorrectionTarget

        class IdentifiedTextSource:
            def get_current_text(self):
                return TextSnapshot(
                    text="The students was happy.",
                    app_name="Notepad.exe",
                    control_info="EditControl | Editor",
                    control_id="pid:4321-hwnd:8765-autoid:editor-type:EditControl-name:Editor",
                    control_type="EditControl",
                    process_id=4321,
                    metadata={
                        "hwnd": 8765,
                        "automation_id": "editor",
                        "control_name": "Editor",
                    },
                )

        monitor = LiveTextMonitor(
            text_source=IdentifiedTextSource(),
            pipeline=self.pipeline,
            resolver=self.resolver,
        )
        state = monitor.trigger_check()
        target = CorrectionTarget.from_snapshot(state)

        self.assertEqual(state.process_id, 4321)
        self.assertEqual(target.process_id, 4321)
        self.assertEqual(target.hwnd, 8765)
        self.assertEqual(target.automation_id, "editor")
        self.assertEqual(target.control_name, "Editor")

    def test_foreground_process_change_invalidates_same_uia_control(self):
        """A real foreground-process switch must be detected even if UIA reuses the same control ID."""
        class ForegroundSwitchingSource:
            def __init__(self):
                self.snapshot = TextSnapshot(
                    text="The students was happy.",
                    app_name="notepad.exe",
                    control_id="uia-control-1",
                    control_type="EditControl",
                    process_id=4321,
                    metadata={
                        "foreground_hwnd": 100,
                        "foreground_process_id": 4321,
                        "foreground_app_name": "notepad.exe",
                        "foreground_identity": "pid:4321",
                    },
                )

            def get_current_text(self):
                return self.snapshot

        source = ForegroundSwitchingSource()
        monitor = LiveTextMonitor(
            text_source=source,
            pipeline=self.pipeline,
            resolver=self.resolver,
        )

        first_state = monitor.trigger_check()
        source.snapshot = TextSnapshot(
            text="The students was happy.",
            app_name="winword.exe",
            control_id="uia-control-1",
            control_type="EditControl",
            process_id=4321,
            metadata={
                "foreground_hwnd": 200,
                "foreground_process_id": 8765,
                "foreground_app_name": "winword.exe",
                "foreground_identity": "pid:8765",
            },
        )
        second_state = monitor.trigger_check()

        self.assertGreater(second_state.generation, first_state.generation)
        self.assertEqual(second_state.status, "waiting")
        self.assertEqual(second_state.metadata["foreground_identity"], "pid:8765")
        self.assertEqual(second_state.app_name, "winword.exe")

    def test_gcoach_foreground_window_preserves_last_external_editor(self):
        """Interacting with a G-Coach popup must not replace or clear the external editor snapshot."""
        class SwitchingSource:
            def __init__(self):
                self.snapshot = TextSnapshot(
                    text="The students was happy.",
                    app_name="notepad.exe",
                    control_id="notepad-editor",
                    control_type="DocumentControl",
                    process_id=4321,
                    metadata={
                        "foreground_process_id": 4321,
                        "foreground_app_name": "notepad.exe",
                        "foreground_identity": "pid:4321",
                    },
                )

            def get_current_text(self):
                return self.snapshot

        source = SwitchingSource()
        monitor = LiveTextMonitor(
            text_source=source,
            pipeline=self.pipeline,
            resolver=self.resolver,
        )

        editor_state = monitor.trigger_check()
        source.snapshot = TextSnapshot(
            text="happy",
            app_name="notepad.exe",
            control_info="ListItemControl | happy",
            control_id="gcoach-dropdown-item-happy",
            control_type="ListItemControl",
            process_id=19520,
            is_editable=False,
            status="unsupported",
            metadata={
                "foreground_process_id": 4321,
                "foreground_app_name": "notepad.exe",
                "foreground_identity": "pid:4321",
                "uia_process_id": 19520,
                "uia_focus_is_self": True,
                "uia_control_type": "ListItemControl",
                "uia_control_name": "happy",
            },
        )
        dropdown_state = monitor.trigger_check()

        self.assertEqual(dropdown_state.text, editor_state.text)
        self.assertEqual(dropdown_state.status, editor_state.status)
        self.assertEqual(dropdown_state.generation, editor_state.generation)
        self.assertEqual(dropdown_state.metadata["foreground_identity"], "pid:4321")

        source.snapshot = TextSnapshot(
            app_name="python.exe",
            control_info="G-Coach internal window",
            process_id=19520,
            is_editable=False,
            status="unsupported",
            metadata={
                "foreground_hwnd": 33162584,
                "foreground_process_id": 19520,
                "foreground_app_name": "python.exe",
                "foreground_identity": "pid:19520",
                "foreground_is_self": True,
            },
        )
        popup_state = monitor.trigger_check()

        self.assertEqual(popup_state.text, editor_state.text)
        self.assertEqual(popup_state.status, editor_state.status)
        self.assertEqual(popup_state.generation, editor_state.generation)
        self.assertEqual(popup_state.metadata["foreground_identity"], "pid:4321")

        source.snapshot = TextSnapshot(
            text="A different document.",
            app_name="winword.exe",
            control_id="word-editor",
            control_type="DocumentControl",
            process_id=8765,
            metadata={
                "foreground_process_id": 8765,
                "foreground_app_name": "winword.exe",
                "foreground_identity": "pid:8765",
            },
        )
        other_app_state = monitor.trigger_check()
        self.assertGreater(other_app_state.generation, popup_state.generation)
        self.assertEqual(other_app_state.metadata["foreground_identity"], "pid:8765")

    def test_gcoach_uia_dropdown_focus_preserves_external_editor_snapshot(self):
        """A G-Coach-owned dropdown item must not be treated as document text."""
        import os
        import sys
        import types
        from unittest.mock import Mock, patch
        from core.monitoring.capture import WindowsUIAccessibilityTextSource

        focused = Mock()
        focused.ControlTypeName = "ListItemControl"
        focused.Name = "happy"
        focused.ClassName = ""
        focused.ProcessId = 19520
        focused.NativeWindowHandle = 0
        focused.AutomationId = "QApplication.FloatingCorrectionPopup.replacementOptions.QComboBoxListView"

        uia_module = types.ModuleType("uiautomation")
        uia_module.GetFocusedControl = Mock(return_value=focused)

        win32gui_module = types.ModuleType("win32gui")
        win32gui_module.GetForegroundWindow = Mock(return_value=100)
        win32process_module = types.ModuleType("win32process")
        win32process_module.GetWindowThreadProcessId = Mock(return_value=(10, 4321))
        win32process_module.GetModuleFileNameEx = Mock(return_value="C:\\Windows\\System32\\notepad.exe")
        win32api_module = types.ModuleType("win32api")
        win32api_module.OpenProcess = Mock(return_value="process-handle")
        win32api_module.CloseHandle = Mock()

        with patch.dict(
            sys.modules,
            {
                "uiautomation": uia_module,
                "win32gui": win32gui_module,
                "win32process": win32process_module,
                "win32api": win32api_module,
            },
        ), patch.object(os, "getpid", return_value=19520):
            data = WindowsUIAccessibilityTextSource()._fetch_focused_control_via_uia()

        self.assertTrue(data["metadata"]["uia_focus_is_self"])
        self.assertFalse(data["metadata"]["foreground_is_self"])
        self.assertEqual(data["metadata"]["foreground_identity"], "pid:4321")
        self.assertEqual(data["metadata"]["uia_control_name"], "happy")
        self.assertEqual(data["text"], "")
        self.assertFalse(data["is_editable"])
        focused.GetPattern.assert_not_called()
        win32api_module.OpenProcess.assert_called_once_with(0x1000, False, 4321)

    def test_uia_child_without_hwnd_keeps_foreground_executable_identity(self):
        """A UIA ListItem with no HWND must not be mistaken for the foreground application."""
        import sys
        import types
        from unittest.mock import Mock, patch
        from core.monitoring.capture import WindowsUIAccessibilityTextSource

        focused = Mock()
        focused.ControlTypeName = "ListItemControl"
        focused.Name = "Recent document"
        focused.ClassName = ""
        focused.ProcessId = 4321
        focused.NativeWindowHandle = 0
        focused.AutomationId = "recent-document"
        focused.GetPattern.return_value = None

        uia_module = types.ModuleType("uiautomation")
        uia_module.GetFocusedControl = Mock(return_value=focused)
        uia_module.PatternId = types.SimpleNamespace(
            ValuePattern=1,
            TextPattern=2,
            TextPattern2=3,
            LegacyIAccessiblePattern=4,
        )

        win32gui_module = types.ModuleType("win32gui")
        win32gui_module.GetForegroundWindow = Mock(return_value=100)
        win32process_module = types.ModuleType("win32process")
        win32process_module.GetWindowThreadProcessId = Mock(return_value=(10, 4321))
        win32process_module.GetModuleFileNameEx = Mock(return_value="C:\\Windows\\System32\\notepad.exe")
        win32api_module = types.ModuleType("win32api")
        win32api_module.OpenProcess = Mock(return_value="process-handle")
        win32api_module.CloseHandle = Mock()

        with patch.dict(
            sys.modules,
            {
                "uiautomation": uia_module,
                "win32gui": win32gui_module,
                "win32process": win32process_module,
                "win32api": win32api_module,
            },
        ):
            data = WindowsUIAccessibilityTextSource()._fetch_focused_control_via_uia()

        self.assertEqual(data["control_type"], "ListItemControl")
        self.assertEqual(data["app_name"], "notepad.exe")
        self.assertEqual(data["metadata"]["foreground_hwnd"], 100)
        self.assertEqual(data["metadata"]["foreground_process_id"], 4321)
        self.assertEqual(data["metadata"]["foreground_identity"], "pid:4321")
        self.assertEqual(data["metadata"]["uia_control_type"], "ListItemControl")
        win32api_module.OpenProcess.assert_any_call(0x1000, False, 4321)

    def test_gcoach_owned_foreground_window_is_marked_as_internal(self):
        """A foreground HWND owned by this process is identified without querying popup UIA focus."""
        import os
        import sys
        import types
        from unittest.mock import Mock, patch
        from core.monitoring.capture import WindowsUIAccessibilityTextSource

        uia_module = types.ModuleType("uiautomation")
        uia_module.GetFocusedControl = Mock(side_effect=AssertionError("must not inspect G-Coach popup controls"))

        win32gui_module = types.ModuleType("win32gui")
        win32gui_module.GetForegroundWindow = Mock(return_value=33162584)
        win32process_module = types.ModuleType("win32process")
        win32process_module.GetWindowThreadProcessId = Mock(return_value=(10, 19520))
        win32process_module.GetModuleFileNameEx = Mock(return_value="C:\\Python\\python.exe")
        win32api_module = types.ModuleType("win32api")
        win32api_module.OpenProcess = Mock(return_value="process-handle")
        win32api_module.CloseHandle = Mock()

        with patch.dict(
            sys.modules,
            {
                "uiautomation": uia_module,
                "win32gui": win32gui_module,
                "win32process": win32process_module,
                "win32api": win32api_module,
            },
        ), patch.object(os, "getpid", return_value=19520):
            data = WindowsUIAccessibilityTextSource()._fetch_focused_control_via_uia()

        self.assertTrue(data["metadata"]["foreground_is_self"])
        self.assertEqual(data["metadata"]["foreground_identity"], "pid:19520")
        self.assertEqual(data["metadata"]["foreground_hwnd"], 33162584)
        self.assertFalse(data["is_editable"])
        self.assertEqual(data["app_name"], "python.exe")
        uia_module.GetFocusedControl.assert_not_called()

    def test_run_on_monitor_thread_executes_command_on_owner_thread(self):
        self.monitor.start()
        try:
            owner_thread_id = self.monitor._monitor_thread.ident
            result_thread_id = self.monitor.run_on_monitor_thread(threading.get_ident)
            self.assertEqual(result_thread_id, owner_thread_id)
        finally:
            self.monitor.stop()

    def test_run_on_monitor_thread_propagates_callback_errors(self):
        self.monitor.start()
        try:
            with self.assertRaisesRegex(ValueError, "expected monitor failure"):
                self.monitor.run_on_monitor_thread(
                    lambda: (_ for _ in ()).throw(ValueError("expected monitor failure"))
                )
        finally:
            self.monitor.stop()

    def test_run_on_monitor_thread_refuses_when_stopped(self):
        with self.assertRaisesRegex(RuntimeError, "monitor thread is not running"):
            self.monitor.run_on_monitor_thread(lambda: "must not run")

    def test_text_source_thread_lifecycle_stays_on_monitor_thread(self):
        class ThreadBoundSource(MockTextSource):
            def __init__(self):
                super().__init__(initial_text="thread-bound")
                self.initialized_on = None
                self.uninitialized_on = None

            def initialize_for_current_thread(self):
                self.initialized_on = threading.get_ident()

            def uninitialize_for_current_thread(self):
                self.uninitialized_on = threading.get_ident()

            def get_current_text(self):
                if self.initialized_on != threading.get_ident():
                    raise RuntimeError("text source used from a non-owner thread")
                return super().get_current_text()

        source = ThreadBoundSource()
        monitor = LiveTextMonitor(source, self.pipeline, self.resolver, poll_interval=0.01)
        monitor.start()
        try:
            self.assertIsNotNone(monitor.run_on_monitor_thread(threading.get_ident))
        finally:
            monitor.stop()

        self.assertIsNotNone(source.initialized_on)
        self.assertEqual(source.uninitialized_on, source.initialized_on)

    def test_text_change_detection_and_debounce(self):
        self.monitor.start()
        
        # 修改文本
        self.text_source.set_text("This has error text")
        
        # 立即触发检查，应识别变化并进入 waiting 状态
        state = self.monitor.trigger_check()
        self.assertEqual(state.status, "waiting")
        self.assertEqual(state.generation, 1)
        self.assertEqual(state.text, "This has error text")

        # 等待超过 debounce 间隔 (0.1s) 及异步分析完成
        time.sleep(0.3)

        state_ready = self.monitor.get_state()
        self.assertEqual(state_ready.status, "ready")
        self.assertEqual(state_ready.generation, 1)
        self.assertEqual(len(state_ready.findings), 1)
        self.assertEqual(state_ready.findings[0].original, "error")

    def test_stale_result_protection(self):
        """测试过期结果保护：当新一代文本在旧分析完成前到达时，旧分析结果被丢弃"""
        # 使用一个带有延迟的引擎来模拟慢速分析
        slow_pipeline = AnalysisPipeline()
        slow_pipeline.register_engine(DummyAnalysisEngine(name="slow", delay=0.2))
        
        slow_monitor = LiveTextMonitor(
            text_source=self.text_source,
            pipeline=slow_pipeline,
            resolver=self.resolver,
            debounce_interval=0.05,
            poll_interval=0.01,
        )
        slow_monitor.start()

        try:
            # 1. 设置第一代有错误的文本
            self.text_source.set_text("first error")
            slow_monitor.trigger_check()
            time.sleep(0.08)  # 等待 debounce 触发分析（代数 1 开始慢速分析）

            # 2. 立即设置第二代文本（打断并递增代数到 2）
            self.text_source.set_text("second clean")
            slow_monitor.trigger_check()

            # 等待足够时间让第一代的慢速分析完成
            time.sleep(0.3)

            state = slow_monitor.get_state()
            # 代数应该是 2（对应 "second clean"），且由于第一代已过期，不应该含有 "first error" 的 finding
            self.assertEqual(state.generation, 2)
            self.assertEqual(state.text, "second clean")
            self.assertEqual(state.findings, [])
        finally:
            slow_monitor.stop()

    def test_rapid_sequence_of_text_changes(self):
        """测试快速连续输入不会导致无限线程膨胀或结果混乱"""
        self.monitor.start()

        for i in range(5):
            self.text_source.set_text(f"rapid text update {i}")
            self.monitor.trigger_check()
            time.sleep(0.02)

        # 等待最后一次静止后分析完成
        time.sleep(0.3)

        state = self.monitor.get_state()
        self.assertEqual(state.generation, 5)
        self.assertEqual(state.text, "rapid text update 4")

    def test_unchanged_text_does_not_reanalyze(self):
        self.monitor.start()
        self.text_source.set_text("stable text")
        self.monitor.trigger_check()
        time.sleep(0.2)
        
        gen_before = self.monitor.get_state().generation
        
        # 再次轮询相同文本
        self.monitor.trigger_check()
        gen_after = self.monitor.get_state().generation
        self.assertEqual(gen_before, gen_after)

    def test_unsupported_text_source_handled_gracefully(self):
        unsupported_source = MockTextSource(status="unsupported")
        monitor = LiveTextMonitor(
            text_source=unsupported_source,
            pipeline=self.pipeline,
            resolver=self.resolver,
        )
        state = monitor.trigger_check()
        self.assertEqual(state.status, "unsupported")

    def test_unsupported_target_invalidates_inflight_analysis_and_recovers(self):
        """Unavailable focus must not publish stale findings and must recover on return."""
        analysis_started = threading.Event()
        release_analysis = threading.Event()

        class BlockingEngine(DummyAnalysisEngine):
            def analyze(self, text):
                analysis_started.set()
                release_analysis.wait(timeout=2.0)
                return super().analyze(text)

        pipeline = AnalysisPipeline()
        pipeline.register_engine(BlockingEngine())
        source = MockTextSource(initial_text="This has error text")
        monitor = LiveTextMonitor(
            text_source=source,
            pipeline=pipeline,
            resolver=self.resolver,
            debounce_interval=0.0,
        )

        try:
            self.assertEqual(monitor.trigger_check().status, "waiting")
            monitor.trigger_check()  # Start the asynchronous analysis.
            self.assertTrue(analysis_started.wait(timeout=1.0))

            source.is_editable = False
            source.status = "unsupported"
            unavailable = monitor.trigger_check()
            self.assertEqual(unavailable.status, "unsupported")
            self.assertEqual(unavailable.findings, [])
            self.assertEqual(unavailable.text, "")
            self.assertIsNotNone(unavailable.error_message)
            unavailable_generation = unavailable.generation

            # Let the old analysis finish; it must not overwrite the unavailable state.
            release_analysis.set()
            time.sleep(0.05)
            after_stale_completion = monitor.get_state()
            self.assertEqual(after_stale_completion.status, "unsupported")
            self.assertEqual(after_stale_completion.generation, unavailable_generation)
            self.assertEqual(after_stale_completion.findings, [])

            # Returning to the same control with identical text is still a new context.
            source.is_editable = True
            source.status = "ready"
            recovered = monitor.trigger_check()
            self.assertEqual(recovered.status, "waiting")
            self.assertGreater(recovered.generation, unavailable_generation)
            self.assertIsNone(recovered.error_message)

            deadline = time.monotonic() + 1.0
            while monitor.get_state().status != "ready" and time.monotonic() < deadline:
                monitor.trigger_check()
                time.sleep(0.01)

            ready = monitor.get_state()
            self.assertEqual(ready.status, "ready")
            self.assertEqual(ready.text, "This has error text")
            self.assertEqual(len(ready.findings), 1)
        finally:
            release_analysis.set()
            monitor.stop()

    def test_capture_error_invalidates_previous_context_and_recovers(self):
        """A transient source exception clears stale data and does not wedge monitoring."""
        class IntermittentSource(MockTextSource):
            fail = False

            def get_current_text(self):
                if self.fail:
                    raise RuntimeError("temporary capture failure")
                return super().get_current_text()

        source = IntermittentSource(initial_text="Stable text")
        monitor = LiveTextMonitor(
            text_source=source,
            pipeline=self.pipeline,
            resolver=self.resolver,
            debounce_interval=0.0,
        )

        initial = monitor.trigger_check()
        self.assertEqual(initial.status, "waiting")
        source.fail = True
        failed = monitor.trigger_check()
        self.assertEqual(failed.status, "error")
        self.assertEqual(failed.text, "")
        self.assertEqual(failed.findings, [])
        self.assertEqual(failed.error_message, "temporary capture failure")

        source.fail = False
        recovered = monitor.trigger_check()
        self.assertEqual(recovered.status, "waiting")
        self.assertEqual(recovered.text, "Stable text")
        self.assertGreater(recovered.generation, failed.generation)
        self.assertIsNone(recovered.error_message)

        deadline = time.monotonic() + 1.0
        while monitor.get_state().status != "ready" and time.monotonic() < deadline:
            monitor.trigger_check()
            time.sleep(0.01)
        self.assertEqual(monitor.get_state().status, "ready")
        self.assertIsNone(monitor.get_state().error_message)

    def test_analysis_failure_does_not_trigger_repeated_automatic_retries(self):
        """An analysis error must not masquerade as loss of the editor context."""
        class RaisingPipeline:
            def __init__(self):
                self.calls = 0
                self.finished = threading.Event()

            def analyze(self, text):
                self.calls += 1
                self.finished.set()
                raise RuntimeError("analysis backend unavailable")

        pipeline = RaisingPipeline()
        monitor = LiveTextMonitor(
            text_source=MockTextSource(initial_text="Stable editor text"),
            pipeline=pipeline,
            resolver=self.resolver,
            debounce_interval=0.01,
            poll_interval=0.005,
        )
        monitor.start()
        try:
            self.assertTrue(pipeline.finished.wait(timeout=1.0))
            deadline = time.monotonic() + 1.0
            while monitor.get_state().status != "error" and time.monotonic() < deadline:
                time.sleep(0.005)
            state = monitor.get_state()
            self.assertEqual(state.status, "error")
            self.assertEqual(state.error_message, "analysis backend unavailable")
            generation = state.generation

            # Several further polls of the same editor must not keep spawning
            # failing workers. A user-triggered force_recheck remains available.
            time.sleep(0.1)
            state_after_polls = monitor.get_state()
            self.assertEqual(pipeline.calls, 1)
            self.assertEqual(state_after_polls.generation, generation)
            self.assertEqual(state_after_polls.status, "error")
        finally:
            monitor.stop()

    def test_analysis_exception_does_not_crash_monitor(self):
        failing_pipeline = AnalysisPipeline()
        failing_pipeline.register_engine(FailingAnalysisEngine())

        monitor = LiveTextMonitor(
            text_source=self.text_source,
            pipeline=failing_pipeline,
            resolver=self.resolver,
            debounce_interval=0.01,
            poll_interval=0.01,
        )
        monitor.start()
        try:
            self.text_source.set_text("some text with error")
            monitor.trigger_check()
            time.sleep(0.1)

            state = monitor.get_state()
            # Pipeline safely isolates engine exceptions and returns empty findings, keeping monitor running ("ready")
            self.assertEqual(state.status, "ready")
            self.assertEqual(state.findings, [])
        finally:
            monitor.stop()

    def test_shutdown_and_cleanup(self):
        self.monitor.start()
        self.assertTrue(self.monitor._is_running)
        self.monitor.stop()
        self.assertFalse(self.monitor._is_running)

    def test_control_switching_isolates_context(self):
        """测试当聚焦控件切换时，LiveTextMonitor 自动隔离旧 findings 并不混淆文本"""
        controls = [
            {"control_id": "ctrl-1", "app_name": "App1", "text": "This has error text", "is_editable": True},
            {"control_id": "ctrl-2", "app_name": "App2", "text": "Clean text in app two", "is_editable": True},
        ]
        multi_source = MultiControlMockTextSource(controls)
        
        monitor = LiveTextMonitor(
            text_source=multi_source,
            pipeline=self.pipeline,
            resolver=self.resolver,
            debounce_interval=0.05,
            poll_interval=0.01,
        )
        monitor.start()
        try:
            # 1. 触发 ctrl-1 分析出 finding
            monitor.trigger_check()
            time.sleep(0.08)
            state1 = monitor.get_state()
            self.assertEqual(state1.status, "ready")
            self.assertEqual(len(state1.findings), 1)
            self.assertEqual(state1.control_id, "ctrl-1")

            # 2. 切换到 ctrl-2 (具有干净文本)
            multi_source.select_control(1)
            state_switched = monitor.trigger_check()
            # 切换控件时应立即进入 waiting 状态并清空旧 findings
            self.assertEqual(state_switched.status, "waiting")
            self.assertEqual(state_switched.control_id, "ctrl-2")
            self.assertEqual(state_switched.findings, [])

            # 等待 ctrl-2 分析完成
            time.sleep(0.08)
            state2 = monitor.get_state()
            self.assertEqual(state2.status, "ready")
            self.assertEqual(state2.control_id, "ctrl-2")
            self.assertEqual(state2.findings, [])
        finally:
            monitor.stop()

    def test_empty_text_clears_findings(self):
        """测试当文本变为空时，不触发多余分析并立即清除旧 findings"""
        self.text_source.set_text("This has error text")
        self.monitor.start()
        try:
            self.monitor.trigger_check()
            deadline = time.monotonic() + 2.0
            state1 = self.monitor.get_state()
            while state1.status != "ready" and time.monotonic() < deadline:
                time.sleep(0.01)
                state1 = self.monitor.get_state()
            self.assertEqual(len(state1.findings), 1)

            # 文本变为空
            self.text_source.set_text("")
            state_empty = self.monitor.trigger_check()
            self.assertEqual(state_empty.status, "ready")
            self.assertEqual(state_empty.text, "")
            self.assertEqual(state_empty.findings, [])
        finally:
            self.monitor.stop()

    def test_non_editable_control_ignored(self):
        """测试不可编辑控件不触发分析且保持监控状态"""
        readonly_source = MockTextSource(initial_text="some text", is_editable=False, status="unsupported")
        monitor = LiveTextMonitor(
            text_source=readonly_source,
            pipeline=self.pipeline,
            resolver=self.resolver,
        )
        state = monitor.trigger_check()
        self.assertEqual(state.status, "unsupported")
        self.assertEqual(state.findings, [])

    def test_phase_8c_application_switching_scenarios(self):
        """测试 Phase 8C 应用程序/控件切换硬化要求：
        1. 多应用/多控件循环切换 (Telegram → ChatGPT → Firefox → Telegram) 隔离 findings
        2. 快速切换 (Rapid switching) 期间旧分析结果被生成保护(stale result protection)正确丢弃
        3. 同一应用内不同控件 (Same app, different controls) 身份区分
        4. 切换回曾使用过的控件保留或重新分析上下文
        5. 空文本/非可编辑控件转入与切出处理
        """
        controls = [
            {"control_id": "ctrl-tg", "app_name": "Telegram", "text": "This has error text", "is_editable": True},
            {"control_id": "ctrl-gpt", "app_name": "ChatGPT", "text": "Clean text here", "is_editable": True},
            {"control_id": "ctrl-ff", "app_name": "Firefox", "text": "Another error text", "is_editable": True},
        ]
        multi_source = MultiControlMockTextSource(controls)

        monitor = LiveTextMonitor(
            text_source=multi_source,
            pipeline=self.pipeline,
            resolver=self.resolver,
            debounce_interval=0.03,
            poll_interval=0.01,
        )
        monitor.start()
        try:
            # 1. Telegram (ctrl-tg) 触发分析
            monitor.trigger_check()
            time.sleep(0.06)
            state_tg1 = monitor.get_state()
            self.assertEqual(state_tg1.control_id, "ctrl-tg")
            self.assertEqual(state_tg1.status, "ready")
            self.assertEqual(len(state_tg1.findings), 1)

            # 2. 切换到 ChatGPT (ctrl-gpt，干净文本)
            multi_source.select_control(1)
            state_gpt = monitor.trigger_check()
            self.assertEqual(state_gpt.control_id, "ctrl-gpt")
            self.assertEqual(state_gpt.status, "waiting")
            self.assertEqual(state_gpt.findings, [], "Telegram findings must not leak to ChatGPT")

            time.sleep(0.05)
            state_gpt_ready = monitor.get_state()
            self.assertEqual(state_gpt_ready.control_id, "ctrl-gpt")
            self.assertEqual(state_gpt_ready.status, "ready")
            self.assertEqual(state_gpt_ready.findings, [])

            # 3. 切换到 Firefox (ctrl-ff)
            multi_source.select_control(2)
            state_ff = monitor.trigger_check()
            self.assertEqual(state_ff.control_id, "ctrl-ff")
            self.assertEqual(state_ff.findings, [])

            # 4. 再次切回 Telegram (ctrl-tg)
            multi_source.select_control(0)
            state_tg_back = monitor.trigger_check()
            self.assertEqual(state_tg_back.control_id, "ctrl-tg")
            # 切换控件时应当先清理上一控件状态进入 waiting
            self.assertEqual(state_tg_back.findings, [])

            time.sleep(0.06)
            state_tg_final = monitor.get_state()
            self.assertEqual(state_tg_final.control_id, "ctrl-tg")
            self.assertEqual(state_tg_final.status, "ready")
            self.assertEqual(len(state_tg_final.findings), 1)

        finally:
            monitor.stop()

    def test_phase_8c_rapid_switching_stale_protection(self):
        """测试 Phase 8C 快速切换时的过期结果保护 (Stale Result Protection)"""
        controls = [
            {"control_id": "ctrl-a", "app_name": "AppA", "text": "error text in a", "is_editable": True},
            {"control_id": "ctrl-b", "app_name": "AppB", "text": "clean text in b", "is_editable": True},
        ]
        multi_source = MultiControlMockTextSource(controls)

        # 调大防抖时间以便在分析排队时有时间切换控件
        monitor = LiveTextMonitor(
            text_source=multi_source,
            pipeline=self.pipeline,
            resolver=self.resolver,
            debounce_interval=0.02,
            poll_interval=0.01,
        )
        monitor.start()
        try:
            # 触发 AppA
            monitor.trigger_check()
            # 在防抖倒计时期间立即切换到 AppB
            time.sleep(0.01)
            multi_source.select_control(1)
            state_switched = monitor.trigger_check()
            self.assertEqual(state_switched.control_id, "ctrl-b")
            
            # 等待足够时间让异步或防抖完成
            time.sleep(0.08)
            state_b = monitor.get_state()
            self.assertEqual(state_b.control_id, "ctrl-b")
            self.assertEqual(state_b.findings, [], "AppA analysis result must not overwrite AppB state")
        finally:
            monitor.stop()



    def test_metadata_survival_without_thread_bound_uia_objects(self):
        """普通控件元数据可传递，但 CorrectionTarget 不保留线程绑定的 UIA 对象。"""
        class CustomMockSource(MockTextSource):
            def get_current_text(self):
                from core.monitoring import TextSnapshot
                return TextSnapshot(
                    text="hello metadata",
                    control_id="ctrl-meta-1",
                    status="ready",
                    is_editable=True,
                    metadata={"hwnd": 9999, "automation_id": "meta-editor", "control_name": "Metadata editor"}
                )

        source = CustomMockSource()
        monitor = LiveTextMonitor(
            text_source=source,
            pipeline=self.pipeline,
            resolver=self.resolver,
        )
        state = monitor.trigger_check()
        self.assertEqual(state.text, "hello metadata")
        self.assertEqual(state.metadata["hwnd"], 9999)

        # The target carries only stable identity data; no COM Control is retained.
        from core.correction.target import CorrectionTarget
        target = CorrectionTarget.from_snapshot(state)
        self.assertEqual(target.hwnd, 9999)
        self.assertEqual(target.automation_id, "meta-editor")
        self.assertEqual(target.control_name, "Metadata editor")
        self.assertFalse(hasattr(target, "element_ref"))


if __name__ == "__main__":
    unittest.main()
