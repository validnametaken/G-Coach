"""
G-Coach UI Presentation & Formatting Logic - Phase 6
独立于具体 UI 框架的展示格式化与辅助逻辑，便于进行单元测试。
"""

from typing import List, Dict, Any, Optional
from core.analysis import Finding
from core.monitoring import MonitorState


class UIPresenter:
    """UI 展示转换与格式化器"""

    format_status_map = {
        "idle": "Idle",
        "waiting": "Waiting",
        "analyzing": "Analyzing",
        "ready": "Ready",
        "unsupported": "Unsupported",
        "error": "Error",
    }

    @classmethod
    def format_status(cls, status: str) -> str:
        """格式化监控/分析状态"""
        return cls.format_status_map.get(status, status.capitalize())

    @classmethod
    def format_app_info(cls, app_name: str, control_info: str) -> str:
        """格式化应用程序及控件信息"""
        if not app_name and not control_info:
            return "Application: Unknown"
        app = app_name or "Unknown"
        ctrl = f" ({control_info})" if control_info else ""
        return f"Application: {app}{ctrl}"

    @classmethod
    def format_finding_summary(cls, finding: Finding) -> str:
        """格式化单条 Finding 的摘要行（供列表显示）"""
        orig = finding.original
        rep = f" → {finding.replacement}" if finding.replacement else " (No replacement)"
        cat = f"[{finding.category}]"
        src = f"Source: {finding.source}"
        return f"{orig}{rep}  |  {cat}  |  {src}"

    @classmethod
    def format_finding_details(cls, finding: Finding) -> Dict[str, str]:
        """格式化单条 Finding 的详细属性（供详情/调试面板显示）"""
        return {
            "Original": finding.original,
            "Replacement": finding.replacement or "N/A",
            "Category": finding.category,
            "Message": finding.message,
            "Source Engine(s)": finding.source,
            "Confidence": f"{finding.confidence:.2f}" if finding.confidence is not None else "N/A",
            "Range": f"start={finding.start}, end={finding.end}",
            "Auto Fixable": "Yes" if finding.auto_fixable else "No",
            "Metadata": str(finding.metadata) if finding.metadata else "None",
        }

    @classmethod
    def group_findings_by_text(cls, findings: List[Finding]) -> Dict[str, List[Finding]]:
        """按原始内容对 Findings 进行分组（用于识别冲突或多引擎合并）"""
        groups: Dict[str, List[Finding]] = {}
        for f in findings:
            key = f.original
            if key not in groups:
                groups[key] = []
            groups[key].append(f)
        return groups

    @classmethod
    def is_pending(cls, status: str) -> bool:
        """检查状态是否为等待防抖或分析中"""
        return status in ("waiting", "analyzing")

    @classmethod
    def format_analyzing_message(cls, generation: int, status: str) -> str:
        """格式化分析中/等待中的提示信息"""
        if status == "waiting":
            return f"⏳ Waiting (debounce) for generation {generation}..."
        elif status == "analyzing":
            return f"🔍 Checking grammar and style (generation {generation})..."
        return f"Checking... (generation {generation})"

    @classmethod
    def format_state_summary(cls, state: MonitorState) -> Dict[str, Any]:
        """将 MonitorState 转换为 UI 友好的摘要结构"""
        status_str = cls.format_status(state.status)
        app_info = cls.format_app_info(state.app_name, state.control_info)
        findings_count = len(state.findings)
        
        # 检查冲突
        groups = cls.group_findings_by_text(state.findings)
        has_conflicts = any(len(group_list) > 1 for group_list in groups.values())

        return {
            "status_text": status_str,
            "app_info": app_info,
            "text": state.text,
            "findings_count": findings_count,
            "findings": state.findings,
            "has_conflicts": has_conflicts,
            "error_message": state.error_message,
            "timestamp": state.timestamp,
            "generation": state.generation,
            "is_pending": cls.is_pending(state.status),
            "pending_message": cls.format_analyzing_message(state.generation, state.status) if cls.is_pending(state.status) else "",
        }
