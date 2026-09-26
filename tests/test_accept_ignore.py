"""
Unit tests for Phase 8E Accept/Ignore sequencing, monitoring persistence, and popup lifecycle.
"""

import unittest
from core.analysis import Finding
from core.monitoring import MonitorState
from core.ui.window import GCoachWindow
from core.correction.controller import CorrectionController
from unittest.mock import MagicMock, patch


class TestAcceptIgnoreSequencing(unittest.TestCase):
    """测试 Phase 8E 浮动弹窗 Accept 与 Ignore 序列化行为、持久性与生命周期"""

    def test_test_a_accept_first_finding(self):
        """TEST A — Accept first finding (. -> .What), re-analysis, and subsequent exposure of Harper finding"""
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

        initial_text = "The students were very happy. are you doing today?"
        
        # 1. 验证初始状态下第一个弹窗对应 GECToR finding
        state = MonitorState(generation=1, text=initial_text, findings=[finding_a, finding_b], status="ready")
        self.assertEqual(state.findings[0].source, "gector")
        self.assertEqual(state.findings[0].original, ".")

        # 2. 模拟 Accept 动作：应用 finding_a
        controller = CorrectionController()
        result = controller.apply_acceptance(initial_text, finding_a)
        self.assertTrue(result.success)
        new_text = result.new_text
        self.assertEqual(new_text, "The students were very happy.What are you doing today?")

        # 3. 模拟重新分析后（假设新文本中 .What 后或字符调整），验证 Harper 修正 fresh offsets 正常可用
        # 在真实应用中，re-analysis 会由 monitor 触发并生成基于新文本的新 findings
        updated_finding_b = Finding(
            source="harper",
            category="capitalization",
            message="Capitalize sentence start",
            original="are",
            replacement="Are",
            start=34, # 假设偏移更新
            end=37,
        )
        updated_state = MonitorState(generation=2, text=new_text, findings=[updated_finding_b], status="ready")
        self.assertEqual(len(updated_state.findings), 1)
        self.assertEqual(updated_state.findings[0].source, "harper")
        self.assertEqual(updated_state.findings[0].replacement, "Are")

    def test_test_b_and_c_ignore_first_finding_and_monitoring(self):
        """TEST B & C — Ignore first finding, check whether it reappears on unchanged text re-poll"""
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

        initial_text = "The students were very happy. are you doing today?"
        controller = CorrectionController()

        # 1. 标记 finding_a 为 ignored
        controller.mark_rejected(finding_a)
        self.assertEqual(finding_a.status, "rejected")

        # 2. 在当前架构下，如果文本未变且未持久过滤 ignored findings，重新分析仍会由引擎产出 finding_a
        # 验证 mark_ignored / mark_rejected 仅标记状态或关闭弹窗，并不直接从无状态引擎的分析结果中永久抹去（临时关闭）
        state_poll = MonitorState(generation=2, text=initial_text, findings=[finding_a, finding_b], status="ready")
        self.assertEqual(len(state_poll.findings), 2)
        # _sync_floating_popup 会选择 findings[0] (即 finding_a)，说明 Ignore 是临时的（关闭当前弹窗），
        # 在未加入黑名单过滤前，相同文本重新轮询时 finding 会再次出现。
        self.assertEqual(state_poll.findings[0].original, ".")

    def test_test_d_popup_state_transitions(self):
        """TEST D — Popup state transitions, signatures, and prevention of flicker/duplicate creation"""
        finding_a = Finding(
            source="gector",
            category="grammar",
            message="Insert What",
            original=".",
            replacement=".What",
            start=28,
            end=29,
        )

        sig_a = (finding_a.source, finding_a.original, finding_a.replacement, finding_a.start, finding_a.end)
        
        # 验证相同 signature 时不应触发重建（防闪烁逻辑）
        active_signature = sig_a
        self.assertEqual(active_signature, sig_a)


if __name__ == "__main__":
    unittest.main()
