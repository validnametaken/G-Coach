"""
G-Coach Correction Target - Phase 8E
封装原始控件的来源证明与定位引用，确保纠正操作精确作用于原控件。
"""

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class CorrectionTarget:
    """纠正目标（Correction Target）

    封装源控件的唯一身份标识与上下文特征，用于在用户点击浮动弹窗时：
    1. 验证目标控件是否依然存在且处于正确状态
    2. 验证目标文本是否未被用户进一步修改（防呆与防陈旧结果保护）
    3. 安全地执行无焦点后台文本更新 (ValuePattern.SetValue)
    """
    control_id: str = ""
    process_id: int = 0
    hwnd: int = 0
    automation_id: str = ""
    control_type: str = ""
    app_name: str = ""
    original_text: str = ""
    text_hash: str = ""
    element_ref: Optional[Any] = field(default=None, repr=False)

    @classmethod
    def from_snapshot(cls, snapshot: Any, element_ref: Optional[Any] = None) -> "CorrectionTarget":
        """从 TextSnapshot 和 UI Automation 元素构建 CorrectionTarget"""
        text = getattr(snapshot, "text", "")
        t_hash = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest() if text else ""
        meta = getattr(snapshot, "metadata", {})
        return cls(
            control_id=getattr(snapshot, "control_id", ""),
            process_id=getattr(snapshot, "process_id", 0),
            hwnd=int(meta.get("hwnd", 0)),
            automation_id=str(meta.get("automation_id", "")),
            control_type=getattr(snapshot, "control_type", ""),
            app_name=getattr(snapshot, "app_name", ""),
            original_text=text,
            text_hash=t_hash,
            element_ref=element_ref,
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
