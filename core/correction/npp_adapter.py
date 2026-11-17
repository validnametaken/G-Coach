"""
G-Coach Notepad++ Correction Adapter (Clipboard-based Fallback)
Handles robust text replacement for Notepad++ (notepad++.exe) using clipboard operations.
"""

from __future__ import annotations

import logging
import platform
import time
from typing import Optional
from core.analysis import Finding
from core.correction.target import CorrectionTarget

logger = logging.getLogger(__name__)

class NppCorrectionAdapter:
    """Notepad++ 修正适配器（基于剪贴板全文档替换）"""

    @staticmethod
    def is_notepad_target(target: CorrectionTarget) -> bool:
        """检查目标是否为 Notepad++ 应用程序"""
        if not target:
            return False
        app_name = (target.app_name or "").lower()
        hwnd_str = str(target.hwnd or "")
        return "notepad++" in app_name or "notepad++.exe" in app_name or "notepad++" in hwnd_str.lower()

    @staticmethod
    def apply_bridge_correction(target: CorrectionTarget, finding: Finding) -> bool:
        """通过剪贴板全文档替换安全地修正 Notepad++ 中的错误文本"""
        if not NppCorrectionAdapter.is_notepad_target(target):
            return False

        if platform.system() != "Windows":
            logger.debug("NppCorrectionAdapter skipped: not Windows platform.")
            return False

        try:
            import keyboard
            import pyperclip
            import time

            old_clipboard = pyperclip.paste()
            keyboard.send("ctrl+a")
            time.sleep(0.1)
            keyboard.send("ctrl+c")
            time.sleep(0.1)

            doc_text = pyperclip.paste()
            if not doc_text:
                pyperclip.copy(old_clipboard)
                return False

            start, end = finding.start, finding.end
            if start >= len(doc_text) or doc_text[start:end] != finding.original:
                idx = doc_text.find(finding.original, max(0, start - 20))
                if idx == -1:
                    idx = doc_text.find(finding.original)
                if idx != -1:
                    start, end = idx, idx + len(finding.original)
                else:
                    logger.warning("Notepad++ correction failed: original text %r not found in document.", finding.original)
                    pyperclip.copy(old_clipboard)
                    return False

            new_doc_text = doc_text[:start] + finding.replacement + doc_text[end:]
            pyperclip.copy(new_doc_text)
            time.sleep(0.05)

            keyboard.send("ctrl+a")
            time.sleep(0.05)
            keyboard.send("ctrl+v")
            time.sleep(0.2)

            pyperclip.copy(old_clipboard)
            return True
        except Exception as exc:
            logger.error(f"Notepad++ correction error: {exc}", exc_info=True)
            return False
