"""
实时监控模块包入口 - Phase 5
"""

from .capture import TextSnapshot, TextSource, MockTextSource, WindowsUIAccessibilityTextSource
from .monitor import MonitorState, LiveTextMonitor

__all__ = [
    "TextSnapshot",
    "TextSource",
    "MockTextSource",
    "WindowsUIAccessibilityTextSource",
    "MonitorState",
    "LiveTextMonitor",
]
