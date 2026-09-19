"""
分析引擎抽象基类与元数据 - Phase 1 Unified Analysis Foundation
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .finding import Finding


class BaseAnalysisEngine(ABC):
    """分析引擎抽象基类

    所有分析引擎（如 Harper, GECToR, no-ai-slop 以及测试引擎）
    均应继承此类并实现 analyze 方法及相关元数据属性。
    """

    def __init__(self, name: str, version: str = "1.0.0", is_local: bool = True):
        self._name = name
        self._version = version
        self._is_local = is_local

    @property
    def name(self) -> str:
        """引擎名称"""
        return self._name

    @property
    def version(self) -> str:
        """引擎版本"""
        return self._version

    @property
    def is_local(self) -> bool:
        """是否为本地/离线引擎"""
        return self._is_local

    @property
    def supported_types(self) -> List[str]:
        """支持的分析类型列表"""
        return ["grammar", "spelling", "style"]

    @property
    def supports_auto_fix(self) -> bool:
        """是否支持自动修复"""
        return True

    @abstractmethod
    def analyze(self, text: str) -> List[Finding]:
        """对输入文本进行分析，返回标准化 Findings 列表"""
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """获取引擎元数据"""
        return {
            "name": self.name,
            "version": self.version,
            "is_local": self.is_local,
            "supported_types": self.supported_types,
            "supports_auto_fix": self.supports_auto_fix,
        }
