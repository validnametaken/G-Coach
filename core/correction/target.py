"""
G-Coach Correction Target - Phase 8E
封装原始控件的来源证明与定位引用，确保纠正操作精确作用于原控件。
"""

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CorrectionTarget:
    """纠正目标（Correction Target）

    只保存普通 Python 身份信息与文本上下文，不保存 UIA COM 对象。
    用于在用户点击浮动弹窗时：
    1. 验证目标控件是否依然存在且处于正确状态
    2. 验证目标文本是否未被用户进一步修改（防呆与防陈旧结果保护）
    3. 在 UIA 所属线程重新获取目标控件并执行精确范围修正
    """
    control_id: str = ""
    process_id: int = 0
    hwnd: int = 0
    automation_id: str = ""
    control_name: str = ""
    control_type: str = ""
    app_name: str = ""
    original_text: str = ""
    text_hash: str = ""

    @classmethod
    def from_snapshot(cls, snapshot: Any) -> "CorrectionTarget":
        """从 TextSnapshot 构建不含线程绑定 COM 引用的 CorrectionTarget"""
        text = getattr(snapshot, "text", "")
        t_hash = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest() if text else ""
        meta = getattr(snapshot, "metadata", {})
        return cls(
            control_id=getattr(snapshot, "control_id", ""),
            process_id=getattr(snapshot, "process_id", 0),
            hwnd=int(meta.get("hwnd", 0)),
            automation_id=str(meta.get("automation_id", "")),
            control_name=str(meta.get("control_name", "")),
            control_type=getattr(snapshot, "control_type", ""),
            app_name=getattr(snapshot, "app_name", ""),
            original_text=text,
            text_hash=t_hash,
        )

    def validate_current_snapshot(self, current_snapshot: Any) -> bool:
        """校验当前快照是否仍然匹配原目标控件"""
        if not current_snapshot or current_snapshot.status == "unsupported":
            return False
        if self.control_id and current_snapshot.control_id != self.control_id:
            logger.warning(f"CorrectionTarget validation failed: control_id mismatch ({current_snapshot.control_id} != {self.control_id})")
            return False
        if self.process_id and current_snapshot.process_id != self.process_id:
            logger.warning(f"CorrectionTarget validation failed: process_id mismatch ({current_snapshot.process_id} != {self.process_id})")
            return False
        return True
