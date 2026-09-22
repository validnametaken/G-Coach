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
        super().__init__(parent)
        self.finding = finding
        self.target = target
        self.on_accept = on_accept
        self.on_ignore = on_ignore

        self._init_window_flags()
        self._init_ui()

    def _init_window_flags(self):
        """配置窗口标志以确保悬浮、置顶且绝不抢占目标应用焦点"""
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # 在 Windows 平台上应用 WS_EX_NOACTIVATE (0x08000000) 扩展样式
        if platform.system() == "Windows":
            try:
                import ctypes
                hwnd = int(self.winId())
                ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE = -20
                ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex_style | 0x08000000)  # WS_EX_NOACTIVATE
            except Exception as e:
                logger.debug(f"Could not apply WS_EX_NOACTIVATE style: {e}")

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
        self.move(x, y)
        self.show()

    def nativeEvent(self, eventType: Any, message: int) -> Tuple[bool, int]:
        """拦截原生 Windows 消息，处理 WM_MOUSEACTIVATE (0x0021) 返回 MA_NOACTIVATE (3)，
        确保弹窗不抢占外部应用焦点，同时不丢弃鼠标点击事件。
        """
        if platform.system() == "Windows":
            try:
                import ctypes
                msg = ctypes.pythonapi.PyCapsule_GetPointer(message, None) if message else None
                if msg is not None:
                    # MSG 结构体：HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam, DWORD time, POINT pt
                    class MSG(ctypes.Structure):
                        _fields_ = [
                            ("hwnd", ctypes.c_void_p),
                            ("message", ctypes.c_uint32),
                            ("wParam", ctypes.c_void_p),
                            ("lParam", ctypes.c_void_p),
                            ("time", ctypes.c_uint32),
                            ("pt", ctypes.c_long * 2),
                        ]
                    m = ctypes.cast(msg, ctypes.POINTER(MSG)).contents
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
