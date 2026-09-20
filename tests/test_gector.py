"""
Unit tests for Phase 3 Gector Local Analysis Engine (Complete Real Inference & Simulation Fallback)
"""

import time
import unittest
from core.analysis import Finding, BaseAnalysisEngine, AnalysisPipeline, GectorAnalysisEngine


class TestGectorAnalysisEngine(unittest.TestCase):
    """测试 GectorAnalysisEngine 的各项功能、置信度阈值、字符范围、多测试样例与管道集成"""

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
        findings = self.engine.analyze("She goes to school every day.")
        self.assertEqual(findings, [])

    def test_test_case_students_was(self):
        text = "The students was very happy."
        findings = self.engine.analyze(text)
        self.assertGreaterEqual(len(findings), 1)
        
        f = findings[0]
        self.assertEqual(f.source, "gector")
        self.assertEqual(f.original, "was")
        self.assertEqual(f.replacement, "were")
        self.assertEqual(text[f.start:f.end], f.original)
        self.assertTrue(0.0 <= f.confidence <= 1.0)
        self.assertIn("gector_label", f.metadata)

    def test_test_case_she_go(self):
        text = "She go to school."
        findings = self.engine.analyze(text)
        self.assertGreaterEqual(len(findings), 1)
        
        f = findings[0]
        self.assertEqual(f.original, "go")
        self.assertEqual(f.replacement, "goes")
        self.assertEqual(text[f.start:f.end], f.original)
        self.assertTrue(0.0 <= f.confidence <= 1.0)

    def test_test_case_i_has_a_apple(self):
        text = "I has a apple."
        findings = self.engine.analyze(text)
        self.assertGreaterEqual(len(findings), 2)
        
        for f in findings:
            self.assertEqual(text[f.start:f.end], f.original)
            self.assertIsNotNone(f.replacement)
            self.assertTrue(0.0 <= f.confidence <= 1.0)

    def test_test_case_didnt_went(self):
        text = "He didn't went to school yesterday."
        findings = self.engine.analyze(text)
        self.assertGreaterEqual(len(findings), 1)
        
        f = findings[0]
        self.assertEqual(f.original, "went")
        self.assertEqual(f.replacement, "go")
        self.assertEqual(text[f.start:f.end], f.original)

    def test_confidence_threshold_filtering(self):
        strict_engine = GectorAnalysisEngine(det_threshold=0.99, lab_threshold=0.99)
        findings = strict_engine.analyze("She go to school.")
        self.assertEqual(findings, [])

    def test_pipeline_integration_with_multiple_engines(self):
        pipeline = AnalysisPipeline()
        from core.analysis import HarperAnalysisEngine
        pipeline.register_engine(HarperAnalysisEngine())
        pipeline.register_engine(self.engine)

        findings = pipeline.analyze("She go to school.")
        self.assertGreaterEqual(len(findings), 1)
        
        sources = {f.source for f in findings}
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


    def test_regression_real_label_mapping_55_replace_were(self):
        """测试对真实模型词表中索引 55 -> $REPLACE_were 的正确映射与解码回归"""
        # 验证词表解析能够正确加载并处理双向映射
        self.engine._id_to_label[55] = "$REPLACE_were"
        self.engine._label_to_id["$REPLACE_were"] = 55
        self.assertEqual(self.engine._id_to_label.get(55), "$REPLACE_were")
        self.assertEqual(self.engine._label_to_id.get("$REPLACE_were"), 55)

        text = "The students was very happy."
        findings = self.engine.analyze(text)
        self.assertGreaterEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f.original, "was")
        self.assertEqual(f.replacement, "were")
        self.assertEqual(f.start, 13)
        self.assertEqual(f.end, 16)

    def test_regression_transform_verb_vb_vbz(self):
        """测试 $TRANSFORM_VERB_VB_VBZ 能够正确将 go 转换为 goes 且不产生重复 findings"""
        self.engine._id_to_label[999] = "$TRANSFORM_VERB_VB_VBZ"
        self.engine._label_to_id["$TRANSFORM_VERB_VB_VBZ"] = 999
        
        # 测试动词转换函数本身
        res = self.engine._apply_transform_verb("go", "VB_VBZ")
        self.assertEqual(res, "goes")
        
        res_other = self.engine._apply_transform_verb("catch", "VB_VBZ")
        self.assertEqual(res_other, "catches")

        # 测试分析 clean text 不产生 findings
        clean_findings = self.engine.analyze("She goes to school every day.")
        self.assertEqual(clean_findings, [])

    def test_regression_transform_verb_vbd_vb(self):
        """测试 $TRANSFORM_VERB_VBD_VB 能够正确将 went 转换为 go（过去式还原为动词原形）"""
        self.engine._id_to_label[998] = "$TRANSFORM_VERB_VBD_VB"
        self.engine._label_to_id["$TRANSFORM_VERB_VBD_VB"] = 998

        # 测试反向动词转换函数本身
        res = self.engine._apply_transform_verb("went", "VBD_VB")
        self.assertEqual(res, "go")

        res_other = self.engine._apply_transform_verb("sat", "VBD_VB")
        self.assertEqual(res_other, "sit")

    def test_regression_transform_verb_comprehensive(self):
        """全面测试各种前向与反向动词转换标签（VB_VBZ, VBD_VB, VBZ_VB, VBG_VB 等）"""
        self.assertEqual(self.engine._apply_transform_verb("go", "VB_VBZ"), "goes")
        self.assertEqual(self.engine._apply_transform_verb("went", "VBD_VB"), "go")
        self.assertEqual(self.engine._apply_transform_verb("goes", "VBZ_VB"), "go")
        self.assertEqual(self.engine._apply_transform_verb("running", "VBG_VB"), "run")
        self.assertEqual(self.engine._apply_transform_verb("eaten", "VBN_VB"), "eat")

if __name__ == "__main__":
    unittest.main()
