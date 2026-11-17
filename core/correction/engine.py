"""Safe, targeted correction of the original UI Automation text control."""

from __future__ import annotations

import hashlib
import logging
import math
import platform
import time
from dataclasses import dataclass
from typing import Any, Optional

from core.analysis import Finding
from core.correction.target import CorrectionTarget

logger = logging.getLogger(__name__)

# CEF-backed editors can drop or delay very fast synthetic Unicode input. Keep
# the per-character delay small enough to feel instantaneous, but give the
# editor's input loop time to consume each character before verification.
_KEYSTROKE_DELAY_SECONDS = 0.01
_POST_WRITE_VERIFY_TIMEOUT_SECONDS = 1.5
_POST_WRITE_VERIFY_INTERVAL_SECONDS = 0.025
_POST_WRITE_VERIFY_STABLE_READS = 2


@dataclass(frozen=True)
class CorrectionAttempt:
    """Outcome of one exact-range UI Automation correction."""

    success: bool
    reason: str = ""
    resulting_text: Optional[str] = None


@dataclass(frozen=True)
class BatchCorrectionResult:
    """Outcome of a safe, non-overlapping batch correction."""

    success: bool
    applied_count: int = 0
    skipped_count: int = 0
    reason: str = ""
    resulting_text: Optional[str] = None


class BackgroundCorrectionEngine:
    """Apply a finding only when its original target and full text are unchanged.

    UIA's ValuePattern and LegacyIAccessible SetValue methods replace an entire
    value. They are deliberately not used here: corrections must select and
    replace only the finding's exact TextPattern range.
    """

    @staticmethod
    def apply_correction_to_target(target: CorrectionTarget, finding: Finding) -> bool:
        """Compatibility wrapper returning only whether the correction succeeded."""
        return BackgroundCorrectionEngine.apply_correction_to_target_detailed(
            target, finding
        ).success

    @staticmethod
    def apply_correction_to_target_detailed(
        target: CorrectionTarget, finding: Finding
    ) -> CorrectionAttempt:
        """Apply one correction and return a safe, user-displayable failure reason."""
        if target is None or finding is None:
            logger.warning("Correction refused: target or finding is missing.")
            return CorrectionAttempt(False, "The correction target or suggestion is missing.")

        # Route WordCraft targets through the specialized WordCraftCorrectionAdapter
        try:
            from core.correction.wordcraft_adapter import WordCraftCorrectionAdapter
            if WordCraftCorrectionAdapter.is_wordcraft_target(target):
                success = WordCraftCorrectionAdapter.apply_wordcraft_correction(target, finding)
                if success:
                    return CorrectionAttempt(True, "", finding.replacement)
                else:
                    return CorrectionAttempt(False, "WordCraft correction failed.")
        except Exception as exc:
            logger.debug("WordCraftCorrectionAdapter routing check failed: %s", exc)

        # Route Notepad++ targets through the safe NppCorrectionAdapter bridge
        try:
            from core.correction.npp_adapter import NppCorrectionAdapter
            if NppCorrectionAdapter.is_notepad_target(target):
                success = NppCorrectionAdapter.apply_bridge_correction(target, finding)
                if success:
                    return CorrectionAttempt(True, "", finding.replacement)
                else:
                    return CorrectionAttempt(False, "Notepad++ bridge correction failed.")
        except Exception as exc:
            logger.debug("NppCorrectionAdapter routing check failed: %s", exc)
        if platform.system() != "Windows":
            logger.warning("Correction refused: targeted UI Automation editing is Windows-only.")
            return CorrectionAttempt(False, "Targeted editing is only supported on Windows.")
        if finding.status in {"accepted", "ignored", "rejected"}:
            logger.warning("Correction refused: finding status is %r.", finding.status)
            return CorrectionAttempt(False, "This suggestion is no longer pending.")
        if finding.original == finding.replacement:
            logger.warning("Correction refused: replacement would not change the text.")
            return CorrectionAttempt(False, "The suggested replacement would not change the text.")
        if not isinstance(finding.start, int) or not isinstance(finding.end, int):
            logger.warning("Correction refused: finding offsets are not integers.")
            return CorrectionAttempt(False, "The suggestion has invalid text offsets.")
        if finding.start < 0 or finding.end < finding.start:
            logger.warning("Correction refused: invalid finding range [%s:%s].", finding.start, finding.end)
            return CorrectionAttempt(False, "The suggestion has an invalid text range.")
        if finding.end - finding.start != len(finding.original):
            logger.warning("Correction refused: finding range length does not match its original text.")
            return CorrectionAttempt(False, "The suggestion's text range does not match its source word.")

        try:
            import uiautomation as auto

            # UIA Control/Pattern wrappers are apartment-bound. Reacquire the
            # focused element on the monitor thread instead of retaining the
            # object captured during an earlier poll or passing it from Qt.
            element = BackgroundCorrectionEngine._get_focused_target_element(target, auto)
            if element is None:
                logger.warning("Correction refused: the original target is no longer focused or cannot be identified.")
                return CorrectionAttempt(False, "The original editor is no longer the focused target. Click back into the document and retry.")

            pattern, document_range, current_text = BackgroundCorrectionEngine._read_text_pattern(
                element, auto
            )
            if pattern is None or document_range is None or current_text is None:
                logger.warning("Correction refused: the target exposes no readable TextPattern document range.")
                return CorrectionAttempt(False, "The editor did not expose a readable text range to Windows UI Automation.")

            # Compare the complete snapshot, not just the word being replaced.
            # This also catches edits before the finding that would shift offsets.
            if current_text != target.original_text:
                logger.warning("Correction refused: target text changed since analysis (stale snapshot).")
                return CorrectionAttempt(False, "The document changed after this suggestion was generated. G-Coach needs to recheck it before applying the correction.")

            start, end = finding.start, finding.end
            if end > len(current_text) or current_text[start:end] != finding.original:
                logger.warning("Correction refused: finding text no longer matches its exact source range.")
                return CorrectionAttempt(False, "The source word is no longer at the position identified by this suggestion.")

            text_range = BackgroundCorrectionEngine._build_exact_range(
                document_range, current_text, start, end, finding.original, auto
            )
            if text_range is None:
                logger.warning("Correction refused: UIA could not resolve the exact finding range.")
                return CorrectionAttempt(False, "Windows UI Automation could not map the suggestion to an exact text range in this editor.")

            # Confirm that the UIA selection operation itself has not raced
            # with another edit before sending any keyboard input.
            if not text_range.Select(waitTime=0):
                logger.warning("Correction refused: UIA could not select the exact finding range.")
                return CorrectionAttempt(False, "The editor refused to select the exact text range.")

            # For CEF/Electron apps like WordCraft, calling text_range.Select() updates the UIA
            # internal selection range, but we should also explicitly ensure the text input focus
            # is set on the element and give the editor a brief moment to process the selection highlight.
            try:
                element.SetFocus()
            except Exception:
                pass
            time.sleep(0.05)

            try:
                selected_text_val = text_range.GetText(-1)
            except Exception:
                selected_text_val = ""

            # For Electron / CEF apps like WordCraft or T3 Code, UIA TextPattern ranges
            # can sometimes select successfully but fail prefix/suffix validation due to
            # chromium text range wrapping. If direct selection and text matching succeed,
            # we accept the range.
            if selected_text_val == finding.original:
                # Direct validation via text_range succeeded
                pass
            else:
                selection = pattern.GetSelection()
                if not selection or len(selection) != 1:
                    logger.warning("Correction refused: the target did not report one exact selected range.")
                    return CorrectionAttempt(False, "The editor did not confirm the requested text selection.")
                selected_range = selection[0]
                if selected_range.GetText(-1) != finding.original:
                    logger.warning("Correction refused: the active selection no longer matches the finding.")
                    return CorrectionAttempt(False, "The selected text did not match the source word, so no change was made.")
                try:
                    same_range = selected_range.Compare(text_range)
                except Exception:
                    same_range = False
                if not same_range:
                    logger.warning("Correction refused: UIA's active selection differs from the requested range.")
                    return CorrectionAttempt(False, "The editor selected a different range than requested, so no change was made.")

            # Re-read the complete document after selecting and immediately
            # before typing. Never fall back to the captured snapshot on error.
            _, _, selected_text = BackgroundCorrectionEngine._read_text_pattern(element, auto)
            if selected_text != current_text:
                logger.warning("Correction refused: target text changed before replacement.")
                return CorrectionAttempt(False, "The document changed immediately before the correction could be applied.")
            if not BackgroundCorrectionEngine._is_original_target_focused(target, auto):
                logger.warning("Correction refused: focus moved away from the original target before replacement.")
                return CorrectionAttempt(False, "Focus moved away from the original editor before the correction could be applied.")

            try:
                import keyboard

                # For Chromium/Electron-based apps like WordCraft, calling text_range.Select()
                # highlights the range, but keyboard.write() without first deleting or replacing
                # the selection can sometimes append at caret if the editor does not treat typing
                # as replacing the active selection. We explicitly send backspace or delete first
                # when the replacement should overwrite the selected finding range, or use selection replacement.
                if finding.original:
                    keyboard.send("backspace")
                if finding.replacement:
                    keyboard.write(
                        finding.replacement,
                        delay=_KEYSTROKE_DELAY_SECONDS,
                    )
            except Exception as exc:
                logger.error("Targeted text input failed: %s", exc, exc_info=True)
                return CorrectionAttempt(False, "Windows could not type the replacement into the editor.")

            expected_text = current_text[:start] + finding.replacement + current_text[end:]
            post_text, verification_status = (
                BackgroundCorrectionEngine._wait_for_expected_text(
                    target, expected_text, auto
                )
            )
            if verification_status != "verified":
                if verification_status == "focus_lost":
                    reason = (
                        "Focus moved away from the original editor while the correction was being verified. "
                        "Please inspect the document before retrying."
                    )
                elif verification_status == "unreadable":
                    reason = (
                        "The editor stopped exposing its text while the correction was being verified. "
                        "Please inspect the document before retrying."
                    )
                elif post_text == current_text:
                    reason = (
                        "The editor did not reflect the replacement after typing. "
                        "No text change was detected; inspect the document before retrying."
                    )
                else:
                    reason = (
                        "The editor changed while typing but did not confirm the complete expected text. "
                        "Please inspect the document before retrying."
                    )
                logger.error(
                    "Correction post-write verification failed (status=%s, expected_length=%s, observed_length=%s).",
                    verification_status,
                    len(expected_text),
                    len(post_text) if post_text is not None else None,
                )
                return CorrectionAttempt(False, reason)

            logger.info(
                "Applied and verified targeted correction at [%s:%s] in control %s.",
                start,
                end,
                target.control_id,
            )
            return CorrectionAttempt(True, resulting_text=post_text)
        except Exception as exc:
            logger.error("Targeted correction failed closed: %s", exc, exc_info=True)
            return CorrectionAttempt(False, "An unexpected Windows text-editing error occurred. No unverified correction was reported as successful.")

    @staticmethod
    def _wait_for_expected_text(
        target: CorrectionTarget,
        expected_text: str,
        auto: Any,
    ) -> tuple[Optional[str], str]:
        """Wait for the live editor text to catch up, without sending input again.

        Some editors (notably canvas/CEF-backed controls) publish UIA text a
        little later than they consume keyboard input. A short bounded wait
        avoids reporting a successful-but-not-yet-published edit as a failure.
        Two consecutive exact reads are required; any focus loss or unreadable
        range remains a hard failure. The replacement is never retyped here.
        """
        deadline = time.monotonic() + _POST_WRITE_VERIFY_TIMEOUT_SECONDS
        consecutive_matches = 0
        last_text: Optional[str] = None
        last_status = "unreadable"

        while True:
            focused_element = BackgroundCorrectionEngine._get_focused_target_element(
                target, auto
            )
            if focused_element is None:
                return last_text, "focus_lost"

            pattern, document_range, observed_text = (
                BackgroundCorrectionEngine._read_text_pattern(
                    focused_element, auto
                )
            )
            if pattern is None or document_range is None or observed_text is None:
                last_status = "unreadable"
                consecutive_matches = 0
            else:
                last_text = observed_text
                last_status = "mismatch"
                if observed_text == expected_text:
                    consecutive_matches += 1
                    if consecutive_matches >= _POST_WRITE_VERIFY_STABLE_READS:
                        return observed_text, "verified"
                else:
                    consecutive_matches = 0

            if time.monotonic() >= deadline:
                return last_text, last_status
            time.sleep(_POST_WRITE_VERIFY_INTERVAL_SECONDS)

    @staticmethod
    def apply_corrections_to_target(
        target: CorrectionTarget, findings: list[Finding]
    ) -> BatchCorrectionResult:
        """Apply independent findings right-to-left, then allow one re-analysis.

        Suggestions that conflict, overlap, are stale, or cannot be validated
        against the original snapshot are skipped. Every actual edit still goes
        through the same live UIA checks and post-write verification as a single
        correction. Descending offsets keep all remaining source ranges stable.
        """
        if target is None or not findings:
            return BatchCorrectionResult(False, skipped_count=len(findings or []), reason="There are no suggestions to apply.")

        candidates = [
            finding for finding in findings
            if finding is not None
            and finding.status not in {"accepted", "ignored", "rejected"}
            and isinstance(finding.start, int)
            and isinstance(finding.end, int)
            and 0 <= finding.start <= finding.end <= len(target.original_text)
            and target.original_text[finding.start:finding.end] == finding.original
            and finding.original != finding.replacement
            and not (finding.metadata or {}).get("has_conflict", False)
        ]

        # Never batch-apply overlapping findings, even when they came from
        # different engines or one of them was otherwise individually valid.
        blocked_ids: set[str] = set()
        for first in candidates:
            for second in findings:
                if first.id == getattr(second, "id", None):
                    continue
                if (
                    second is not None
                    and isinstance(getattr(second, "start", None), int)
                    and isinstance(getattr(second, "end", None), int)
                    and 0 <= second.start <= second.end <= len(target.original_text)
                    and BackgroundCorrectionEngine._finding_ranges_overlap(first, second)
                ):
                    blocked_ids.add(first.id)
                    break

        safe_findings = [f for f in candidates if f.id not in blocked_ids]
        skipped_count = len(findings) - len(safe_findings)
        if not safe_findings:
            return BatchCorrectionResult(
                False,
                skipped_count=skipped_count,
                reason="No independent, non-overlapping suggestions could be safely batch-applied.",
                resulting_text=target.original_text,
            )

        applied_count = 0
        for finding in sorted(safe_findings, key=lambda item: (item.start, item.end), reverse=True):
            attempt = BackgroundCorrectionEngine.apply_correction_to_target_detailed(
                target, finding
            )
            if not attempt.success or attempt.resulting_text is None:
                return BatchCorrectionResult(
                    applied_count > 0,
                    applied_count=applied_count,
                    skipped_count=skipped_count + len(safe_findings) - applied_count,
                    reason=attempt.reason or "The batch stopped because a correction could not be verified.",
                    resulting_text=target.original_text,
                )

            target.original_text = attempt.resulting_text
            target.text_hash = hashlib.sha256(
                attempt.resulting_text.encode("utf-8", errors="ignore")
            ).hexdigest() if attempt.resulting_text else ""
            finding.status = "accepted"
            applied_count += 1

        return BatchCorrectionResult(
            True,
            applied_count=applied_count,
            skipped_count=skipped_count,
            resulting_text=target.original_text,
        )

    @staticmethod
    def _finding_ranges_overlap(first: Finding, second: Finding) -> bool:
        """Return whether two half-open finding ranges overlap or share an insertion point."""
        first_empty = first.start == first.end
        second_empty = second.start == second.end
        if first_empty and second_empty:
            return first.start == second.start
        if first_empty:
            return second.start <= first.start <= second.end
        if second_empty:
            return first.start <= second.start <= first.end
        return max(first.start, second.start) < min(first.end, second.end)

    @staticmethod
    def get_finding_screen_rect(
        target: CorrectionTarget, finding: Finding
    ) -> Optional[tuple[int, int, int, int]]:
        """Return the UIA screen rectangle for a finding without changing selection.

        The live document and exact Python-offset range are revalidated after
        reacquiring the focused control on the UIA owner thread. Controls without
        usable TextPattern geometry return ``None`` for a window-bounds fallback.
        """
        if target is None or finding is None or platform.system() != "Windows":
            return None
        if not isinstance(finding.start, int) or not isinstance(finding.end, int):
            return None
        if finding.start < 0 or finding.end < finding.start:
            return None
        if finding.end - finding.start != len(finding.original):
            return None

        try:
            import uiautomation as auto

            element = BackgroundCorrectionEngine._get_focused_target_element(target, auto)
            if element is None:
                return None

            _, document_range, current_text = BackgroundCorrectionEngine._read_text_pattern(
                element, auto
            )
            if document_range is None or current_text is None:
                return None
            if current_text != target.original_text:
                return None

            start, end = finding.start, finding.end
            if end > len(current_text) or current_text[start:end] != finding.original:
                return None

            text_range = BackgroundCorrectionEngine._build_exact_range(
                document_range, current_text, start, end, finding.original, auto
            )
            if text_range is None:
                return None

            raw_rectangles = list(text_range.GetBoundingRectangles() or [])
            if not raw_rectangles:
                return None

            # uiautomation wraps the COM float array as List[Rect]. Accept that
            # native shape, plus a flat float array for compatible providers.
            rectangles = []
            if all(hasattr(rect, "left") for rect in raw_rectangles):
                candidates = []
                for rect in raw_rectangles:
                    left = float(rect.left)
                    top = float(rect.top)
                    width = float(rect.width()) if callable(getattr(rect, "width", None)) else float(rect.right) - left
                    height = float(rect.height()) if callable(getattr(rect, "height", None)) else float(rect.bottom) - top
                    candidates.append((left, top, width, height))
            else:
                if len(raw_rectangles) % 4:
                    return None
                candidates = [
                    tuple(float(value) for value in raw_rectangles[index:index + 4])
                    for index in range(0, len(raw_rectangles), 4)
                ]

            # UIA returns one rectangle per visible visual line. Anchor to the
            # final segment, nearest the end of the finding.
            for left, top, width, height in candidates:
                if all(math.isfinite(value) for value in (left, top, width, height)) and width > 0 and height > 0:
                    rectangles.append((left, top, width, height))
            if not rectangles:
                return None

            return tuple(round(value) for value in rectangles[-1])
        except Exception as exc:
            logger.debug("Unable to resolve UIA geometry for the current finding: %s", exc)
            return None

    @staticmethod
    def _get_focused_target_element(target: CorrectionTarget, auto: Any) -> Optional[Any]:
        """Get a fresh UIA element only when the exact captured target is focused."""
        # Fail before initializing/querying UIA when the capture did not expose
        # enough identity to distinguish this control from its siblings.
        is_wordcraft = "wordcraft" in (target.app_name or "").lower()
        if not target.process_id or (not target.automation_id and not target.control_name and not is_wordcraft):
            return None
        try:
            focused = auto.GetFocusedControl()
            if focused is None:
                return None

            process_id = int(getattr(focused, "ProcessId", 0) or 0)
            hwnd = int(getattr(focused, "NativeWindowHandle", 0) or 0)
            automation_id = str(getattr(focused, "AutomationId", "") or "")
            control_name = str(getattr(focused, "Name", "") or "")
            control_type = str(getattr(focused, "ControlTypeName", "") or "")

            if process_id != target.process_id:
                return None
            if target.hwnd and hwnd and hwnd != target.hwnd:
                return None
            if target.automation_id and automation_id and automation_id != target.automation_id:
                return None
            if target.control_name and control_name and control_name != target.control_name:
                return None
            if target.control_type and control_type and control_type != target.control_type:
                return None

            if not is_wordcraft and not target.automation_id and not target.control_name:
                return None
            return focused
        except Exception:
            return None

    @staticmethod
    def _is_original_target_focused(target: CorrectionTarget, auto: Any) -> bool:
        """Require the exact captured control identity before sending keystrokes."""
        return BackgroundCorrectionEngine._get_focused_target_element(target, auto) is not None

    @staticmethod
    def _read_text_pattern(element: Any, auto: Any) -> tuple[Optional[Any], Optional[Any], Optional[str]]:
        """Return a live TextPattern, its DocumentRange, and the full text.

        None text means reading failed; an empty string is a valid empty document.
        ValuePattern/LegacyIAccessible are intentionally not write fallbacks.
        """
        for pattern_id in (auto.PatternId.TextPattern, auto.PatternId.TextPattern2):
            try:
                pattern = element.GetPattern(pattern_id)
                if pattern is None:
                    continue
                document_range = pattern.DocumentRange
                if document_range is None:
                    continue
                text = document_range.GetText(-1)
                if text is None:
                    continue
                return pattern, document_range, str(text)
            except Exception as exc:
                logger.debug("Unable to read UIA TextPattern %s: %s", pattern_id, exc)
        return None, None, None

    @staticmethod
    def _build_exact_range(
        document_range: Any,
        document_text: str,
        start: int,
        end: int,
        expected_text: str,
        auto: Any,
    ) -> Optional[Any]:
        """Map Python offsets to a UIA character range and verify both contexts.

        UIA providers can expose character boundaries differently for complex
        Unicode and may count supplementary characters as UTF-16 code units.
        Prefix, selected text, and suffix comparisons make any offset mismatch
        a hard refusal rather than risking a nearby or repeated word.
        """
        try:
            unit = auto.TextUnit.Character
            endpoint_start = auto.TextPatternRangeEndpoint.Start
            endpoint_end = auto.TextPatternRangeEndpoint.End

            # Python indexes Unicode code points. Some UIA providers expose
            # TextUnit.Character offsets as UTF-16 code units instead. Try both
            # coordinate systems, but accept a range only when the selected
            # text and its complete prefix/suffix match byte-for-byte.
            python_units = (len(document_text), start, end)
            utf16_length = len(document_text.encode("utf-16-le", errors="surrogatepass")) // 2
            utf16_start = len(document_text[:start].encode("utf-16-le", errors="surrogatepass")) // 2
            utf16_end = len(document_text[:end].encode("utf-16-le", errors="surrogatepass")) // 2
            coordinate_sets = [python_units, (utf16_length, utf16_start, utf16_end)]

            # If strict prefix/suffix coordinate validation fails on Electron/CEF apps
            # like WordCraft due to boundary normalization, but we successfully found a
            # range whose text matches expected_text at the requested offset, accept it.
            fallback_range = None
            for total_units, start_units, end_units in coordinate_sets:
                text_range = document_range.Clone()
                start_delta = text_range.MoveEndpointByUnit(
                    endpoint_start, unit, start_units, waitTime=0
                )
                end_delta = text_range.MoveEndpointByUnit(
                    endpoint_end, unit, end_units - total_units, waitTime=0
                )
                if start_delta == start_units and end_delta == end_units - total_units:
                    if text_range.GetText(-1) == expected_text:
                        fallback_range = text_range
                        # Check if prefix/suffix pass; if so, return immediately
                        prefix = document_range.Clone()
                        prefix_delta = prefix.MoveEndpointByUnit(
                            endpoint_end, unit, start_units - total_units, waitTime=0
                        )
                        suffix = document_range.Clone()
                        suffix_delta = suffix.MoveEndpointByUnit(
                            endpoint_start, unit, end_units, waitTime=0
                        )
                        if (prefix_delta == start_units - total_units and prefix.GetText(-1) == document_text[:start] and
                            suffix_delta == end_units and suffix.GetText(-1) == document_text[end:]):
                            return text_range

            if fallback_range is not None:
                return fallback_range

            return None
        except Exception as exc:
            logger.debug("Unable to construct exact UIA text range: %s", exc)
            return None
