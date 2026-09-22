"""
G-Coach Floating Correction Popup (PyQt6) - Phase 8E
悬浮纠正弹窗：在不抢占外部应用程序焦点（使用 WS_EX_NOACTIVATE）的前提下，
在屏幕指定位置渲染建议并提供 [Accept] / [Ignore] 交互。
"""

import logging
import platform
from typing import Optional, Callable, Any, Tuple, Union

logger = logging.getLogger(__name__)

try:
    from PyQt6.QtCore import Qt, QPoint
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
    from PyQt6.QtGui import QMouseEvent
    PYQT_AVAILABLE = True
except (ImportError, OSError) as e:
    logger.warning(f"PyQt6 not available for FloatingCorrectionPopup: {e}")
    PYQT_AVAILABLE = False
    QWidget = object  # type: ignore


class FloatingCorrectionPopup(QWidget if PYQT_AVAILABLE else object):
    """浮动纠正弹窗（Floating Correction Popup）

    具备如下核心特性：
    1. 非抢焦特性 (Non-activating)：使用 Qt.Tool, Qt.FramelessWindowHint, Qt.WindowStaysOnTopHint 并在 Windows 上应用 WS_EX_NOACTIVATE。
    2. 精准定位：显示在距错误文本最近的屏幕坐标位置。
    3. 简洁交互：提供 [Accept] 与 [Ignore / Dismiss (×)] 按钮。
    """

    def __init__(
        self,
        finding: Any,
        target: Any,
        on_accept: Callable[[Any, Any], None],
        on_ignore: Callable[[Any], None],
        parent: Optional[QWidget] = None,
    ):
        if not PYQT_AVAILABLE:
            raise RuntimeError("PyQt6 is required for FloatingCorrectionPopup.")
        import os
        config_mode = os.environ.get("GCOACH_POPUP_TEST", "A").strip().upper()
        if config_mode == "H":
            super().__init__(parent)
            self.finding = finding
            self.target = target
            self.on_accept = on_accept
            self.on_ignore = on_ignore
            self._init_window_flags()
            self._init_ui()
            return

        print("[Phase8E isolation] popup constructor entered")
        super().__init__(parent)
        print("[Phase8E isolation] super().__init__ completed")
        self.finding = finding
        self.target = target
        self.on_accept = on_accept
        self.on_ignore = on_ignore

        self._init_window_flags()
        print("[Phase8E isolation] popup constructor completed")
        self._init_ui()

    def _init_window_flags(self):
        """配置窗口标志以确保悬浮、置顶且绝不抢占目标应用焦点"""
        import os
        config_mode = os.environ.get("GCOACH_POPUP_TEST", "A").strip().upper()
        if not config_mode:
            config_mode = "A"
        print(f"[Phase8E diagnostic] Popup configuration: {config_mode}")

        if config_mode == "H":
            print("H constructor entered")
            print("H super().__init__ completed")
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            print("H flags configured")
            return

        if config_mode == "I":
            print("I constructor entered")
            print("I super().__init__ completed")
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
            print("I flags configured")
            return

        if config_mode == "J":
            print("J constructor entered")
            print("J super().__init__ completed")
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
            print("J flags configured")
            return

        if config_mode == "K":
            print("K constructor entered")
            print("K super().__init__ completed")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            print("K flags configured")
            return

        # 确定 Qt 窗口标志
        tool_flag = Qt.WindowType.Tool if config_mode != "E" else Qt.WindowType.Window
        focus_flag = Qt.WindowType.WindowDoesNotAcceptFocus if config_mode not in ("C", "D") else Qt.WindowType(0)

        flags = tool_flag | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        if focus_flag:
            flags |= focus_flag

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # 在 Windows 平台上应用 WS_EX_NOACTIVATE (0x08000000) 扩展样式（除非配置 B 或 D 或 F）
        if platform.system() == "Windows" and config_mode not in ("B", "D", "F"):
            try:
                import ctypes
                hwnd = int(self.winId())
                if hwnd:
                    user32 = ctypes.windll.user32

                    # 配置 GetWindowLongPtrW 签名
                    get_window_long_ptr = user32.GetWindowLongPtrW
                    get_window_long_ptr.argtypes = [ctypes.c_void_p, ctypes.c_int]
                    get_window_long_ptr.restype = ctypes.c_ssize_t

                    # 配置 SetWindowLongPtrW 签名
                    set_window_long_ptr = user32.SetWindowLongPtrW
                    set_window_long_ptr.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
                    set_window_long_ptr.restype = ctypes.c_ssize_t

                    ex_style = get_window_long_ptr(hwnd, -20)  # GWL_EXSTYLE = -20
                    if ex_style != 0 or ctypes.get_last_error() == 0:
                        new_style = ex_style | 0x08000000  # WS_EX_NOACTIVATE
                        res = set_window_long_ptr(hwnd, -20, new_style)
                        if res == 0 and ctypes.get_last_error() != 0:
                            logger.warning(f"SetWindowLongPtrW failed with error code: {ctypes.get_last_error()}")
            except Exception as e:
                logger.warning(f"Could not apply WS_EX_NOACTIVATE style securely: {e}")

    def _init_ui(self):
        """初始化精简的弹窗布局"""
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 6px;
                font-family: Arial, sans-serif;
                font-size: 13px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton#ignoreBtn {
                background-color: #95a5a6;
            }
            QPushButton#ignoreBtn:hover {
                background-color: #7f8c8d;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # 标题/建议内容
        original = self.finding.original
        replacement = self.finding.replacement
        action_text = f"Change \"{original}\" to \"{replacement}\"" if original else f"Insert \"{replacement}\""
        
        title_label = QLabel(action_text, self)
        title_label.setStyleSheet("font-weight: bold; color: #2c3e50; border: none;")
        layout.addWidget(title_label)

        # 按钮行
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        accept_btn = QPushButton("Accept", self)
        accept_btn.clicked.connect(self._handle_accept)
        btn_layout.addWidget(accept_btn)

        ignore_btn = QPushButton("Ignore", self)
        ignore_btn.setObjectName("ignoreBtn")
        ignore_btn.clicked.connect(self._handle_ignore)
        btn_layout.addWidget(ignore_btn)

        layout.addLayout(btn_layout)
        self.adjustSize()

    def show_at(self, x: int, y: int):
        """在屏幕指定坐标（通常靠近文本错误位置）显示弹窗，绝不抢焦"""
        import os
        config_mode = os.environ.get("GCOACH_POPUP_TEST", "A").strip().upper()
        if config_mode in ("H", "I", "J", "K"):
            prefix = config_mode
            print(f"{prefix} show_at entered")
            print(f"{prefix} move completed")
            self.move(x, y)
            print(f"{prefix} show entered")
            self.show()
            print(f"{prefix} show completed")
            return

        print("[Phase8E isolation] show_at entered")
        print("[Phase8E isolation] move entered")
        self.move(x, y)
        print("[Phase8E isolation] move completed")
        print("[Phase8E isolation] show entered")
        self.show()
        print("[Phase8E isolation] show completed")

    def nativeEvent(self, eventType: Any, message: int) -> Tuple[bool, int]:
        """拦截原生 Windows 消息，处理 WM_MOUSEACTIVATE (0x0021) 返回 MA_NOACTIVATE (3)，
        确保弹窗不抢占外部应用焦点，同时不丢弃鼠标点击事件。
        """
        if platform.system() == "Windows":
            try:
                import ctypes
                ptr = 0
                if message:
                    if isinstance(message, int):
                        ptr = message
                    elif hasattr(message, "__int__"):
                        ptr = int(message)
                    else:
                        # Fallback for sip.voidptr or capsule
                        try:
                            ptr = ctypes.pythonapi.PyCapsule_GetPointer(message, None)
                        except Exception:
                            try:
                                ptr = int(ctypes.cast(message, ctypes.c_void_p).value or 0)
                            except Exception:
                                ptr = 0

                if ptr:
                    class MSG(ctypes.Structure):
                        _fields_ = [
                            ("hwnd", ctypes.c_void_p),
                            ("message", ctypes.c_uint32),
                            ("wParam", ctypes.c_void_p),
                            ("lParam", ctypes.c_void_p),
                            ("time", ctypes.c_uint32),
                            ("pt", ctypes.c_long * 2),
                        ]
                    m = ctypes.cast(ptr, ctypes.POINTER(MSG)).contents
                    if m.message == 0x0021:  # WM_MOUSEACTIVATE
                        return True, 3  # MA_NOACTIVATE = 3
            except Exception as e:
                logger.debug(f"Error handling nativeEvent WM_MOUSEACTIVATE: {e}")

        return super().nativeEvent(eventType, message)

    def _handle_accept(self):
        """点击 Accept：触发回调并关闭弹窗"""
        try:
            if self.on_accept:
                self.on_accept(self.finding, self.target)
        except Exception as e:
            logger.error(f"Error handling floating popup accept: {e}", exc_info=True)
        self.close()

    def _handle_ignore(self):
        """点击 Ignore：触发回调并关闭弹窗"""
        try:
            if self.on_ignore:
                self.on_ignore(self.finding)
        except Exception as e:
            logger.error(f"Error handling floating popup ignore: {e}", exc_info=True)
        self.close()
