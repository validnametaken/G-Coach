"""
统一 findings 数据模型 - Phase 1 Unified Analysis Foundation
"""

import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional


@dataclass
class Finding:
    """标准化分析发现（Finding）数据结构

    表示由分析引擎检测到的写作问题或改进建议。
    文本范围 (start, end) 采用 Python 字符串的标准字符偏移量（character offsets）。
    """
    source: str
    category: str
    message: str
    original: str
    replacement: str
    start: int
    end: int
    confidence: float = 1.0
    severity: str = "error"  # "error", "warning", "style"
    auto_fixable: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "detected"  # "detected", "accepted", "rejected", "ignored"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将 Finding 转换为字典，便于序列化和 JSON 存储"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Finding":
        """从字典反序列化创建 Finding 对象"""
        return cls(**data)
