"""
文本捕获抽象与 Windows UI Automation 基础 - Phase 5 Live Text Monitoring
"""

import abc
import logging
import platform
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class TextSnapshot:
    """文本快照（Text Snapshot）

    包含捕获的文本内容、版本代数（generation）、时间戳以及控件元数据。
    """
    text: str = ""
    generation: int = 0
    timestamp: float = field(default_factory=time.time)
    app_name: str = ""
    control_info: str = ""
    status: str = "idle"  # "idle", "ready", "unsupported", "error"
    error_message: Optional[str] = None


class TextSource(abc.ABC):
    """文本源抽象基类（Text Source Abstraction）

    与平台特定的 UI 访问解耦，允许在测试中使用 Mock 文本源，
    同时为 Windows UI Automation 提供底层扩展。
    """

    @abc.abstractmethod
    def get_current_text(self) -> TextSnapshot:
        """获取当前聚焦控件的文本快照"""
        pass


class MockTextSource(TextSource):
    """用于测试和非 Windows 环境的模拟文本源（Mock Text Source）"""

    def __init__(self, initial_text: str = "", app_name: str = "MockApp", status: str = "ready"):
        self.text = initial_text
        self.app_name = app_name
        self.status = status
        self.generation = 0

    def set_text(self, new_text: str):
        self.text = new_text
        self.generation += 1

    def get_current_text(self) -> TextSnapshot:
        return TextSnapshot(
            text=self.text,
            generation=self.generation,
            timestamp=time.time(),
            app_name=self.app_name,
            control_info="MockControl",
            status=self.status,
        )


class WindowsUIAccessibilityTextSource(TextSource):
    """Windows UI Automation 文本源

    通过 Windows UI Automation API 尝试获取当前聚焦控件的文本内容。
    在非 Windows 平台或无法访问时，优雅地返回 unsupported 状态。
    """

    def __init__(self):
        self._is_windows = platform.system() == "Windows"

    def get_current_text(self) -> TextSnapshot:
        if not self._is_windows:
            return TextSnapshot(
                text="",
                generation=0,
                timestamp=time.time(),
                app_name="Non-Windows",
                control_info="None",
                status="unsupported",
                error_message="Windows UI Automation is only available on Windows platforms.",
            )

        try:
            text, app_name, control_info = self._fetch_via_uia()
            return TextSnapshot(
                text=text,
                generation=0,
                timestamp=time.time(),
                app_name=app_name,
                control_info=control_info,
                status="ready",
            )
        except Exception as e:
            logger.debug(f"Could not retrieve text via Windows UI Automation: {e}")
            return TextSnapshot(
                text="",
                generation=0,
                timestamp=time.time(),
                app_name="Unknown",
                control_info="Unknown",
                status="unsupported",
                error_message=str(e),
            )

    def _fetch_via_uia(self) -> tuple:
        """底层 Windows UI Automation 访问逻辑桩"""
        raise NotImplementedError("Windows UIA native binding requires active GUI session.")
