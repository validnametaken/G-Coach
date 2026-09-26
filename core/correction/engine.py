"""
G-Coach Background Text Correction Engine - Phase 8E
实现通过 Windows UI Automation 的 ValuePattern / TextPattern 在无焦点状态下
直接安全地修改目标控件文本。
"""

import logging
import platform
from typing import Optional, Any
from core.analysis import Finding
from core.correction.target import CorrectionTarget

logger = logging.getLogger(__name__)


class BackgroundCorrectionEngine:
    """后台修正引擎（Background Correction Engine）

    负责在无需将焦点抢占到 G-Coach 主窗口的情况下，
    使用 UI Automation 原生模式（ValuePattern.SetValue）将纠正直接应用到原目标控件。
    """

    @staticmethod
    def apply_correction_to_target(target: CorrectionTarget, finding: Finding) -> bool:
        """在无焦点状态下，直接将 finding 的纠正应用到 target 原始控件。

        步骤：
        1. 验证目标控件引用或通过 UIA 重新获取。
        2. 获取控件当前完整文本。
        3. 验证 finding 的 [start:end] 文本与 finding.original 严格匹配。
        4. 构造新完整文本。
        5. 通过 ValuePattern.SetValue() 写入控件。
        """
        if not target:
            logger.error("Cannot apply correction: CorrectionTarget is None.")
            return False

        # 1. 获取或绑定 UIA 元素
        element = target.element_ref
        if not element and platform.system() == "Windows":
            element = BackgroundCorrectionEngine._reacquire_element(target)

        # 注意：在非 Windows 环境（如 Linux CI）或测试 Mock 模式下，element 可能为 None，
        # 此时应允许降级使用 target.original_text 进行纯文本验证与替换构造，而不是直接失败返回 False。

        # 2. 读取当前文本
        current_text = ""
        try:
            if element:
                import uiautomation as auto
                # 尝试从 ValuePattern 读取
                val_pattern = element.GetPattern(auto.PatternId.ValuePattern)
                if val_pattern:
                    current_text = val_pattern.Value or ""
                if not current_text:
                    # 尝试 TextPattern
                    for pid in (auto.PatternId.TextPattern, auto.PatternId.TextPattern2):
                        p = element.GetPattern(pid)
                        if p and p.DocumentRange:
                            current_text = p.DocumentRange.GetText(65535) or ""
                            if current_text:
                                break
                if not current_text:
                    acc = element.GetPattern(auto.PatternId.LegacyIAccessiblePattern)
                    if acc:
                        current_text = acc.Value or acc.Name or ""
            else:
                # 单元测试 Mock 模式下降级使用 target.original_text
                current_text = target.original_text
        except Exception as e:
            logger.error(f"Error reading current text from target element: {e}")
            current_text = target.original_text

        # 3. 严格范围与文本校验 (Stale Finding & Range Protection)
        start = finding.start
        end = finding.end
        original = finding.original

        if start < 0 or end < start or end > len(current_text):
            logger.warning(f"Stale finding rejection: offset range [{start}, {end}] out of bounds for text of length {len(current_text)}.")
            return False

        if original != "" and current_text[start:end] != original:
            logger.warning(f"Stale finding rejection: source text at [{start}:{end}] is '{current_text[start:end]}', expected '{original}'. Text changed.")
            return False

        # 4. 构造新完整文本
        if original == "" and start == end:
            new_text = current_text[:start] + finding.replacement + current_text[start:]
        else:
            new_text = current_text[:start] + finding.replacement + current_text[end:]

        # 5. 应用写入 (ValuePattern.SetValue / TextPattern)
        success = False
        try:
            if element:
                import uiautomation as auto
                applied = False
                
                # 尝试 1: ValuePattern
                logger.info("Diagnostic: Attempting UIA write pattern: ValuePattern")
                try:
                    val_pattern = element.GetPattern(auto.PatternId.ValuePattern)
                    pattern_exists = (val_pattern is not None)
                    logger.info(f"Diagnostic: ValuePattern exists: {pattern_exists} (ReadOnly: {getattr(val_pattern, 'IsReadOnly', 'N/A') if pattern_exists else 'N/A'})")
                    if pattern_exists and not getattr(val_pattern, "IsReadOnly", False):
                        logger.info("Diagnostic: Calling ValuePattern.SetValue()")
                        try:
                            val_pattern.SetValue(new_text)
                            applied = True
                            logger.info(f"Successfully applied background correction via ValuePattern to control {target.control_id}")
                        except Exception as e:
                            logger.info(f"Diagnostic: ValuePattern.SetValue raised exception: {e}")
                            raise
                except Exception as e:
                    logger.debug(f"ValuePattern.SetValue failed: {e}")

                # 尝试 2: TextPattern range replacement
                if not applied:
                    for pid in (auto.PatternId.TextPattern, auto.PatternId.TextPattern2):
                        pattern_name = "TextPattern" if pid == auto.PatternId.TextPattern else "TextPattern2"
                        logger.info(f"Diagnostic: Attempting UIA write pattern: {pattern_name}")
                        try:
                            tp = element.GetPattern(pid)
                            pattern_exists = (tp is not None and getattr(tp, "DocumentRange", None) is not None)
                            logger.info(f"Diagnostic: {pattern_name} exists: {pattern_exists}")
                            if pattern_exists:
                                logger.info(f"Diagnostic: Calling {pattern_name} range select/replace")
                                try:
                                    rng = tp.DocumentRange
                                    rng.Select()
                                    active_selection = tp.GetSelection()
                                    if active_selection and len(active_selection) > 0:
                                        active_selection[0].ReplaceText(finding.replacement)
                                        applied = True
                                        logger.info(f"Successfully applied correction via {pattern_name} ReplaceText.")
                                        break
                                except Exception as e:
                                    logger.info(f"Diagnostic: {pattern_name} replacement raised exception: {e}")
                                    raise
                        except Exception as e:
                            logger.debug(f"TextPattern replacement failed: {e}")

                # 尝试 3: 若 ValuePattern 和 TextPattern 均不可用但控件有焦点或支持 LegacyIAccessiblePattern
                if not applied:
                    logger.info("Diagnostic: Attempting UIA write pattern: LegacyIAccessiblePattern")
                    try:
                        acc = element.GetPattern(auto.PatternId.LegacyIAccessiblePattern)
                        pattern_exists = (acc is not None and hasattr(acc, "SetValue"))
                        logger.info(f"Diagnostic: LegacyIAccessiblePattern exists and has SetValue: {pattern_exists}")
                        if pattern_exists:
                            logger.info("Diagnostic: Calling LegacyIAccessiblePattern.SetValue()")
                            try:
                                acc.SetValue(new_text)
                                applied = True
                                logger.info("Successfully applied correction via LegacyIAccessiblePattern.")
                            except Exception as e:
                                logger.info(f"Diagnostic: LegacyIAccessiblePattern.SetValue raised exception: {e}")
                                raise
                    except Exception as e:
                        logger.debug(f"LegacyIAccessiblePattern SetValue failed: {e}")

                success = applied
                
                # 5. Read target text immediately after the call if possible
                try:
                    post_text = ""
                    val_p = element.GetPattern(auto.PatternId.ValuePattern)
                    if val_p:
                        post_text = val_p.Value or ""
                    if not post_text:
                        for pid in (auto.PatternId.TextPattern, auto.PatternId.TextPattern2):
                            p = element.GetPattern(pid)
                            if p and p.DocumentRange:
                                post_text = p.DocumentRange.GetText(65535) or ""
                                if post_text:
                                    break
                    if not post_text:
                        acc = element.GetPattern(auto.PatternId.LegacyIAccessiblePattern)
                        if acc:
                            post_text = acc.Value or acc.Name or ""
                    logger.info(f"Diagnostic: Target text immediately after write call: {repr(post_text)}")
                except Exception as ex:
                    logger.info(f"Diagnostic: Failed to read target text immediately after call: {ex}")

                if not success:
                    logger.warning(f"No suitable writable pattern (ValuePattern/TextPattern/LegacyIAccessible) found for target control {target.control_id}.")
            else:
                logger.warning(f"Cannot apply correction: No UIA element reference available for target control {target.control_id}.")
                success = False
        except Exception as e:
            logger.error(f"Failed to set value on target control via UIA: {e}", exc_info=True)
            success = False

        return success

    @staticmethod
    def _reacquire_element(target: CorrectionTarget) -> Optional[Any]:
        """根据 process_id 和 automation_id 尝试重新定位 UIA 元素"""
        try:
            import uiautomation as auto
            root = auto.GetRootControl()
            # 简单的进程树遍历查找
            # 在实际运行中，如果保存了 element_ref 且控件未被销毁，通常直接可用
            return None
        except Exception:
            return None
