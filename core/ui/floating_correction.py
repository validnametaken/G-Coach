"""
G-Coach Floating Correction Popup (PyQt6) - Phase 8E
悬浮纠正弹窗：在不抢占外部应用程序焦点（使用 WS_EX_NOACTIVATE）的前提下，
在屏幕指定位置渲染建议并提供 [Accept] / [Ignore] 交互。
"""

import logging
import platform
from dataclasses import replace as dataclass_replace
from typing import Optional, Callable, Any, Tuple, Union, List
from core.dictionary import is_dictionary_candidate

logger = logging.getLogger(__name__)

try:
    from PyQt6.QtCore import (
        QAbstractNativeEventFilter,
        QCoreApplication,
        Qt,
        QPoint,
    )
    from PyQt6.QtWidgets import (
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QComboBox,
    )
    from PyQt6.QtGui import QMouseEvent
    PYQT_AVAILABLE = True
except (ImportError, OSError) as e:
    logger.warning(f"PyQt6 not available for FloatingCorrectionPopup: {e}")
    PYQT_AVAILABLE = False
    QWidget = object  # type: ignore


def _apply_windows_no_activate(widget: Any) -> bool:
    """Make a floating widget topmost without activating it on Windows.

    Do not rely on Qt's WindowStaysOnTopHint for these windows: Qt may apply
    that hint through a separate z-order operation while showing the widget.
    Apply both WS_EX_NOACTIVATE and HWND_TOPMOST through one native operation
    carrying SWP_NOACTIVATE, before and after the Qt show path.
    """
    if platform.system() != "Windows":
        return True

    try:
        import ctypes
        from ctypes import wintypes

        hwnd = wintypes.HWND(int(widget.winId()))
        user32 = ctypes.WinDLL("user32", use_last_error=True)

        if ctypes.sizeof(ctypes.c_void_p) == 8:
            get_window_long = user32.GetWindowLongPtrW
            set_window_long = user32.SetWindowLongPtrW
            long_type = ctypes.c_ssize_t
        else:
            get_window_long = user32.GetWindowLongW
            set_window_long = user32.SetWindowLongW
            long_type = wintypes.LONG

        get_window_long.argtypes = (wintypes.HWND, ctypes.c_int)
        get_window_long.restype = long_type
        set_window_long.argtypes = (wintypes.HWND, ctypes.c_int, long_type)
        set_window_long.restype = long_type

        gwl_exstyle = -20
        ws_ex_noactivate = 0x08000000
        ctypes.set_last_error(0)
        current_style = get_window_long(hwnd, gwl_exstyle)
        if current_style == 0 and ctypes.get_last_error():
            raise ctypes.WinError(ctypes.get_last_error())

        required_style = current_style | ws_ex_noactivate
        if required_style != current_style:
            ctypes.set_last_error(0)
            previous_style = set_window_long(hwnd, gwl_exstyle, required_style)
            if previous_style == 0 and ctypes.get_last_error():
                raise ctypes.WinError(ctypes.get_last_error())

        user32.SetWindowPos.argtypes = (
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        )
        user32.SetWindowPos.restype = wintypes.BOOL
        swp_nosize = 0x0001
        swp_nomove = 0x0002
        swp_noactivate = 0x0010
        swp_framechanged = 0x0020
        flags = (
            swp_nosize
            | swp_nomove
            | swp_noactivate
            | swp_framechanged
        )
        hwnd_topmost = wintypes.HWND(-1)  # HWND_TOPMOST
        if not user32.SetWindowPos(hwnd, hwnd_topmost, 0, 0, 0, 0, flags):
            raise ctypes.WinError(ctypes.get_last_error())

        return True
    except Exception:
        logger.exception("Unable to enforce WS_EX_NOACTIVATE for G-Coach popup window.")
        return False


if PYQT_AVAILABLE:
    class _NonActivatingPopupMouseFilter(QAbstractNativeEventFilter):
        """Keep Windows from discarding the click that opens an inactive popup.

        Qt's non-activating top-level windows can receive WM_MOUSEACTIVATE
        before the actual mouse-button message. MA_NOACTIVATEANDEAT preserves
        the no-focus behavior but discards that click. Return MA_NOACTIVATE
        for this dropdown only: it still does not activate, but the click is
        delivered to the list view.
        """

        WM_MOUSEACTIVATE = 0x0021
        MA_NOACTIVATE = 3

        def __init__(self):
            super().__init__()
            self._popup_hwnd = 0
            self._popup_owner_hwnd = 0

        def set_popup_hwnd(self, hwnd: int, owner_hwnd: int = 0) -> None:
            self._popup_hwnd = int(hwnd or 0)
            self._popup_owner_hwnd = int(owner_hwnd or 0)

        def _is_popup_related(self, hwnd: int) -> bool:
            if not hwnd:
                return False
            relevant_hwnds = {
                value
                for value in (self._popup_hwnd, self._popup_owner_hwnd)
                if value
            }
            if hwnd in relevant_hwnds:
                return True

            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
                user32.GetAncestor.restype = wintypes.HWND
                # WM_MOUSEACTIVATE may identify a child HWND. Resolve both its
                # top-level window and root owner before deciding it is unrelated.
                for ancestor_kind in (2, 3):  # GA_ROOT, GA_ROOTOWNER
                    ancestor = int(
                        user32.GetAncestor(wintypes.HWND(hwnd), ancestor_kind) or 0
                    )
                    if ancestor in relevant_hwnds:
                        return True
            except Exception as exc:
                logger.debug("Could not resolve popup ancestry for HWND %s: %s", hwnd, exc)
            return False

        def nativeEventFilter(self, event_type, message):
            if not self._popup_hwnd or bytes(event_type) != b"windows_generic_MSG":
                return False, 0

            try:
                import ctypes
                from ctypes import wintypes

                message_address = int(message)
                native_message = ctypes.cast(
                    message_address,
                    ctypes.POINTER(wintypes.MSG),
                ).contents
                if int(native_message.message) != self.WM_MOUSEACTIVATE:
                    return False, 0

                # WM_MOUSEACTIVATE may be delivered to the popup itself or to
                # a child which identifies the popup or its root owner as the
                # top-level parent. Qt's combo container is an owned window,
                # so Windows can report the floating correction window here.
                message_hwnd = int(native_message.hWnd or 0)
                parent_hwnd = int(native_message.wParam or 0)
                if not (
                    self._is_popup_related(message_hwnd)
                    or self._is_popup_related(parent_hwnd)
                ):
                    return False, 0

                return True, self.MA_NOACTIVATE
            except Exception as exc:
                logger.debug("Could not inspect popup mouse-activation message: %s", exc)
                return False, 0


    class NonActivatingComboBox(QComboBox):
        """Combo box whose native dropdown does not activate the G-Coach process.

        The floating correction window deliberately does not accept focus so the
        editor underneath it (for example, Notepad) remains the foreground app.
        QComboBox creates a separate native popup window for its choices; give
        that window the same non-activating behavior or opening the list can
        disturb focus tracking in the target editor.
        """

        def __init__(self, parent=None):
            super().__init__(parent)
            self._mouse_activation_filter = None
            self._mouse_activation_filter_app = None
            if platform.system() == "Windows":
                app = QCoreApplication.instance()
                if app is not None:
                    self._mouse_activation_filter = _NonActivatingPopupMouseFilter()
                    self._mouse_activation_filter_app = app
                    app.installNativeEventFilter(self._mouse_activation_filter)
                    self.destroyed.connect(self._remove_mouse_activation_filter)
            self._configure_popup_window()

        def _remove_mouse_activation_filter(self, *_args):
            app = self._mouse_activation_filter_app
            event_filter = self._mouse_activation_filter
            if app is not None and event_filter is not None:
                app.removeNativeEventFilter(event_filter)
            self._mouse_activation_filter = None
            self._mouse_activation_filter_app = None

        def _track_popup_window(self, popup_window):
            popup_hwnd = int(popup_window.winId())
            owner_hwnd = 0
            if platform.system() == "Windows" and self._mouse_activation_filter is not None:
                try:
                    import ctypes
                    from ctypes import wintypes

                    user32 = ctypes.WinDLL("user32", use_last_error=True)
                    user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
                    user32.GetAncestor.restype = wintypes.HWND
                    # GA_ROOTOWNER: walk the popup's parent and owner chain.
                    owner_hwnd = int(
                        user32.GetAncestor(wintypes.HWND(popup_hwnd), 3) or 0
                    )
                    if owner_hwnd == popup_hwnd:
                        owner_hwnd = 0
                except Exception as exc:
                    logger.debug("Could not resolve the dropdown's root owner: %s", exc)

            if self._mouse_activation_filter is not None:
                self._mouse_activation_filter.set_popup_hwnd(popup_hwnd, owner_hwnd)

        def _configure_popup_window(self):
            popup_window = self.view().window()
            flags = popup_window.windowFlags() | Qt.WindowType.WindowDoesNotAcceptFocus
            if platform.system() == "Windows":
                flags &= ~Qt.WindowType.WindowStaysOnTopHint
            if flags != popup_window.windowFlags():
                popup_window.setWindowFlags(flags)
            popup_window.setAttribute(
                Qt.WidgetAttribute.WA_ShowWithoutActivating, True
            )
            self._native_popup_ready = _apply_windows_no_activate(popup_window)
            self._track_popup_window(popup_window)

        def showPopup(self):
            self._configure_popup_window()
            if not self._native_popup_ready:
                logger.error("Alternative dropdown suppressed because non-activation could not be guaranteed.")
                return
            super().showPopup()
            popup_window = self.view().window()
            self._track_popup_window(popup_window)
            if not _apply_windows_no_activate(popup_window):
                self.hidePopup()


class FloatingCorrectionPopup(QWidget if PYQT_AVAILABLE else object):
    """浮动纠正弹窗（Floating Correction Popup）

    具备如下核心特性：
    1. 非抢焦特性 (Non-activating)：使用 Qt.Tool, Qt.FramelessWindowHint, Qt.WindowStaysOnTopHint 并在 Windows 上应用 WS_EX_NOACTIVATE。
    2. 精准定位：显示在距错误文本最近的屏幕坐标位置。
    3. 简洁交互：提供 [Accept] 与 [Ignore / Dismiss (×)] 按钮。
    """

    def __init__(
        self,
        findings: List[Any],
        current_index: int,
        target: Any,
        on_accept: Callable[[Any, Any], None],
        on_ignore: Callable[[Any], None],
        on_navigate: Optional[Callable[[int], None]] = None,
        on_add_to_dict: Optional[Callable[[Any], None]] = None,
        parent: Optional[QWidget] = None,
        on_accept_all: Optional[Callable[[List[Any], Any], None]] = None,
    ):
        if not PYQT_AVAILABLE:
            raise RuntimeError("PyQt6 is required for FloatingCorrectionPopup.")
        
        # 兼容旧的单个 finding 传参或列表传参
        if isinstance(findings, list):
            self.findings = findings
        else:
            self.findings = [findings] if findings else []
        
        self.current_index = max(0, min(current_index, len(self.findings) - 1)) if self.findings else 0
        self.target = target
        self.on_accept = on_accept
        self.on_ignore = on_ignore
        self.on_navigate = on_navigate
        self.on_add_to_dict = on_add_to_dict
        self.on_accept_all = on_accept_all
        self._displayed_finding_id = None

        import os
        config_mode = os.environ.get("GCOACH_POPUP_TEST", "A").strip().upper()
        if config_mode == "POPUP-CONSTRUCTOR":
            super().__init__(parent)
            self._init_window_flags()
            self._init_ui()
            return

        if config_mode == "H":
            super().__init__(parent)
            self._init_window_flags()
            self._init_ui()
            return

        super().__init__(parent)
        self._init_window_flags()
        self._init_ui()

    @property
    def finding(self) -> Any:
        """返回当前选中的 finding"""
        if self.findings and 0 <= self.current_index < len(self.findings):
            return self.findings[self.current_index]
        return None

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

        flags = tool_flag | Qt.WindowType.FramelessWindowHint
        if platform.system() != "Windows":
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if focus_flag:
            flags |= focus_flag

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)



    def _init_ui(self):
        """初始化精简的弹窗布局，包含导航控件 (‹ 1 / 2 ›)"""
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
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #ecf0f1;
            }
            QPushButton#ignoreBtn {
                background-color: #95a5a6;
            }
            QPushButton#ignoreBtn:hover {
                background-color: #7f8c8d;
            }
            QPushButton.navBtn {
                background-color: #ecf0f1;
                color: #2c3e50;
                font-weight: bold;
                padding: 2px 6px;
                border-radius: 3px;
            }
            QPushButton.navBtn:hover:enabled {
                background-color: #bdc3c7;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # 顶部导航与计数行 (‹ 1 / 2 ›)
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(4)

        self.prev_btn = QPushButton("‹", self)
        self.prev_btn.setProperty("class", "navBtn")
        self.prev_btn.setFixedSize(24, 24)
        self.prev_btn.clicked.connect(self._handle_prev)
        top_layout.addWidget(self.prev_btn)

        total = len(self.findings)
        display_idx = self.current_index + 1 if total > 0 else 0
        self.counter_label = QLabel(f"{display_idx} / {total}", self)
        self.counter_label.setStyleSheet("font-weight: bold; color: #7f8c8d; border: none; font-size: 11px;")
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(self.counter_label)

        self.next_btn = QPushButton("›", self)
        self.next_btn.setProperty("class", "navBtn")
        self.next_btn.setFixedSize(24, 24)
        self.next_btn.clicked.connect(self._handle_next)
        top_layout.addWidget(self.next_btn)

        top_layout.addStretch()
        layout.addLayout(top_layout)

        # 建议内容标签
        self.title_label = QLabel(self)
        self.title_label.setStyleSheet("font-weight: bold; color: #2c3e50; border: none;")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        # Harper can return several valid replacements for one finding. Keep
        # its first suggestion as the default while allowing the user to pick
        # another option without changing the shared Finding object.
        alternatives_layout = QHBoxLayout()
        alternatives_layout.setContentsMargins(0, 0, 0, 0)
        alternatives_layout.setSpacing(6)
        self.alternatives_label = QLabel("Alternative:", self)
        self.alternatives_label.setStyleSheet(
            "color: #7f8c8d; border: none; font-size: 11px;"
        )
        alternatives_layout.addWidget(self.alternatives_label)
        self.replacement_combo = NonActivatingComboBox(self)
        self.replacement_combo.setObjectName("replacementOptions")
        self.replacement_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.replacement_combo.setMinimumWidth(180)
        self.replacement_combo.currentIndexChanged.connect(
            self._handle_replacement_changed
        )
        alternatives_layout.addWidget(self.replacement_combo, 1)
        layout.addLayout(alternatives_layout)
        self.alternatives_label.setVisible(False)
        self.replacement_combo.setVisible(False)

        # 按钮行 (Accept / Add to dictionary / Ignore)。对有拼写建议的词，
        # 用户可以选择接受建议，也可以将原词加入个人词典。
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.accept_btn = QPushButton("Accept", self)
        self.accept_btn.clicked.connect(self._handle_accept)
        btn_layout.addWidget(self.accept_btn)

        self.add_to_dict_btn = QPushButton("Add to dictionary", self)
        self.add_to_dict_btn.clicked.connect(self._handle_add_to_dict)
        self.add_to_dict_btn.setVisible(False)
        btn_layout.addWidget(self.add_to_dict_btn)

        self.ignore_btn = QPushButton("Ignore", self)
        self.ignore_btn.setObjectName("ignoreBtn")
        self.ignore_btn.clicked.connect(self._handle_ignore)
        btn_layout.addWidget(self.ignore_btn)

        layout.addLayout(btn_layout)

        self.accept_all_btn = QPushButton("Accept all safe suggestions", self)
        self.accept_all_btn.setToolTip(
            "Apply independent, non-overlapping suggestions in one pass, then recheck the document once."
        )
        self.accept_all_btn.clicked.connect(self._handle_accept_all)
        self.accept_all_btn.setVisible(len(self.findings) > 1 and self.on_accept_all is not None)
        layout.addWidget(self.accept_all_btn)

        self._update_content()
        self.adjustSize()

    @staticmethod
    def _get_replacement_options(finding: Any) -> List[str]:
        """Return distinct Harper replacements, keeping its best choice first."""
        if not finding or str(getattr(finding, "source", "")).lower() != "harper":
            return []

        metadata = getattr(finding, "metadata", None)
        raw_options = metadata.get("replacements", []) if isinstance(metadata, dict) else []
        if not isinstance(raw_options, (list, tuple)):
            raw_options = []

        options: List[str] = []
        for candidate in [getattr(finding, "replacement", ""), *raw_options]:
            if not isinstance(candidate, str) or not candidate.strip():
                continue
            if candidate not in options:
                options.append(candidate)
        return options

    def _selected_replacement(self, finding: Any) -> str:
        """Return the visible user choice, falling back to Harper's best choice."""
        if finding is self.finding and self.replacement_combo.count() > 0:
            selected = self.replacement_combo.currentData()
            if isinstance(selected, str):
                return selected
        return getattr(finding, "replacement", "") if finding else ""

    def _finding_with_selected_replacement(self, finding: Any) -> Any:
        """Copy the current finding only when the user chose another replacement."""
        selected = self._selected_replacement(finding)
        if finding is not None and selected != finding.replacement:
            return dataclass_replace(finding, replacement=selected)
        return finding

    @staticmethod
    def _sync_accepted_finding(original: Any, applied: Any) -> None:
        """Keep the popup's shared finding in sync after a copied choice succeeds."""
        if original is not None and applied is not original and applied.status == "accepted":
            original.replacement = applied.replacement
            original.status = applied.status

    def _handle_replacement_changed(self, *_args):
        finding = self.finding
        if finding:
            replacement = self._selected_replacement(finding)
            original = finding.original
            if replacement and replacement.strip():
                action_text = (
                    f'Change "{original}" to "{replacement}"'
                    if original
                    else f'Insert "{replacement}"'
                )
            else:
                action_text = f'Unknown word: "{original}"' if original else "Unknown word"
            self.title_label.setText(action_text)

    def _update_content(self):
        """更新当前展示的 finding 文本及导航按钮状态"""
        f = self.finding
        if f:
            original = f.original
            options = self._get_replacement_options(f)
            previous_selection = (
                self.replacement_combo.currentData()
                if self._displayed_finding_id == getattr(f, "id", None)
                else None
            )

            blocked = self.replacement_combo.blockSignals(True)
            self.replacement_combo.clear()
            for option in options:
                self.replacement_combo.addItem(option, option)
            if options:
                if previous_selection in options:
                    selected_index = options.index(previous_selection)
                else:
                    selected_index = 0
                self.replacement_combo.setCurrentIndex(selected_index)
            self.replacement_combo.blockSignals(blocked)
            show_alternatives = len(options) > 1
            self.alternatives_label.setVisible(show_alternatives)
            self.replacement_combo.setVisible(show_alternatives)
            self._displayed_finding_id = getattr(f, "id", None)

            replacement = self._selected_replacement(f)
            if replacement and replacement.strip():
                action_text = f"Change \"{original}\" to \"{replacement}\"" if original else f"Insert \"{replacement}\""
            else:
                action_text = f"Unknown word: \"{original}\"" if original else "Unknown word"
            
            self.title_label.setText(action_text)
            
            has_replacement = bool(options or (replacement and replacement.strip()))
            is_cand = is_dictionary_candidate(f)

            # A spelling finding can be both a valid correction and a possible
            # personal-dictionary word. Keep both actions available when it has
            # a suggested replacement (e.g. "doiing" -> "doing").
            self.accept_btn.setVisible(has_replacement)
            self.accept_btn.setEnabled(has_replacement)
            self.add_to_dict_btn.setVisible(is_cand)
            self.add_to_dict_btn.setEnabled(is_cand)
            self.ignore_btn.setEnabled(True)
        else:
            self.replacement_combo.clear()
            self.replacement_combo.setVisible(False)
            self.alternatives_label.setVisible(False)
            self._displayed_finding_id = None
            self.title_label.setText("No suggestions")
            self.add_to_dict_btn.setVisible(False)
            self.accept_btn.setVisible(True)
            self.accept_btn.setEnabled(False)
            self.ignore_btn.setEnabled(False)

        total = len(self.findings)
        display_idx = self.current_index + 1 if total > 0 else 0
        self.counter_label.setText(f"{display_idx} / {total}")

        if total <= 1:
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
        else:
            self.prev_btn.setEnabled(self.current_index > 0)
            self.next_btn.setEnabled(self.current_index < total - 1)

    def set_findings(self, findings: List[Any], current_index: int = 0):
        """更新当前 findings 列表与索引并刷新显示"""
        self.findings = findings or []
        self.current_index = max(0, min(current_index, len(self.findings) - 1)) if self.findings else 0
        if hasattr(self, "accept_all_btn"):
            self.accept_all_btn.setVisible(
                len(self.findings) > 1 and self.on_accept_all is not None
            )
        self._update_content()
        self.adjustSize()

    def _handle_prev(self):
        """点击上一个发现 (‹)"""
        print(f"[Phase8E Navigation] _handle_prev clicked. Current index before: {self.current_index}")
        if self.current_index > 0:
            self.current_index -= 1
            self._update_content()
            print(f"[Phase8E Navigation] Moved to index: {self.current_index}")
            if self.on_navigate:
                self.on_navigate(self.current_index)

    def _handle_next(self):
        """点击下一个发现 (›)"""
        print(f"[Phase8E Navigation] _handle_next clicked. Current index before: {self.current_index}, total: {len(self.findings)}")
        if self.findings and self.current_index < len(self.findings) - 1:
            self.current_index += 1
            self._update_content()
            print(f"[Phase8E Navigation] Moved to index: {self.current_index}")
            if self.on_navigate:
                self.on_navigate(self.current_index)

    def show_at(self, x: int, y: int):
        """在屏幕指定坐标（通常靠近文本错误位置）显示弹窗，绝不抢焦"""
        self.move(x, y)
        # Force native HWND creation while hidden, then apply WS_EX_NOACTIVATE
        # before QWidget.show() can ask Windows to display the popup.
        if not _apply_windows_no_activate(self):
            logger.error("Floating correction popup suppressed: native no-activation could not be enforced.")
            return
        self.show()
        # Re-apply after Qt's show path in case the platform plugin adjusted styles.
        # The pre-show call is the important guard against transient activation.
        if not _apply_windows_no_activate(self):
            self.hide()
            logger.error("Floating correction popup hidden: native no-activation style was not retained.")
            return



    def _handle_accept(self):
        """点击 Accept：触发回调并关闭弹窗"""
        print("[Phase8E Click Diagnostic] FloatingCorrectionPopup._handle_accept() entered")
        original_finding = self.finding
        applied_finding = self._finding_with_selected_replacement(original_finding)
        try:
            if self.on_accept:
                print("[Phase8E Click Diagnostic] invoking on_accept callback")
                self.on_accept(applied_finding, self.target)
                print("[Phase8E Click Diagnostic] on_accept callback completed")
            else:
                print("[Phase8E Click Diagnostic] warning: on_accept is None")
        except Exception as e:
            logger.error(f"Error handling floating popup accept: {e}", exc_info=True)
            print(f"[Phase8E Click Diagnostic] Error in _handle_accept: {e}")
        finally:
            self._sync_accepted_finding(original_finding, applied_finding)
        print("[Phase8E Click Diagnostic] calling self.close()")
        self.close()

    def _handle_accept_all(self):
        """Apply all independent suggestions through one verified batch operation."""
        original_findings = list(self.findings)
        findings = list(original_findings)
        try:
            if self.on_accept_all:
                if 0 <= self.current_index < len(findings):
                    findings[self.current_index] = self._finding_with_selected_replacement(
                        findings[self.current_index]
                    )
                self.on_accept_all(findings, self.target)
        except Exception as exc:
            logger.error("Error handling floating popup accept-all: %s", exc, exc_info=True)
        finally:
            for original, applied in zip(original_findings, findings):
                self._sync_accepted_finding(original, applied)
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

    def _handle_add_to_dict(self):
        """点击 Add to dictionary：触发回调并关闭弹窗"""
        print("[Phase8F.1 Click Diagnostic] FloatingCorrectionPopup._handle_add_to_dict() entered")
        try:
            if self.on_add_to_dict:
                self.on_add_to_dict(self.finding)
        except Exception as e:
            logger.error(f"Error handling floating popup add to dict: {e}", exc_info=True)
        self.close()


def calculate_popup_position(
    anchor_x: int,
    anchor_y: int,
    anchor_width: int,
    anchor_height: int,
    popup_width: int,
    popup_height: int,
    screen_left: int,
    screen_top: int,
    screen_width: int,
    screen_height: int,
    gap: int = 20,
) -> Tuple[int, int]:
    """Place the popup beside an anchor rectangle while keeping it on-screen."""
    screen_right = screen_left + screen_width
    screen_bottom = screen_top + screen_height

    # Prefer the right side of the text/control, then the left side.
    popup_x = anchor_x + anchor_width + gap
    if popup_x + popup_width > screen_right:
        left_candidate = anchor_x - popup_width - gap
        if left_candidate >= screen_left:
            popup_x = left_candidate
        else:
            popup_x = max(screen_left, min(popup_x, screen_right - popup_width))

    # Keep the popup below the text where possible; otherwise put it above.
    below = anchor_y + anchor_height + gap
    above = anchor_y - popup_height - gap
    if below + popup_height <= screen_bottom:
        popup_y = below
    elif above >= screen_top:
        popup_y = above
    else:
        popup_y = max(screen_top, min(below, screen_bottom - popup_height))

    return (popup_x, popup_y)
