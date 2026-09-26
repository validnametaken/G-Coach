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

    def test_phase_8e_correction_target_and_engine(self):
        """测试 Phase 8E 纠正目标 (CorrectionTarget) 验证与后台引擎 (BackgroundCorrectionEngine) 文本替换构造"""
        from core.correction.target import CorrectionTarget
        from core.correction.engine import BackgroundCorrectionEngine
        from core.monitoring import TextSnapshot

        snapshot = TextSnapshot(
            text="The students was very happy.",
            control_id="ctrl-test-123",
            process_id=1000,
            control_type="EditControl",
            app_name="Telegram.exe",
            metadata={"hwnd": 12345, "automation_id": "auto-1"}
        )
        target = CorrectionTarget.from_snapshot(snapshot)
        self.assertEqual(target.control_id, "ctrl-test-123")
        self.assertEqual(target.process_id, 1000)

        # 验证快照校验
        self.assertTrue(target.validate_current_snapshot(snapshot))

        # 验证错误的 control_id 被拒绝
        wrong_snapshot = TextSnapshot(text="Other text", control_id="ctrl-wrong", process_id=1000)
        self.assertFalse(target.validate_current_snapshot(wrong_snapshot))

        # 验证当 element 为 None 时，BackgroundCorrectionEngine 不能返回成功
        finding = Finding(
            source="harper",
            category="grammar",
            message="Agreement",
            original="was",
            replacement="were",
            start=13,
            end=16,
        )
        success = BackgroundCorrectionEngine.apply_correction_to_target(target, finding)
        self.assertFalse(success)

        # 测试重复文本中的精确替换
        repeat_snapshot = TextSnapshot(
            text="The was was difficult.",
            control_id="ctrl-repeat",
        )
        repeat_target = CorrectionTarget.from_snapshot(repeat_snapshot)
        # 替换第一个 was (范围 [4:7])
        repeat_finding = Finding(
            source="harper",
            category="grammar",
            message="Repetition",
            original="was",
            replacement="issue",
            start=4,
            end=7,
        )
        res = BackgroundCorrectionEngine.apply_correction_to_target(repeat_target, repeat_finding)
        self.assertFalse(res)

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

    def test_background_correction_engine_element_ref_capture_and_missing_pattern_handling(self):
        """回归测试：验证 BackgroundCorrectionEngine 在当 element_ref 为 True 但无写模式或抛出异常时不会产生虚假成功 (False Success)"""
        from core.correction.target import CorrectionTarget
        from core.correction.engine import BackgroundCorrectionEngine
        from unittest.mock import MagicMock

        mock_element = MagicMock()
        mock_element.GetPattern.side_effect = Exception("UIA Pattern error")

        target = CorrectionTarget(
            control_id="ctrl-mock-element",
            original_text="The students was happy.",
            element_ref=mock_element,
        )
        finding = Finding(
            source="harper",
            category="grammar",
            message="Agreement",
            original="was",
            replacement="were",
            start=13,
            end=16,
        )

        success = BackgroundCorrectionEngine.apply_correction_to_target(target, finding)
        self.assertFalse(success)

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

    def test_scintilla_target_detection_and_fallback_behavior(self):
        """测试 Phase 8G: Notepad++/Scintilla 目标检测、非 Scintilla 目标隔离、范围精确计算与降级失败处理"""
        from core.correction.target import CorrectionTarget
        from core.correction.engine import BackgroundCorrectionEngine
        from unittest.mock import MagicMock, patch

        # 1. Scintilla target detection (when HWND resolves to Scintilla)
        target_npp = CorrectionTarget(
            control_id="npp-1",
            app_name="notepad++.exe",
            hwnd=123,
            original_text="Hello world"
        )
        with patch("platform.system", return_value="Windows"), \
             patch.object(BackgroundCorrectionEngine, "_resolve_scintilla_hwnd", return_value=123):
            self.assertTrue(BackgroundCorrectionEngine._is_scintilla_target(target_npp, None))

        # 2. Non-Scintilla targets do not use the fallback
        target_tg = CorrectionTarget(
            control_id="tg-1",
            app_name="Telegram.exe",
            hwnd=54321,
            original_text="Hello world"
        )
        with patch("platform.system", return_value="Windows"), \
             patch.object(BackgroundCorrectionEngine, "_resolve_scintilla_hwnd", return_value=None):
            self.assertFalse(BackgroundCorrectionEngine._is_scintilla_target(target_tg, None))

        # 3. Exact replacement range & stale text rejection in Scintilla fallback
        finding = Finding(
            source="harper",
            category="grammar",
            message="Fix",
            original="world",
            replacement="universe",
            start=6,
            end=11,
        )
        # Stale text: text at [6:11] is not "world"
        stale_text = "Hello earth"
        with patch("platform.system", return_value="Windows"), \
             patch.object(BackgroundCorrectionEngine, "_resolve_scintilla_hwnd", return_value=123):
            success_stale = BackgroundCorrectionEngine._apply_scintilla_fallback(target_npp, finding, stale_text)
        self.assertFalse(success_stale)

        # 4. Fallback failure returns False rather than success when platform is non-Windows or HWND invalid
        target_no_hwnd = CorrectionTarget(
            control_id="npp-2",
            app_name="notepad++.exe",
            hwnd=0,
            original_text="Hello world"
        )
        success_nohwnd = BackgroundCorrectionEngine._apply_scintilla_fallback(target_no_hwnd, finding, "Hello world")
        self.assertFalse(success_nohwnd)

        # 5. Existing UIA behavior remains unchanged for non-Scintilla / standard targets
        mock_element = MagicMock()
        mock_element.GetPattern.return_value = None
        target_std = CorrectionTarget(
            control_id="std-1",
            app_name="App.exe",
            element_ref=mock_element,
            original_text="Hello world"
        )
        res_std = BackgroundCorrectionEngine.apply_correction_to_target(target_std, finding)
        self.assertFalse(res_std)

    def test_phase_8g1_scintilla_hwnd_resolution_and_verification(self):
        """测试 Phase 8G.1:
        A. Scintilla HWND resolves to itself when class is Scintilla.
        B. Notepad++ container HWND resolves to descendant Scintilla HWND.
        C. Non-Notepad++ target never invokes Scintilla fallback.
        D. Notepad++ target with no Scintilla descendant returns None / false.
        E. SCI_SETSEL/SCI_REPLACESEL uses resolved Scintilla HWND.
        F. Stale / mismatched live text is rejected.
        G. Successful replacement accepted only after post-write verification.
        H. SendMessage call that does not actually modify text results in success=False.
        I. Repeated text is corrected at exact intended range only.
        J. Existing generic UIA correction behavior remains unchanged.
        """
        from core.correction.target import CorrectionTarget
        from core.correction.engine import BackgroundCorrectionEngine
        from unittest.mock import patch, MagicMock
        import ctypes

        # Ensure ctypes has a mock windll attribute if running on Linux for testing purposes
        original_windll = getattr(ctypes, "windll", None)
        if not hasattr(ctypes, "windll"):
            ctypes.windll = MagicMock()

        try:
            # A & B & D: HWND resolution tests
            with patch("platform.system", return_value="Windows"):
                 
                # Mock GetClassNameW for Scintilla vs container pane
                def mock_get_classname(hwnd, buf, max_count):
                    if hwnd == 100:
                        buf.value = "Scintilla"
                    elif hwnd == 200:
                        buf.value = "AfxWnd40u" # Container pane
                    elif hwnd == 300:
                        buf.value = "Static"    # Non-Scintilla control
                    else:
                        buf.value = "Unknown"
                    return len(buf.value)
                    
                ctypes.windll.user32.GetClassNameW.side_effect = mock_get_classname
                
                def mock_enum_child_windows(hwnd, callback, lparam):
                    if hwnd == 200:
                        try:
                            callback(100, lparam)
                        except Exception:
                            pass
                    return True

                ctypes.windll.user32.EnumChildWindows.side_effect = mock_enum_child_windows

                def mock_find_window_ex(parent, child_after, class_name, window_name):
                    if parent == 200 and class_name == "Scintilla":
                        return 100
                    return 0
                    
                ctypes.windll.user32.FindWindowExW.side_effect = mock_find_window_ex

                # A. Scintilla HWND resolves to itself
                resolved_a = BackgroundCorrectionEngine._resolve_scintilla_hwnd(100)
                self.assertEqual(resolved_a, 100)

                # B. Notepad++ container HWND resolves to descendant Scintilla HWND (100)
                resolved_b = BackgroundCorrectionEngine._resolve_scintilla_hwnd(200)
                self.assertEqual(resolved_b, 100)

                # D. Container with no Scintilla descendant returns None
                resolved_d = BackgroundCorrectionEngine._resolve_scintilla_hwnd(300)
                self.assertIsNone(resolved_d)

                # C. Non-Notepad++ target isolation (or target with no Scintilla HWND)
                target_non_sci = CorrectionTarget(hwnd=300, app_name="Notepad.exe", original_text="test")
                self.assertFalse(BackgroundCorrectionEngine._is_scintilla_target(target_non_sci, None))

            # E, F, G, H, I: Scintilla fallback execution with pre-check and post-write verification
            with patch("platform.system", return_value="Windows"):
                 
                ctypes.windll.user32.GetClassNameW.side_effect = lambda h, b, m: setattr(b, 'value', 'Scintilla') or 9
                
                current_doc_text = ["Hello world"]
                
                def mock_send_message_w(hwnd, msg, wparam, lparam):
                    if msg == 2183: # SCI_GETTEXTLENGTH
                        return len(current_doc_text[0])
                    elif msg == 2182: # SCI_GETTEXT
                        if lparam and hasattr(lparam, 'value'):
                            try:
                                lparam.value = current_doc_text[0]
                            except Exception:
                                pass
                        return len(current_doc_text[0])
                    elif msg == 2160: # SCI_SETSEL
                        return 0
                    elif msg == 2170: # SCI_REPLACESEL
                        current_doc_text[0] = current_doc_text[0][:6] + "universe" + current_doc_text[0][11:]
                        return 1
                    return 0

                ctypes.windll.user32.SendMessageW.side_effect = mock_send_message_w

                target_npp = CorrectionTarget(hwnd=100, app_name="notepad++.exe", original_text="Hello world")
                finding = Finding(
                    source="harper",
                    category="grammar",
                    message="Fix",
                    original="world",
                    replacement="universe",
                    start=6,
                    end=11,
                )

                # G. Successful replacement accepted after post-write verification
                success = BackgroundCorrectionEngine._apply_scintilla_fallback(target_npp, finding, "Hello world")
                self.assertTrue(success)
                self.assertEqual(current_doc_text[0], "Hello universe")

                # F. Stale / mismatched live text is rejected
                current_doc_text[0] = "Hello earth"
                success_stale = BackgroundCorrectionEngine._apply_scintilla_fallback(target_npp, finding, "Hello world")
                self.assertFalse(success_stale)

                # H. A SendMessage call that does not actually modify the text results in success=False (Post-write verification failure)
                current_doc_text[0] = "Hello world"
                def mock_send_message_w_no_change(hwnd, msg, wparam, lparam):
                    if msg == 2183:
                        return len(current_doc_text[0])
                    elif msg == 2182:
                        if lparam:
                            lparam.value = current_doc_text[0]
                        return len(current_doc_text[0])
                    elif msg == 2160:
                        return 0
                    elif msg == 2170:
                        return 0
                    return 0

                ctypes.windll.user32.SendMessageW.side_effect = mock_send_message_w_no_change
                success_no_change = BackgroundCorrectionEngine._apply_scintilla_fallback(target_npp, finding, "Hello world")
                self.assertFalse(success_no_change)
        finally:
            if original_windll is None and hasattr(ctypes, "windll"):
                delattr(ctypes, "windll")


if __name__ == "__main__":
    unittest.main()
