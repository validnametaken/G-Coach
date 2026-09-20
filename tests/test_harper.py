"""
Unit tests for Phase 2 Harper Local Analysis Engine
"""

import time
import unittest
from core.analysis import Finding, BaseAnalysisEngine, AnalysisPipeline, HarperAnalysisEngine


class TestHarperAnalysisEngine(unittest.TestCase):
    """测试 HarperAnalysisEngine 的各项功能与边界情况"""

    @classmethod
    def setUpClass(cls):
        cls.engine = HarperAnalysisEngine()

    def test_engine_metadata(self):
        self.assertEqual(self.engine.name, "harper")
        self.assertEqual(self.engine.version, "0.1.0")
        self.assertTrue(self.engine.is_local)
        self.assertTrue(self.engine.supports_auto_fix)
        self.assertIn("grammar", self.engine.supported_types)

        meta = self.engine.get_metadata()
        self.assertEqual(meta["name"], "harper")
        self.assertTrue(meta["is_local"])

    def test_empty_and_whitespace_text(self):
        self.assertEqual(self.engine.analyze(""), [])
        self.assertEqual(self.engine.analyze("   \n\t "), [])

    def test_clean_grammatical_text(self):
        findings = self.engine.analyze("I went to school yesterday.")
        # 正确的句子通常没有问题或 findings 很少
        self.assertIsInstance(findings, list)

    def test_grammar_issue_subject_verb_agreement(self):
        findings = self.engine.analyze("She go to school.")
        self.assertGreaterEqual(len(findings), 1)
        
        # 验证至少有一个 Finding 检测到动词不一致
        found = False
        for f in findings:
            self.assertEqual(f.source, "harper")
            self.assertIsInstance(f.id, str)
            self.assertEqual(f.confidence, 1.0) # 确定性规则引擎置信度为 1.0
            if f.original == "go" and f.replacement == "goes":
                found = True
                self.assertEqual(f.start, 4)
                self.assertEqual(f.end, 6)
                # 验证文本切片匹配
                self.assertEqual("She go to school."[f.start:f.end], f.original)
                self.assertTrue(f.auto_fixable)
        self.assertTrue(found, "Expected finding 'go' -> 'goes' not found")

    def test_multiple_grammar_issues(self):
        findings = self.engine.analyze("She go and they was happy.")
        self.assertGreaterEqual(len(findings), 1)
        for f in findings:
            self.assertEqual(f.source, "harper")
            self.assertTrue(0 <= f.start <= f.end <= len("She go and they was happy."))
            self.assertEqual("She go and they was happy."[f.start:f.end], f.original)

    def test_unicode_and_apostrophes(self):
        text = "It's a beautiful day, isn't it?"
        findings = self.engine.analyze(text)
        self.assertIsInstance(findings, list)
        for f in findings:
            self.assertEqual(text[f.start:f.end], f.original)

    def test_pipeline_integration_with_harper(self):
        pipeline = AnalysisPipeline()
        pipeline.register_engine(self.engine)

        findings = pipeline.analyze("She go to school.")
        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0].source, "harper")

    def test_pipeline_resilience_with_invalid_runner(self):
        bad_engine = HarperAnalysisEngine(runner_path="nonexistent_runner.js")
        pipeline = AnalysisPipeline()
        pipeline.register_engine(bad_engine)

        # 引擎失效不应导致管道崩溃
        findings = pipeline.analyze("She go to school.")
        self.assertEqual(findings, [])

    def test_finding_serialization_compatibility(self):
        findings = self.engine.analyze("She go to school.")
        if findings:
            f = findings[0]
            d = f.to_dict()
            f_restored = Finding.from_dict(d)
            self.assertEqual(f, f_restored)

    def test_performance_measurement(self):
        short_text = "She go to school."
        long_text = (
            "The quick brown fox jumps over the lazy dog. "
            "She go to store yesterday and buy a apple. "
            "They was very happy about the results."
        )

        start_time = time.time()
        res_short = self.engine.analyze(short_text)
        duration_short = time.time() - start_time

        start_time = time.time()
        res_long = self.engine.analyze(long_text)
        duration_long = time.time() - start_time

        print(f"\n[Performance] Short text ({len(short_text)} chars): {duration_short*1000:.2f} ms (findings: {len(res_short)})")
        print(f"[Performance] Long text ({len(long_text)} chars): {duration_long*1000:.2f} ms (findings: {len(res_long)})")

        self.assertLess(duration_short, 3.0, "Short text analysis took too long")
        self.assertLess(duration_long, 8.0, "Long text analysis took too long")


if __name__ == "__main__":
    unittest.main()
