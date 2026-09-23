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
        if config_mode == "POPUP-CONSTRUCTOR":
            print("[PopupCtor] 01 before super().__init__")
            super().__init__(parent)
            print("[PopupCtor] 02 after super().__init__")
            self.finding = finding
            self.target = target
            self.on_accept = on_accept
            self.on_ignore = on_ignore
            print("[PopupCtor] 03 before _init_window_flags")
            self._init_window_flags()
            print("[PopupCtor] 04 after _init_window_flags")
            print("[PopupCtor] 05 before _init_ui")
            self._init_ui()
            print("[PopupCtor] 06 after _init_ui")
            return

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

        if config_mode == "Q":
            print("Q constructor entered")
            print("Q super().__init__ completed")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            print("Q flags and attributes configured")
            return

        if config_mode == "Q-PARENT":
            print("Q-PARENT constructor entered")
            print("Q-PARENT super().__init__ completed")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            print("Q-PARENT flags and attributes configured")
            return

        if config_mode == "Q-TOPLEVEL":
            print("Q-TOPLEVEL constructor entered")
            print("Q-TOPLEVEL super().__init__ completed")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            print("Q-TOPLEVEL flags and attributes configured")
            return

        if config_mode == "POPUP-CONSTRUCTOR":
            print(f"{config_mode} constructor entered")
            print(f"{config_mode} super().__init__ completed")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            print(f"{config_mode} flags and attributes configured")
            return

        if config_mode == "Q-STEP1":
            # 只有 FramelessWindowHint
            print("Q-STEP1 constructor entered")
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            print("Q-STEP1 flags configured")
            return

        if config_mode == "Q-STEP2":
            # FramelessWindowHint + WindowStaysOnTopHint
            print("Q-STEP2 constructor entered")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
            )
            print("Q-STEP2 flags configured")
            return

        if config_mode == "Q-STEP3":
            # FramelessWindowHint + WindowStaysOnTopHint + WindowDoesNotAcceptFocus
            print("Q-STEP3 constructor entered")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            print("Q-STEP3 flags configured")
            return

        if config_mode == "Q-STEP4":
            # FramelessWindowHint + WindowStaysOnTopHint + WindowDoesNotAcceptFocus + WA_ShowWithoutActivating
            print("Q-STEP4 constructor entered")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            print("Q-STEP4 flags and attributes configured")
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

        if config_mode == "L":
            print("L constructor entered")
            print("L super().__init__ completed")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            print("L flags and attributes configured")
            return

        if config_mode == "M":
            print("M constructor entered")
            print("M super().__init__ completed")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            print("M before winId")
            hwnd = int(self.winId())
            print(f"M after winId: {hwnd}")
            print("M flags, attributes and winId configured")
            return

        if config_mode == "N":
            print("N constructor entered")
            print("N super().__init__ completed")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            print("N flags and attributes configured")
            return

        if config_mode == "O":
            print("O constructor entered")
            print("O super().__init__ completed")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            print("O before windowHandle")
            window_handle = self.windowHandle()
            print(f"O after windowHandle: {window_handle}")
            print("O flags, attributes and windowHandle configured")
            return

        if config_mode == "P":
            print("P constructor entered")
            print("P super().__init__ completed")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            print("P flags and attributes configured")
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
        if config_mode in ("H", "I", "J", "K", "L", "M", "N", "O"):
            prefix = config_mode
            print(f"{prefix} show_at entered")
            print(f"{prefix} move completed")
            self.move(x, y)
            print(f"{prefix} show entered")
            self.show()
            print(f"{prefix} show completed")
            return

        if config_mode == "P":
            print("P show_at entered")
            print("P move completed")
            self.move(x, y)
            print("P before show")
            self.show()
            print("P after show")
            window_handle = self.windowHandle()
            print(f"P windowHandle after show: {window_handle}")
            return

        if config_mode == "Q":
            print("[Phase8E Q] popup shown")
            print("before move")
            self.move(x, y)
            print("after move")
            print("before show")
            self.show()
            print("show returned")
            print("after show")
            print("before query isVisible")
            vis = self.isVisible()
            print(f"after query isVisible: {vis}")
            print("before query isWindow")
            is_win = self.isWindow()
            print(f"after query isWindow: {is_win}")
            print("before query parent")
            par = self.parent()
            print(f"after query parent: {par}")
            print("before query geometry")
            geom = self.geometry()
            print(f"after query geometry: {geom}")
            print("before query pos")
            p = self.pos()
            print(f"after query pos: {p}")
            print("before query size")
            sz = self.size()
            print(f"after query size: {sz}")
            print("before query windowFlags")
            wf = self.windowFlags()
            print(f"after query windowFlags: {wf}")
            print("[Phase8E Q] waiting for interaction")
            return

        print("[Phase8E isolation] show_at entered")
        print("[Phase8E isolation] move entered")
        self.move(x, y)
        print("[Phase8E isolation] move completed")
        print("[Phase8E isolation] show entered")
        self.show()
        print("[Phase8E isolation] show completed")



    def _handle_accept(self):
        """点击 Accept：触发回调并关闭弹窗"""
        print("[Phase8E Click Diagnostic] FloatingCorrectionPopup._handle_accept() entered")
        try:
            if self.on_accept:
                print("[Phase8E Click Diagnostic] invoking on_accept callback")
                self.on_accept(self.finding, self.target)
                print("[Phase8E Click Diagnostic] on_accept callback completed")
            else:
                print("[Phase8E Click Diagnostic] warning: on_accept is None")
        except Exception as e:
            logger.error(f"Error handling floating popup accept: {e}", exc_info=True)
            print(f"[Phase8E Click Diagnostic] Error in _handle_accept: {e}")
        print("[Phase8E Click Diagnostic] calling self.close()")
        self.close()

    def _handle_ignore(self):
        """点击 Ignore：触发回调并关闭弹窗"""
        print("[Phase8E Click Diagnostic] FloatingCorrectionPopup._handle_ignore() entered")
        try:
            if self.on_ignore:
                print("[Phase8E Click Diagnostic] invoking on_ignore callback")
                self.on_ignore(self.finding)
                print("[Phase8E Click Diagnostic] on_ignore callback completed")
            else:
                print("[Phase8E Click Diagnostic] warning: on_ignore is None")
        except Exception as e:
            logger.error(f"Error handling floating popup ignore: {e}", exc_info=True)
            print(f"[Phase8E Click Diagnostic] Error in _handle_ignore: {e}")
        print("[Phase8E Click Diagnostic] calling self.close()")
        self.close()
