"""
Unit tests for Phase 4 Analysis Resolution Layer
"""

import unittest
from core.analysis import Finding, AnalysisResolver


class TestAnalysisResolver(unittest.TestCase):
    """测试 Analysis Resolver 的消解、合并、冲突标记与确定性排序功能"""

    def setUp(self):
        self.resolver = AnalysisResolver()

    def test_empty_input(self):
        self.assertEqual(self.resolver.resolve([]), [])
        self.assertEqual(self.resolver.resolve(None), [])

    def test_single_finding_harper(self):
        f = Finding(
            source="harper",
            category="grammar",
            message="Verb agreement error",
            original="go",
            replacement="goes",
            start=4,
            end=6,
            confidence=1.0,
        )
        resolved = self.resolver.resolve([f])
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].source, "harper")
        self.assertEqual(resolved[0].metadata["sources"], ["harper"])
        self.assertFalse(resolved[0].metadata["is_merged"])
        self.assertFalse(resolved[0].metadata["has_conflict"])

    def test_single_finding_gector(self):
        f = Finding(
            source="gector",
            category="subject_verb_agreement",
            message="Agreement error",
            original="go",
            replacement="goes",
            start=4,
            end=6,
            confidence=0.95,
        )
        resolved = self.resolver.resolve([f])
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].source, "gector")
        self.assertEqual(resolved[0].metadata["sources"], ["gector"])

    def test_identical_findings_merge(self):
        """测试 Harper 和 GECToR 报告完全相同的修正时合并为一个 finding"""
        f_harper = Finding(
            source="harper",
            category="grammar",
            message="Agreement error",
            original="go",
            replacement="goes",
            start=4,
            end=6,
            confidence=1.0,
        )
        f_gector = Finding(
            source="gector",
            category="subject_verb_agreement",
            message="Subject verb agreement",
            original="go",
            replacement="goes",
            start=4,
            end=6,
            confidence=0.96,
        )

        resolved = self.resolver.resolve([f_harper, f_gector])
        self.assertEqual(len(resolved), 1)
        res = resolved[0]
        self.assertTrue(res.metadata["is_merged"])
        self.assertFalse(res.metadata["has_conflict"])
        self.assertIn("harper", res.metadata["sources"])
        self.assertIn("gector", res.metadata["sources"])
        self.assertEqual(res.metadata["source_confidences"]["harper"], 1.0)
        self.assertEqual(res.metadata["source_confidences"]["gector"], 0.96)

    def test_same_location_different_replacement_conflict(self):
        """测试相同位置但不同替换方案时标记冲突"""
        f_harper = Finding(
            source="harper",
            category="grammar",
            message="Agreement error",
            original="go",
            replacement="goes",
            start=4,
            end=6,
            confidence=1.0,
        )
        f_gector = Finding(
            source="gector",
            category="verb_form",
            message="Past tense suggestion",
            original="go",
            replacement="went",
            start=4,
            end=6,
            confidence=0.85,
        )

        resolved = self.resolver.resolve([f_harper, f_gector])
        # 应该保留冲突的候选项
        self.assertGreaterEqual(len(resolved), 2)
        for res in resolved:
            self.assertTrue(res.metadata["has_conflict"])
            self.assertFalse(res.metadata["is_merged"])
            self.assertIn("conflicting_findings", res.metadata)

    def test_non_overlapping_findings(self):
        """测试不重叠的 findings 独立保留"""
        f1 = Finding(
            source="harper",
            category="article",
            message="Missing article",
            original="apple",
            replacement="an apple",
            start=10,
            end=15,
            confidence=1.0,
        )
        f2 = Finding(
            source="gector",
            category="verb_form",
            message="Verb form error",
            original="go",
            replacement="goes",
            start=4,
            end=6,
            confidence=0.95,
        )

        resolved = self.resolver.resolve([f1, f2])
        self.assertEqual(len(resolved), 2)
        # 验证确定性排序（按 start 升序）
        self.assertEqual(resolved[0].start, 4)
        self.assertEqual(resolved[1].start, 10)

    def test_duplicate_findings_from_same_source(self):
        """测试来自同一引擎的重复 findings"""
        f1 = Finding(
            source="harper",
            category="grammar",
            message="Error",
            original="go",
            replacement="goes",
            start=4,
            end=6,
            confidence=1.0,
        )
        f2 = Finding(
            source="harper",
            category="grammar",
            message="Error",
            original="go",
            replacement="goes",
            start=4,
            end=6,
            confidence=1.0,
        )

        resolved = self.resolver.resolve([f1, f2])
        self.assertEqual(len(resolved), 1)

    def test_findings_with_no_replacement(self):
        """测试没有替换文本（如纯删除或警告）的 findings"""
        f = Finding(
            source="harper",
            category="style",
            message="Wordy expression",
            original="very",
            replacement="",
            start=2,
            end=6,
            confidence=0.8,
        )
        resolved = self.resolver.resolve([f])
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].replacement, "")

    def test_different_categories_equivalent_corrections(self):
        """测试不同类别但等价替换的 findings"""
        f1 = Finding(
            source="harper",
            category="grammar",
            message="Msg 1",
            original="go",
            replacement="goes",
            start=4,
            end=6,
            confidence=1.0,
        )
        f2 = Finding(
            source="gector",
            category="subject_verb_agreement",
            message="Msg 2",
            original="go",
            replacement=" goes ",
            start=4,
            end=6,
            confidence=0.9,
        )

        resolved = self.resolver.resolve([f1, f2])
        self.assertEqual(len(resolved), 1)
        self.assertTrue(resolved[0].metadata["is_merged"])

    def test_finding_serialization_with_resolution_metadata(self):
        """测试带有消解元数据的 Finding 序列化与反序列化"""
        f1 = Finding(
            source="harper",
            category="grammar",
            message="Agreement",
            original="go",
            replacement="goes",
            start=4,
            end=6,
            confidence=1.0,
        )
        f2 = Finding(
            source="gector",
            category="agreement",
            message="Agreement",
            original="go",
            replacement="goes",
            start=4,
            end=6,
            confidence=0.98,
        )
        resolved = self.resolver.resolve([f1, f2])
        d = resolved[0].to_dict()
        restored = Finding.from_dict(d)
        self.assertEqual(resolved[0], restored)
        self.assertTrue(restored.metadata["is_merged"])


if __name__ == "__main__":
    unittest.main()
