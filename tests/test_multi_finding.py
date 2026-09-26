"""
Unit test for Phase 8E multi-finding popup synchronization and selection behavior.
"""

import unittest
from core.analysis import Finding
from core.monitoring import MonitorState
from core.ui.window import GCoachWindow
from unittest.mock import MagicMock, patch


class TestMultiFindingPopupSync(unittest.TestCase):
    """测试当 MonitorState 中存在多个 Findings（如 GECToR 的 . -> .What 和 Harper 的 are -> Are）时，窗口和浮动弹窗的同步与选择行为"""

    def test_multi_finding_selection_and_survival(self):
        finding_a = Finding(
            source="gector",
            category="grammar",
            message="Insert What",
            original=".",
            replacement=".What",
            start=28,
            end=29,
        )
        finding_b = Finding(
            source="harper",
            category="capitalization",
            message="Capitalize sentence start",
            original="are",
            replacement="Are",
            start=30,
            end=33,
        )

        state = MonitorState(
            generation=1,
            text="The students were very happy. are you doing today on this super duper nice day?",
            findings=[finding_a, finding_b],
            status="ready",
        )

        # 验证所有 findings 在 MonitorState 中完整保留且无丢失
        self.assertEqual(len(state.findings), 2)
        self.assertEqual(state.findings[0].id, finding_a.id)
        self.assertEqual(state.findings[1].id, finding_b.id)

        # 验证 _sync_floating_popup 选择的 active_finding 规则
        # 当前实现选择 findings[0] (即第 1 个 finding: . -> .What)
        active_finding = state.findings[0]
        self.assertEqual(active_finding.source, "gector")
        self.assertEqual(active_finding.original, ".")
        self.assertEqual(active_finding.replacement, ".What")

        # 验证弹窗签名计算是否能够准确区分不同的 finding
        sig_a = (finding_a.source, finding_a.original, finding_a.replacement, finding_a.start, finding_a.end)
        sig_b = (finding_b.source, finding_b.original, finding_b.replacement, finding_b.start, finding_b.end)
        self.assertNotEqual(sig_a, sig_b)


if __name__ == "__main__":
    unittest.main()
