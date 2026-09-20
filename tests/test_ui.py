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


if __name__ == "__main__":
    unittest.main()
