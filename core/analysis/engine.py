"""
Abstract base class and metadata for analysis engines - Phase 1 Unified Analysis Foundation
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .finding import Finding


class BaseAnalysisEngine(ABC):
    """Abstract base class for analysis engines

    All analysis engines (such as Harper, GECToR, no-ai-slop, and test engines)
    should inherit from this class and implement the analyze method and related metadata properties.
    """

    def __init__(self, name: str, version: str = "1.0.0", is_local: bool = True):
        self._name = name
        self._version = version
        self._is_local = is_local

    @property
    def name(self) -> str:
        """Engine name"""
        return self._name

    @property
    def version(self) -> str:
        """Engine version"""
        return self._version

    @property
    def is_local(self) -> bool:
        """Whether it is a local/offline engine"""
        return self._is_local

    @property
    def supported_types(self) -> List[str]:
        """List of supported analysis types"""
        return ["grammar", "spelling", "style"]

    @property
    def supports_auto_fix(self) -> bool:
        """Whether auto-fix is supported"""
        return True

    @abstractmethod
    def analyze(self, text: str) -> List[Finding]:
        """Analyze input text and return a list of standardized Findings"""
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """Get engine metadata"""
        return {
            "name": self.name,
            "version": self.version,
            "is_local": self.is_local,
            "supported_types": self.supported_types,
            "supports_auto_fix": self.supports_auto_fix,
        }
