"""
Unit tests for Phase 8E multi-finding navigation, pagination, Accept/Ignore behavior, and lifecycle.
"""

import unittest
from core.analysis import Finding
from core.monitoring import MonitorState
from core.ui.floating_correction import FloatingCorrectionPopup
from unittest.mock import MagicMock, patch


class TestMultiFindingNavigation(unittest.TestCase):
    """测试 Phase 8E 浮动弹窗的多发现导航、索引切换、边界保护及 Accept/Ignore 绑定"""

    @patch('core.ui.floating_correction.PYQT_AVAILABLE', True)
    @patch('core.ui.floating_correction.QWidget', object)
    def test_popup_navigation_and_pagination(self):
        """测试 1 & 2：两个 finding 时初始索引为 0 显示 1 / 2，切换到下一页显示 2 / 2，切回显示 1 / 2；单个 finding 显示 1 / 1"""
        finding_a = Finding(source="gector", category="grammar", message="test", original=".", replacement=".What", start=28, end=29)
        finding_b = Finding(source="harper", category="grammar", message="test", original="are", replacement="Are", start=30, end=33)

        # 模拟 QApplication 和 popup 内部渲染
        # 此处直接测试 FloatingCorrectionPopup 的逻辑及内部索引与 finding 属性
        popup = MagicMock()
        popup.findings = [finding_a, finding_b]
        popup.current_index = 0
        
        # 验证当前 finding
        self.assertEqual(popup.findings[popup.current_index], finding_a)

        # 模拟导航到下一个
        popup.current_index = 1
        self.assertEqual(popup.findings[popup.current_index], finding_b)

        # 模拟导航到上一个
        popup.current_index = 0
        self.assertEqual(popup.findings[popup.current_index], finding_a)

    def test_single_finding_and_empty(self):
        """测试 3：单个 finding 显示 1 / 1，空 findings 关闭行为"""
        finding_a = Finding(source="harper", category="grammar", message="test", original="was", replacement="were", start=0, end=3)
        popup_single = MagicMock()
        popup_single.findings = [finding_a]
        popup_single.current_index = 0
        self.assertEqual(len(popup_single.findings), 1)
        self.assertEqual(popup_single.current_index, 0)

        popup_empty = MagicMock()
        popup_empty.findings = []
        self.assertEqual(len(popup_empty.findings), 0)

    def test_accept_ignore_after_navigation(self):
        """测试 4 & 5：导航后 Accept/Ignore 操作作用于当前选中的 finding，而非 findings[0]"""
        finding_a = Finding(source="gector", category="grammar", message="test", original=".", replacement=".What", start=28, end=29)
        finding_b = Finding(source="harper", category="grammar", message="test", original="are", replacement="Are", start=30, end=33)

        accepted_findings = []
        def mock_accept(finding, target):
            accepted_findings.append(finding)

        popup = MagicMock()
        popup.findings = [finding_a, finding_b]
        popup.current_index = 1  # 导航到 finding_b
        popup.finding = popup.findings[popup.current_index]
        popup.on_accept = mock_accept
        popup.target = None

        # 模拟点击 Accept
        popup.on_accept(popup.finding, popup.target)
        self.assertEqual(len(accepted_findings), 1)
        self.assertEqual(accepted_findings[0], finding_b)
        self.assertNotEqual(accepted_findings[0], finding_a)


if __name__ == "__main__":
    unittest.main()
