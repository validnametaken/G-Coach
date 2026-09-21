"""
Unit tests for G-Coach Interactive Corrections - Phase 7
"""

import unittest
from core.analysis import Finding
from core.correction import CorrectionController, CorrectionResult


class TestCorrectionController(unittest.TestCase):
    """测试 CorrectionController 的各项交互式修正功能"""

    def setUp(self):
        self.controller = CorrectionController()

    def test_simple_replacement(self):
        """测试简单的文本替换 (Accept)"""
        text = "The students was happy."
        finding = Finding(
            source="harper",
            category="grammar",
            message="Subject-verb agreement error",
            original="was",
            replacement="were",
            start=13,
            end=16,
        )
        result = self.controller.apply_acceptance(text, finding)
        self.assertTrue(result.success)
        self.assertEqual(result.new_text, "The students were happy.")
        self.assertEqual(finding.status, "accepted")

    def test_repeated_words_replacement(self):
        """测试重复单词中仅替换指定范围的情况"""
        text = "test test test"
        # 替换第二个 "test" (范围 [5:9])
        finding = Finding(
            source="harper",
            category="style",
            message="Repeated word",
            original="test",
            replacement="exam",
            start=5,
            end=9,
        )
        result = self.controller.apply_acceptance(text, finding)
        self.assertTrue(result.success)
        self.assertEqual(result.new_text, "test exam test")

    def test_deletion(self):
        """测试删除 (replacement 为空字符串)"""
        text = "Hello beautiful world"
        finding = Finding(
            source="harper",
            category="style",
            message="Redundant word",
            original="beautiful ",
            replacement="",
            start=6,
            end=16,
        )
        result = self.controller.apply_acceptance(text, finding)
        self.assertTrue(result.success)
        self.assertEqual(result.new_text, "Hello world")

    def test_insertion(self):
        """测试插入 (original 为空，start == end)"""
        text = "Hello world"
        finding = Finding(
            source="harper",
            category="style",
            message="Missing word",
            original="",
            replacement="wonderful ",
            start=6,
            end=6,
        )
        result = self.controller.apply_acceptance(text, finding)
        self.assertTrue(result.success)
        self.assertEqual(result.new_text, "Hello wonderful world")

    def test_range_validation_and_stale_rejection(self):
        """测试范围校验与过时 Finding 拒绝 (Stale Finding Rejection)"""
        text = "The students are happy."  # 已经改变了 ("was" 变成 "are")
        finding = Finding(
            source="harper",
            category="grammar",
            message="Subject-verb agreement error",
            original="was",
            replacement="were",
            start=13,
            end=16,
        )
        result = self.controller.apply_acceptance(text, finding)
        self.assertFalse(result.success)
        self.assertIn("Stale finding rejection", result.error_message)
        self.assertNotEqual(finding.status, "accepted")

    def test_boundary_and_invalid_offsets(self):
        """测试边界与非法偏移量"""
        text = "Short"
        # 越界
        finding = Finding(
            source="harper",
            category="grammar",
            message="Error",
            original="Short",
            replacement="Long",
            start=0,
            end=10,
        )
        result = self.controller.apply_acceptance(text, finding)
        self.assertFalse(result.success)
        self.assertIn("out of bounds", result.error_message)

        # 负数偏移
        finding2 = Finding(
            source="harper",
            category="grammar",
            message="Error",
            original="S",
            replacement="L",
            start=-1,
            end=2,
        )
        result2 = self.controller.apply_acceptance(text, finding2)
        self.assertFalse(result2.success)

    def test_empty_text(self):
        """测试空文本上的修正"""
        text = ""
        finding = Finding(
            source="harper",
            category="grammar",
            message="Error",
            original="",
            replacement="Hello",
            start=0,
            end=0,
        )
        result = self.controller.apply_acceptance(text, finding)
        self.assertTrue(result.success)
        self.assertEqual(result.new_text, "Hello")

    def test_ignore_and_reject_status(self):
        """测试忽略与拒绝 Finding 状态"""
        finding = Finding(
            source="harper",
            category="style",
            message="Suggestion",
            original="bad",
            replacement="good",
            start=0,
            end=3,
        )
        ignored = self.controller.mark_ignored(finding)
        self.assertEqual(ignored.status, "ignored")

        text = "bad text"
        result = self.controller.apply_acceptance(text, ignored)
        self.assertFalse(result.success)
        self.assertIn("status is 'ignored'", result.error_message)

        rejected = self.controller.mark_rejected(finding)
        self.assertEqual(rejected.status, "rejected")

    def test_conflict_refusal(self):
        """测试冲突 Finding 拒绝自动应用"""
        text = "She go to store."
        f1 = Finding(
            source="harper",
            category="grammar",
            message="Harper suggestion",
            original="go",
            replacement="goes",
            start=4,
            end=6,
            metadata={"has_conflict": True},
        )
        f2 = Finding(
            source="gector",
            category="grammar",
            message="Gector suggestion",
            original="go",
            replacement="went",
            start=4,
            end=6,
            metadata={"has_conflict": True},
        )
        all_findings = [f1, f2]

        result = self.controller.apply_acceptance(text, f1, all_findings=all_findings)
        self.assertFalse(result.success)
        self.assertIn("has conflicting alternative suggestions", result.error_message)


if __name__ == "__main__":
    unittest.main()
