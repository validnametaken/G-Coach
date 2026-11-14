"""Regression tests for fail-closed, exact-range UIA correction."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import uiautomation as auto

from core.analysis import Finding, HarperAnalysisEngine
from core.correction.engine import BackgroundCorrectionEngine
from core.correction.target import CorrectionTarget


class FakeRect:
    def __init__(self, left, top, width, height):
        self.left = left
        self.top = top
        self.right = left + width
        self.bottom = top + height

    def width(self):
        return self.right - self.left

    def height(self):
        return self.bottom - self.top


class FakeDocument:
    def __init__(self, text):
        self.text = text
        self.selection = None
        self.rectangles = [FakeRect(100, 200, 50, 18)]

    def replace_selection(self, replacement):
        if self.selection is None:
            return
        start, end = self.selection
        self.text = self.text[:start] + replacement + self.text[end:]
        self.selection = (start, start + len(replacement))


class FakeTextRange:
    def __init__(self, document, start, end):
        self.document = document
        self.start = start
        self.end = end

    def Clone(self):
        return FakeTextRange(self.document, self.start, self.end)

    def MoveEndpointByUnit(self, endpoint, _unit, count, waitTime=0):
        if endpoint == auto.TextPatternRangeEndpoint.Start:
            new_value = max(0, min(len(self.document.text), self.start + count))
            moved = new_value - self.start
            self.start = new_value
            if self.start > self.end:
                self.end = self.start
            return moved
        new_value = max(0, min(len(self.document.text), self.end + count))
        moved = new_value - self.end
        self.end = new_value
        if self.end < self.start:
            self.start = self.end
        return moved

    def GetText(self, _max_length=-1):
        return self.document.text[self.start:self.end]

    def Select(self, waitTime=0):
        self.document.selection = (self.start, self.end)
        return True

    def Compare(self, other):
        return self.start == other.start and self.end == other.end

    def GetBoundingRectangles(self):
        return self.document.rectangles


class FakeTextPattern:
    def __init__(self, document):
        self.document = document

    @property
    def DocumentRange(self):
        return FakeTextRange(self.document, 0, len(self.document.text))

    def GetSelection(self):
        if self.document.selection is None:
            return []
        return [FakeTextRange(self.document, *self.document.selection)]


class Utf16TextRange(FakeTextRange):
    """Fake UIA range whose Character movement counts UTF-16 code units."""

    @staticmethod
    def _unit_offset(text, index):
        return len(text[:index].encode("utf-16-le", errors="surrogatepass")) // 2

    @staticmethod
    def _python_offset(text, units):
        consumed = 0
        for index, character in enumerate(text):
            width = 2 if ord(character) > 0xFFFF else 1
            if consumed + width > units:
                return index
            consumed += width
            if consumed == units:
                return index + 1
        return len(text)

    def Clone(self):
        return Utf16TextRange(self.document, self.start, self.end)

    def MoveEndpointByUnit(self, endpoint, _unit, count, waitTime=0):
        current_index = self.start if endpoint == auto.TextPatternRangeEndpoint.Start else self.end
        current_units = self._unit_offset(self.document.text, current_index)
        total_units = self._unit_offset(self.document.text, len(self.document.text))
        requested_units = max(0, min(total_units, current_units + count))
        new_index = self._python_offset(self.document.text, requested_units)
        new_units = self._unit_offset(self.document.text, new_index)
        moved = new_units - current_units

        if endpoint == auto.TextPatternRangeEndpoint.Start:
            self.start = new_index
            if self.start > self.end:
                self.end = self.start
        else:
            self.end = new_index
            if self.end < self.start:
                self.start = self.end
        return moved


class Utf16TextPattern(FakeTextPattern):
    @property
    def DocumentRange(self):
        return Utf16TextRange(self.document, 0, len(self.document.text))

    def GetSelection(self):
        if self.document.selection is None:
            return []
        return [Utf16TextRange(self.document, *self.document.selection)]


class FakeElement:
    ProcessId = 202
    NativeWindowHandle = 101
    AutomationId = "editor"
    Name = "Main editor"
    ControlTypeName = "EditControl"

    def __init__(self, document):
        self.pattern = FakeTextPattern(document)

    def GetPattern(self, pattern_id):
        if pattern_id in (auto.PatternId.TextPattern, auto.PatternId.TextPattern2):
            return self.pattern
        return None


class TestBackgroundCorrectionSafety(unittest.TestCase):
    def setUp(self):
        self.original_text = "same same same"
        self.document = FakeDocument(self.original_text)
        self.element = FakeElement(self.document)
        self.target = CorrectionTarget(
            control_id="test-control",
            process_id=202,
            hwnd=101,
            automation_id="editor",
            control_type="EditControl",
            app_name="TestApp.exe",
            original_text=self.original_text,
        )

    def finding(self, original="same", replacement="middle", start=5, end=9):
        return Finding(
            source="test",
            category="grammar",
            message="test correction",
            original=original,
            replacement=replacement,
            start=start,
            end=end,
        )

    def apply_with_keyboard(self, finding, focused=None):
        if focused is None:
            focused = self.element

        def write_text(value, delay=0):
            self.document.replace_selection(value)

        def send_key(value):
            if value == "backspace":
                self.document.replace_selection("")

        with patch("platform.system", return_value="Windows"), \
             patch("uiautomation.GetFocusedControl", return_value=focused), \
             patch("keyboard.write", side_effect=write_text) as write_mock, \
             patch("keyboard.send", side_effect=send_key) as send_mock:
            result = BackgroundCorrectionEngine.apply_correction_to_target(self.target, finding)
        return result, write_mock, send_mock

    def test_replaces_only_the_requested_occurrence(self):
        result, write_mock, _ = self.apply_with_keyboard(self.finding())
        self.assertTrue(result)
        self.assertEqual(self.document.text, "same middle same")
        write_mock.assert_called_once_with("middle", delay=0.01)

    def test_refuses_when_any_part_of_snapshot_changed(self):
        self.document.text = "prefix same same same"
        result, write_mock, send_mock = self.apply_with_keyboard(self.finding())
        self.assertFalse(result)
        self.assertEqual(self.document.text, "prefix same same same")
        write_mock.assert_not_called()
        send_mock.assert_not_called()

    def test_refuses_when_exact_range_does_not_match(self):
        result, write_mock, _ = self.apply_with_keyboard(
            self.finding(original="word", replacement="text")
        )
        self.assertFalse(result)
        write_mock.assert_not_called()

    def test_refuses_when_focus_moved_to_another_control(self):
        other_control = type(
            "OtherControl",
            (),
            {
                "ProcessId": 202,
                "NativeWindowHandle": 999,
                "AutomationId": "other-editor",
                "ControlTypeName": "EditControl",
            },
        )()
        result, write_mock, _ = self.apply_with_keyboard(self.finding(), focused=other_control)
        self.assertFalse(result)
        write_mock.assert_not_called()

    def test_refuses_hwnd_only_target_that_cannot_distinguish_sibling_controls(self):
        self.target.automation_id = ""
        self.target.control_name = ""

        with patch("platform.system", return_value="Windows"), \
             patch("uiautomation.GetFocusedControl", return_value=self.element):
            result = BackgroundCorrectionEngine.get_finding_screen_rect(
                self.target, self.finding()
            )

        self.assertIsNone(result)

    def test_validates_captured_control_name_when_automation_id_is_missing(self):
        self.target.automation_id = ""
        self.target.control_name = "Main editor"
        other_control = FakeElement(self.document)
        other_control.Name = "Another editor"

        with patch("platform.system", return_value="Windows"), \
             patch("uiautomation.GetFocusedControl", return_value=other_control):
            result = BackgroundCorrectionEngine.get_finding_screen_rect(
                self.target, self.finding()
            )

        self.assertIsNone(result)

    def test_supports_empty_range_insertion(self):
        self.document.text = "hello world"
        self.target.original_text = self.document.text
        finding = self.finding(original="", replacement="beautiful ", start=6, end=6)
        result, write_mock, _ = self.apply_with_keyboard(finding)
        self.assertTrue(result)
        self.assertEqual(self.document.text, "hello beautiful world")
        write_mock.assert_called_once_with("beautiful ", delay=0.01)

    def test_supports_deletion_with_backspace(self):
        self.document.text = "same same same"
        finding = self.finding(original="same ", replacement="", start=5, end=10)
        result, _, send_mock = self.apply_with_keyboard(finding)
        self.assertTrue(result)
        self.assertEqual(self.document.text, "same same")
        send_mock.assert_called_once_with("backspace")

    def test_refuses_if_post_write_text_is_not_exact(self):
        clock = {"now": 0.0}

        def advance_clock(seconds):
            clock["now"] += seconds

        with patch("platform.system", return_value="Windows"), \
             patch("uiautomation.GetFocusedControl", return_value=self.element), \
             patch("keyboard.write") as write_mock, \
             patch("core.correction.engine.time.monotonic", side_effect=lambda: clock["now"]), \
             patch("core.correction.engine.time.sleep", side_effect=advance_clock):
            result = BackgroundCorrectionEngine.apply_correction_to_target_detailed(
                self.target, self.finding()
            )
        self.assertFalse(result.success)
        self.assertIn("No text change was detected", result.reason)
        write_mock.assert_called_once_with("middle", delay=0.01)

    def test_waits_for_delayed_uia_text_publication_without_retyping(self):
        finding = self.finding()
        expected_text = "same middle same"
        read_text = BackgroundCorrectionEngine._read_text_pattern
        delayed_publication = {"pending": False}

        def delayed_read(element, automation):
            pattern, document_range, observed_text = read_text(element, automation)
            if delayed_publication["pending"] and observed_text == expected_text:
                delayed_publication["pending"] = False
                return pattern, document_range, self.original_text
            return pattern, document_range, observed_text

        def write_text(value, delay=0):
            self.document.replace_selection(value)
            delayed_publication["pending"] = True

        with patch("platform.system", return_value="Windows"), \
             patch("uiautomation.GetFocusedControl", return_value=self.element), \
             patch("core.correction.engine.BackgroundCorrectionEngine._read_text_pattern", side_effect=delayed_read), \
             patch("keyboard.write", side_effect=write_text) as write_mock, \
             patch("core.correction.engine.time.sleep"):
            result = BackgroundCorrectionEngine.apply_correction_to_target_detailed(
                self.target, finding
            )

        self.assertTrue(result.success)
        self.assertEqual(result.resulting_text, expected_text)
        self.assertEqual(self.document.text, expected_text)
        write_mock.assert_called_once_with("middle", delay=0.01)

    def test_refuses_when_live_text_cannot_be_read(self):
        class UnreadableElement:
            ProcessId = 202
            NativeWindowHandle = 101
            AutomationId = "editor"
            ControlTypeName = "EditControl"

            def GetPattern(self, _pattern_id):
                raise RuntimeError("UIA read failed")

        unreadable_element = UnreadableElement()
        with patch("platform.system", return_value="Windows"), \
             patch("uiautomation.GetFocusedControl", return_value=unreadable_element), \
             patch("keyboard.write") as write_mock:
            result = BackgroundCorrectionEngine.apply_correction_to_target(
                self.target, self.finding()
            )
        self.assertFalse(result)
        write_mock.assert_not_called()

    def test_finding_screen_rect_uses_exact_range_geometry_without_selecting(self):
        self.document.rectangles = [
            FakeRect(10, 20, 30, 18),
            FakeRect(42.4, 20.2, 24.8, 18.0),
        ]

        with patch("platform.system", return_value="Windows"):
            with patch("uiautomation.GetFocusedControl", return_value=self.element):
                rect = BackgroundCorrectionEngine.get_finding_screen_rect(
                    self.target, self.finding()
                )

        self.assertEqual(rect, (42, 20, 25, 18))
        self.assertIsNone(self.document.selection)

    def test_finding_screen_rect_refuses_stale_snapshot(self):
        self.document.text = "changed same same"

        with patch("platform.system", return_value="Windows"):
            with patch("uiautomation.GetFocusedControl", return_value=self.element):
                rect = BackgroundCorrectionEngine.get_finding_screen_rect(
                    self.target, self.finding()
                )

        self.assertIsNone(rect)
        self.assertIsNone(self.document.selection)

    def test_finding_screen_rect_refuses_invalid_uia_geometry(self):
        self.document.rectangles = [FakeRect(float("nan"), 20, 30, 18)]

        with patch("platform.system", return_value="Windows"):
            with patch("uiautomation.GetFocusedControl", return_value=self.element):
                rect = BackgroundCorrectionEngine.get_finding_screen_rect(
                    self.target, self.finding()
                )

        self.assertIsNone(rect)

    def test_unicode_prefix_is_mapped_or_rejected_safely(self):
        self.document.text = "café 🙂 same same"
        self.target.original_text = self.document.text
        start = self.document.text.index("same") + 5
        finding = self.finding(start=start, end=start + 4)
        result, _, _ = self.apply_with_keyboard(finding)
        self.assertTrue(result)
        self.assertEqual(self.document.text, "café 🙂 same middle")

    def test_utf16_ui_automation_offsets_are_supported_after_emoji(self):
        self.document.text = "prefix 🙂 MB suffix"
        self.target.original_text = self.document.text
        self.element.pattern = Utf16TextPattern(self.document)
        start = self.document.text.index("MB")
        finding = self.finding(original="MB", replacement="megabytes", start=start, end=start + 2)

        result, write_mock, _ = self.apply_with_keyboard(finding)

        self.assertTrue(result)
        self.assertEqual(self.document.text, "prefix 🙂 megabytes suffix")
        write_mock.assert_called_once_with("megabytes", delay=0.01)

    def test_harper_utf16_offsets_after_family_emoji_are_normalized_before_correction(self):
        text = "Family 👨‍👩‍👧‍👦 size: 2 MB — ready 👍."
        python_start = text.index("MB")
        harper_start = len(text[:python_start].encode("utf-16-le")) // 2
        payload = [{
            "original": "MB",
            "start": harper_start,
            "end": harper_start + 2,
            "replacements": ["megabytes"],
            "category": "style",
            "message": "Expand the unit abbreviation.",
        }]

        with patch(
            "core.analysis.harper.subprocess.run",
            return_value=SimpleNamespace(
                returncode=0,
                stdout=json.dumps(payload).encode("utf-8"),
                stderr=b"",
            ),
        ):
            findings = HarperAnalysisEngine().analyze(text)

        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual((finding.start, finding.end), (python_start, python_start + 2))
        self.assertEqual(text[finding.start:finding.end], "MB")

        self.document.text = text
        self.target.original_text = text
        self.element.pattern = Utf16TextPattern(self.document)
        result, write_mock, _ = self.apply_with_keyboard(finding)

        self.assertTrue(result)
        self.assertEqual(
            self.document.text,
            "Family 👨‍👩‍👧‍👦 size: 2 megabytes — ready 👍.",
        )
        write_mock.assert_called_once_with("megabytes", delay=0.01)

    def test_batch_correction_applies_non_overlapping_findings_right_to_left(self):
        self.document.text = "red and blue"
        self.target.original_text = self.document.text
        first_start = self.document.text.index("red")
        second_start = self.document.text.index("blue")
        findings = [
            self.finding("red", "green", first_start, first_start + 3),
            self.finding("blue", "yellow", second_start, second_start + 4),
        ]
        write_order = []

        def write_text(value, delay=0):
            write_order.append(value)
            self.document.replace_selection(value)

        with patch("platform.system", return_value="Windows"), \
             patch("uiautomation.GetFocusedControl", return_value=self.element), \
             patch("keyboard.write", side_effect=write_text):
            result = BackgroundCorrectionEngine.apply_corrections_to_target(
                self.target, findings
            )

        self.assertTrue(result.success)
        self.assertEqual(result.applied_count, 2)
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(self.document.text, "green and yellow")
        self.assertEqual(write_order, ["yellow", "green"])
        self.assertEqual(self.target.original_text, self.document.text)
        self.assertTrue(all(f.status == "accepted" for f in findings))

    def test_batch_correction_skips_overlapping_suggestions(self):
        first = self.finding("same", "word", 5, 9)
        overlapping = self.finding("same ", "phrase", 5, 10)
        overlapping.metadata["has_conflict"] = True

        with patch("platform.system", return_value="Windows"), \
             patch("uiautomation.GetFocusedControl", return_value=self.element), \
             patch("keyboard.write") as write_mock:
            result = BackgroundCorrectionEngine.apply_corrections_to_target(
                self.target, [first, overlapping]
            )

        self.assertFalse(result.success)
        self.assertEqual(result.applied_count, 0)
        self.assertEqual(result.skipped_count, 2)
        write_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
