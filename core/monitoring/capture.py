"""
文本捕获抽象与 Windows UI Automation 基础 - Phase 5 Live Text Monitoring
"""

import abc
import logging
import platform
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


@dataclass
class TextSnapshot:
    """文本快照（Text Snapshot）

    包含捕获的文本内容、版本代数（generation）、时间戳以及控件身份与编辑状态元数据。
    """
    text: str = ""
    generation: int = 0
    timestamp: float = field(default_factory=time.time)
    app_name: str = ""
    control_info: str = ""
    control_id: str = ""
    control_type: str = ""
    process_id: int = 0
    is_editable: bool = True
    status: str = "idle"  # "idle", "ready", "unsupported", "error"
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


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

    def __init__(self, initial_text: str = "", app_name: str = "MockApp", status: str = "ready", control_id: str = "mock-ctrl-1", is_editable: bool = True):
        self.text = initial_text
        self.app_name = app_name
        self.status = status
        self.control_id = control_id
        self.is_editable = is_editable
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
            control_id=self.control_id,
            control_type="EditControl",
            process_id=1001,
            is_editable=self.is_editable,
            status=self.status if self.is_editable else "unsupported",
            error_message=None if self.is_editable else "Control is not editable",
        )


class MultiControlMockTextSource(TextSource):
    """支持多控件切换和不同 control_id 隔离的 Mock 文本源（用于 Phase 8A 单元测试）"""

    def __init__(self, controls: List[Dict[str, Any]]):
        self.controls = controls
        self.current_index = 0
        self.generation = 0

    def select_control(self, index: int):
        if 0 <= index < len(self.controls):
            self.current_index = index
            self.generation += 1

    def set_current_text(self, text: str):
        if self.controls:
            self.controls[self.current_index]["text"] = text
            self.generation += 1

    def get_current_text(self) -> TextSnapshot:
        if not self.controls:
            return TextSnapshot(status="unsupported")
        c = self.controls[self.current_index]
        is_editable = c.get("is_editable", True)
        return TextSnapshot(
            text=c.get("text", ""),
            generation=self.generation,
            timestamp=time.time(),
            app_name=c.get("app_name", "MockApp"),
            control_info=c.get("control_type", "Edit"),
            control_id=c.get("control_id", "ctrl-default"),
            control_type=c.get("control_type", "Edit"),
            process_id=c.get("process_id", 1000),
            is_editable=is_editable,
            status="ready" if is_editable else "unsupported",
            error_message=None if is_editable else "Control is not editable",
            metadata=c.get("metadata", {}),
        )


class WindowsUIAccessibilityTextSource(TextSource):
    """Windows UI Automation 文本源 (Phase 8A Global Windows Text Discovery)

    通过 Windows UI Automation API 动态检测当前具有键盘焦点的控件，
    验证其是否为可编辑文本控件，并安全提取文本、控件类型、进程 ID、句柄及 AutomationId。
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
                control_id="",
                control_type="",
                process_id=0,
                is_editable=False,
                status="unsupported",
                error_message="Windows UI Automation is only available on Windows platforms.",
            )

        try:
            snapshot_data = self._fetch_focused_control_via_uia()
            return TextSnapshot(
                text=snapshot_data["text"],
                generation=0,
                timestamp=time.time(),
                app_name=snapshot_data["app_name"],
                control_info=snapshot_data["control_info"],
                control_id=snapshot_data["control_id"],
                control_type=snapshot_data["control_type"],
                process_id=snapshot_data["process_id"],
                is_editable=snapshot_data["is_editable"],
                status="ready" if snapshot_data["is_editable"] else "unsupported",
                error_message=None if snapshot_data["is_editable"] else "Focused control is not editable.",
                metadata=snapshot_data["metadata"],
            )
        except Exception as e:
            logger.debug(f"Could not retrieve text via Windows UI Automation: {e}")
            return TextSnapshot(
                text="",
                generation=0,
                timestamp=time.time(),
                app_name="Unknown",
                control_info="Unknown",
                control_id="",
                control_type="",
                process_id=0,
                is_editable=False,
                status="unsupported",
                error_message=str(e),
            )

    def _fetch_focused_control_via_uia(self) -> Dict[str, Any]:
        import uiautomation as auto

        focused = auto.GetFocusedControl()
        if not focused:
            return {
                "text": "",
                "app_name": "Unknown",
                "control_info": "No Focus",
                "control_id": "",
                "control_type": "",
                "process_id": 0,
                "is_editable": False,
                "metadata": {},
            }

        control_type = str(focused.ControlTypeName)
        name = str(focused.Name or "")
        class_name = str(focused.ClassName or "")
        process_id = int(getattr(focused, "ProcessId", 0))
        hwnd = int(getattr(focused, "NativeWindowHandle", 0))
        automation_id = str(getattr(focused, "AutomationId", ""))

        is_editable = True
        non_editable_types = {"ButtonControl", "ImageControl", "TextControl", "CheckBoxControl", "RadioButtonControl", "MenuControl", "MenuItemControl", "ScrollBarControl", "ProgressBarControl", "SliderControl"}
        if control_type in non_editable_types:
            has_value_pattern = False
            has_text_pattern = False
            try:
                has_value_pattern = focused.GetPattern(auto.PatternId.ValuePattern) is not None
            except Exception:
                pass
            try:
                has_text_pattern = (focused.GetPattern(auto.PatternId.TextPattern) is not None) or (focused.GetPattern(auto.PatternId.TextPattern2) is not None)
            except Exception:
                pass
            if not has_value_pattern and not has_text_pattern:
                is_editable = False

        try:
            val_pattern = focused.GetPattern(auto.PatternId.ValuePattern)
            if val_pattern and getattr(val_pattern, "IsReadOnly", False):
                is_editable = False
        except Exception:
            pass

        text = ""
        for pattern_id in (auto.PatternId.TextPattern, auto.PatternId.TextPattern2):
            try:
                pattern = focused.GetPattern(pattern_id)
                if pattern:
                    document_range = pattern.DocumentRange
                    if document_range:
                        text = document_range.GetText(65535) or ""
                        if text:
                            break
            except Exception:
                pass

        if not text:
            try:
                val_pattern = focused.GetPattern(auto.PatternId.ValuePattern)
                if val_pattern:
                    text = val_pattern.Value or ""
            except Exception:
                pass

        if not text:
            try:
                acc_pattern = focused.GetPattern(auto.PatternId.LegacyIAccessiblePattern)
                if acc_pattern:
                    text = acc_pattern.Value or acc_pattern.Name or ""
            except Exception:
                pass

        if not text and name and control_type in {"EditControl", "DocumentControl"}:
            text = name

        control_id = f"pid:{process_id}-hwnd:{hwnd}-autoid:{automation_id}-type:{control_type}-name:{name}"

        app_name = class_name or control_type
        try:
            import win32process
            import win32api
            if hwnd:
                handle = win32api.OpenProcess(0x1000, False, process_id)
                path = win32process.GetModuleFileNameEx(handle, 0)
                win32api.CloseHandle(handle)
                app_name = path.rsplit("\\", 1)[-1]
        except Exception:
            pass

        control_info = f"{control_type} | {name}" if name else control_type

        return {
            "text": text,
            "app_name": app_name,
            "control_info": control_info,
            "control_id": control_id,
            "control_type": control_type,
            "process_id": process_id,
            "is_editable": is_editable,
            "metadata": {
                "automation_id": automation_id,
                "hwnd": hwnd,
                "class_name": class_name,
            },
        }
