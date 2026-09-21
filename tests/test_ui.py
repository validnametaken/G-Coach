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
        """测试 Phase 8E 浮动纠正弹窗与 GCoachWindow 的集成逻辑（确定性轮询同步）"""
        from core.ui.window import PYQT_AVAILABLE
        if not PYQT_AVAILABLE:
            return

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

        window = GCoachWindow(monitor)
        try:
            monitor.start()
            import time
            start_time = time.time()
            # 确定性同步等待直到 monitor 状态变为 ready 且包含 findings，或超时 (2.0s)
            while time.time() - start_time < 2.0:
                window._poll_monitor_state()
                if window.monitor.get_state().status == "ready" and window.current_findings:
                    break
                time.sleep(0.05)

            # 验证 findings 出现时弹窗是否被正确同步创建
            self.assertIsNotNone(window.active_popup)
            self.assertEqual(window.last_popup_finding_id, window.current_findings[0].id)

            # 验证点击 Ignore 可以关闭弹窗
            finding = window.current_findings[0]
            window._handle_popup_ignore(finding)
            self.assertIsNone(window.active_popup)
            self.assertIsNone(window.last_popup_finding_id)
        finally:
            window.close()
            monitor.stop()


if __name__ == "__main__":
    unittest.main()
