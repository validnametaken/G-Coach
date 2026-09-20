"""
Unit tests for Phase 3 Gector Local Analysis Engine
"""

import time
import unittest
from core.analysis import Finding, BaseAnalysisEngine, AnalysisPipeline, GectorAnalysisEngine


class TestGectorAnalysisEngine(unittest.TestCase):
    """测试 GectorAnalysisEngine 的各项功能、置信度阈值、字符范围与管道集成"""

    @classmethod
    def setUpClass(cls):
        cls.engine = GectorAnalysisEngine()

    def test_engine_metadata(self):
        self.assertEqual(self.engine.name, "gector")
        self.assertEqual(self.engine.version, "0.1.0")
        self.assertTrue(self.engine.is_local)
        self.assertTrue(self.engine.supports_auto_fix)
        self.assertIn("grammar", self.engine.supported_types)

        meta = self.engine.get_metadata()
        self.assertEqual(meta["name"], "gector")
        self.assertTrue(meta["is_local"])

    def test_empty_and_whitespace_text(self):
        self.assertEqual(self.engine.analyze(""), [])
        self.assertEqual(self.engine.analyze("   \n\t "), [])

    def test_clean_text(self):
        findings = self.engine.analyze("I went there yesterday.")
        self.assertEqual(findings, [])

    def test_subject_verb_agreement_correction(self):
        text = "She go to school."
        findings = self.engine.analyze(text)
        self.assertGreaterEqual(len(findings), 1)
        
        f = findings[0]
        self.assertEqual(f.source, "gector")
        self.assertEqual(f.original, "go")
        self.assertEqual(f.replacement, "goes")
        self.assertEqual(f.start, 4)
        self.assertEqual(f.end, 6)
        self.assertEqual(text[f.start:f.end], f.original)
        self.assertTrue(0.0 <= f.confidence <= 1.0)
        self.assertIn("gector_label", f.metadata)

    def test_multiple_errors_correction(self):
        text = "I has a apple ."
        findings = self.engine.analyze(text)
        self.assertGreaterEqual(len(findings), 2)
        
        for f in findings:
            self.assertEqual(text[f.start:f.end], f.original)
            self.assertIsNotNone(f.replacement)

    def test_confidence_threshold_filtering(self):
        # 使用较高的阈值，测试低置信度过滤
        strict_engine = GectorAnalysisEngine(det_threshold=0.99, lab_threshold=0.99)
        findings = strict_engine.analyze("She go to school.")
        # 置信度小于 0.99 的应当被过滤
        self.assertEqual(findings, [])

    def test_pipeline_integration_with_multiple_engines(self):
        pipeline = AnalysisPipeline()
        # 同时注册 Harper 和 Gector
        from core.analysis import HarperAnalysisEngine
        pipeline.register_engine(HarperAnalysisEngine())
        pipeline.register_engine(self.engine)

        findings = pipeline.analyze("She go to school.")
        self.assertGreaterEqual(len(findings), 1)
        
        sources = {f.source for f in findings}
        # 验证两个引擎都能独立产出 findings，且未被合并或覆盖
        self.assertIn("harper", sources)
        self.assertIn("gector", sources)

    def test_finding_serialization(self):
        findings = self.engine.analyze("She go to school.")
        if findings:
            f = findings[0]
            d = f.to_dict()
            f_restored = Finding.from_dict(d)
            self.assertEqual(f, f_restored)

    def test_performance_measurement(self):
        text = "She go to school."
        start_time = time.time()
        findings = self.engine.analyze(text)
        duration = time.time() - start_time

        print(f"\n[Performance] Gector analysis duration: {duration*1000:.2f} ms (findings: {len(findings)})")
        self.assertLess(duration, 3.0)


if __name__ == "__main__":
    unittest.main()
