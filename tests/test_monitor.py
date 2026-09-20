"""
Unit tests for LiveTextMonitor, debounce, generation tracking, and stale result protection - Phase 5
"""

import time
import unittest
from core.analysis import AnalysisPipeline, AnalysisResolver, Finding, BaseAnalysisEngine
from core.monitoring import MockTextSource, LiveTextMonitor


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


if __name__ == "__main__":
    unittest.main()
