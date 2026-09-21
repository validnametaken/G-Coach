"""
G-Coach Interactive Correction Controller - Phase 7
"""

import logging
from typing import Optional, Dict, Any, List
from core.analysis import Finding

logger = logging.getLogger(__name__)


class CorrectionResult:
    """交互式修正操作的结果数据结构"""

    def __init__(
        self,
        success: bool,
        new_text: str = "",
        message: str = "",
        error_message: Optional[str] = None,
        applied_finding: Optional[Finding] = None,
    ):
        self.success = success
        self.new_text = new_text
        self.message = message
        self.error_message = error_message
        self.applied_finding = applied_finding

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "new_text": self.new_text,
            "message": self.message,
            "error_message": self.error_message,
            "applied_finding": self.applied_finding.to_dict() if self.applied_finding else None,
        }


class CorrectionController:
    """交互式修正控制器（Correction Controller）

    负责在保持与分析引擎完全独立的前提下，安全地对指定文本和 Finding 执行：
    1. Accept (替换指定 [start:end] 区间)
    2. Delete (删除指定区间)
    3. Insert (在 [start:end] (start == end) 处插入)
    4. Range Validation & Stale Finding Detection (严格校验 text[start:end] == finding.original)
    5. Ignore / Reject (更新 Finding 状态为 ignored / rejected)
    6. Conflict Refusal (拒绝未消解或有冲突的 Finding 自动应用，除非显式选择)
    """

    def __init__(self):
        pass

    def apply_acceptance(
        self, text: str, finding: Finding, all_findings: Optional[List[Finding]] = None
    ) -> CorrectionResult:
        """应用接受修正（Accept）

        参数：
            text: 当前源文本
            finding: 要应用的 Finding
            all_findings: 当前所有的 findings（用于检查该 Finding 是否存在未解决的冲突/歧义）
        """
        # 1. 冲突检查 (Conflict Refusal)
        if all_findings and self._has_conflict_for_finding(finding, all_findings):
            return CorrectionResult(
                success=False,
                error_message=f"Refusing correction: finding '{finding.original} → {finding.replacement}' has conflicting alternative suggestions. Please resolve ambiguity explicitly.",
                applied_finding=finding,
            )

        # 2. 检查 Finding 状态是否已被忽略或拒绝
        if finding.status in ("ignored", "rejected"):
            return CorrectionResult(
                success=False,
                error_message=f"Cannot apply correction: finding status is '{finding.status}'.",
                applied_finding=finding,
            )

        # 3. 边界与范围验证 (Range Validation & Stale Finding Detection)
        start = finding.start
        end = finding.end
        original = finding.original

        # 验证偏移量是否合法
        if start < 0 or end < start or end > len(text):
            return CorrectionResult(
                success=False,
                error_message=f"Stale finding rejection: offset range [{start}, {end}] is out of bounds for text of length {len(text)}.",
                applied_finding=finding,
            )

        # 插入处理 (Insert: original == "" and start == end)
        if original == "" and start == end:
            new_text = text[:start] + finding.replacement + text[start:]
            finding.status = "accepted"
            return CorrectionResult(
                success=True,
                new_text=new_text,
                message=f"Successfully inserted text at offset {start}.",
                applied_finding=finding,
            )

        # 删除处理 (Delete: replacement == "" and original != "")
        # 或者普通替换 (Replace)
        extracted = text[start:end]
        if extracted != original:
            return CorrectionResult(
                success=False,
                error_message=f"Stale finding rejection: source text at [{start}:{end}] is '{extracted}', but finding expected '{original}'. Text has changed.",
                applied_finding=finding,
            )

        # 执行替换或删除
        new_text = text[:start] + finding.replacement + text[end:]
        finding.status = "accepted"

        action_name = "deleted" if finding.replacement == "" else "replaced"
        return CorrectionResult(
            success=True,
            new_text=new_text,
            message=f"Successfully {action_name} range [{start}:{end}] ('{original}' → '{finding.replacement}').",
            applied_finding=finding,
        )

    def mark_ignored(self, finding: Finding) -> Finding:
        """标记 Finding 为 ignored"""
        finding.status = "ignored"
        return finding

    def mark_rejected(self, finding: Finding) -> Finding:
        """标记 Finding 为 rejected"""
        finding.status = "rejected"
        return finding

    def _has_conflict_for_finding(self, finding: Finding, all_findings: List[Finding]) -> bool:
        """检查该 finding 是否在 all_findings 中与其他 finding 存在冲突"""
        if finding.metadata and finding.metadata.get("has_conflict"):
            return True

        for f in all_findings:
            if f.id != finding.id:
                if (f.start == finding.start and f.end == finding.end) or (
                    f.original == finding.original and f.start == finding.start
                ):
                    if f.replacement != finding.replacement:
                        return True
        return False
