"""
G-Coach WordCraft Correction Adapter (Phase 8G.7)
Handles specialized text replacement for WordCraft (wordcraft.exe) where UIA TextRange selection
highlights text visually but doesn't bind keyboard typing to the selection range.
"""

from __future__ import annotations

import logging
import platform
import time
from typing import Optional
from core.analysis import Finding
from core.correction.target import CorrectionTarget

logger = logging.getLogger(__name__)

class WordCraftCorrectionAdapter:
    """WordCraft 专用修正适配器
    
    针对 WordCraft (wordcraft.exe) 的 Electron/Chromium 编辑器特性，
    通过全文档替换或光标导航确保纠正能够正确覆盖错误单词。
    """

    @staticmethod
    def is_wordcraft_target(target: CorrectionTarget) -> bool:
        """检查目标是否为 WordCraft 应用程序"""
        if not target:
            return False
        app_name = (target.app_name or "").lower()
        hwnd_str = str(target.hwnd or "")
        return "wordcraft" in app_name or "wordcraft.exe" in app_name or "wordcraft" in hwnd_str.lower()

    @staticmethod
    def apply_wordcraft_correction(target: CorrectionTarget, finding: Finding) -> bool:
        """通过剪贴板全文档或键盘精准定位替换 WordCraft 中的错误文本"""
        if not WordCraftCorrectionAdapter.is_wordcraft_target(target):
            return False

        if platform.system() != "Windows":
            return False

        try:
            import keyboard
            import pyperclip
            import time

            # 1. 备份当前剪贴板
            old_clipboard = pyperclip.paste()

            # 2. 全选当前文档 (Ctrl+A)，复制 (Ctrl+C)
            keyboard.send("ctrl+a")
            time.sleep(0.1)
            keyboard.send("ctrl+c")
            time.sleep(0.1)

            doc_text = pyperclip.paste()
            logger.info("WordCraft clipboard text length: %s, finding range: [%s:%s], original: %r, replacement: %r", len(doc_text), finding.start, finding.end, finding.original, finding.replacement)
            if not doc_text:
                pyperclip.copy(old_clipboard)
                return False

            # 3. 验证指定偏移处的原文是否匹配
            start, end = finding.start, finding.end
            if start >= len(doc_text) or doc_text[start:end] != finding.original:
                # 尝试在全文或合理范围内查找 finding.original
                idx = doc_text.find(finding.original, max(0, start - 20))
                if idx == -1:
                    idx = doc_text.find(finding.original)
                if idx != -1:
                    start, end = idx, idx + len(finding.original)
                else:
                    # 如果还找不到，尝试不区分大小写或去除空白搜索
                    lower_doc = doc_text.lower()
                    lower_orig = finding.original.lower()
                    idx = lower_doc.find(lower_orig)
                    if idx != -1:
                        start, end = idx, idx + len(finding.original)
                    else:
                        logger.warning("WordCraft correction failed: original text %r not found in document (clipboard length %s).", finding.original, len(doc_text))
                        pyperclip.copy(old_clipboard)
                        return False

            # 4. 替换文本
            new_doc_text = doc_text[:start] + finding.replacement + doc_text[end:]
            pyperclip.copy(new_doc_text)
            time.sleep(0.05)

            # 5. 粘贴回 WordCraft
            keyboard.send("ctrl+a")
            time.sleep(0.05)
            keyboard.send("ctrl+v")
            time.sleep(0.2) # Give Chromium / Electron time to process clipboard paste

            # 6. 恢复剪贴板
            pyperclip.copy(old_clipboard)
            return True

        except Exception as exc:
            logger.error(f"WordCraftCorrectionAdapter error: {exc}", exc_info=True)
            return False
