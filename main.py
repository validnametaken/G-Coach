"""
G-Coach - Main Entry Point
An advanced offline-capable Windows desktop writing assistant and grammar correction tool.
"""

import sys
import ctypes
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

# Windows taskbar icon setting
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("GCoach")
except Exception:
    pass

from ui.main_window import MainWindow
from ui.apple_style import apply_apple_style
from core.config_manager import ConfigManager
from core.api_client import APIClient
from core.prompt_manager import PromptManager
from core.resources import resource_path


_single_instance_mutex = None


def _ensure_single_instance() -> bool:
    """Ensure only one app instance owns the global hotkey."""
    global _single_instance_mutex
    ERROR_ALREADY_EXISTS = 183
    _single_instance_mutex = ctypes.windll.kernel32.CreateMutexW(
        None,
        False,
        "Global\\G_Coach_Single_Instance",
    )
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        print("[Main] Another instance is already running. Exiting current instance.")
        return False
    return True



def main():
    # 检查是否有独立的最小化 Qt 顶层/父子组件诊断测试环境变量（必须在单实例检查与任何 G-Coach 业务逻辑之前运行）
    import os
    diag_mode = os.environ.get("GCOACH_POPUP_TEST", "").strip().upper()
    if diag_mode in ("MINIMAL-TOPLEVEL", "MINIMAL-PARENTED", "POPUP-REDUCTION", "POPUP-CONSTRUCTOR", "POPUP-SHOW-ISOLATION", "POPUP-NATIVE-EVENT-BYPASS"):
        app = QApplication(sys.argv)
        from PyQt6.QtWidgets import QWidget
        if diag_mode == "MINIMAL-TOPLEVEL":
            print("MINIMAL-TOPLEVEL diagnostic starting...")
            print("MINIMAL: before construction")
            widget = QWidget()
            print("MINIMAL: after construction (constructed)")
            widget.setWindowTitle("G-Coach Top-Level Diagnostic")
            widget.resize(200, 80)
            print(f"MINIMAL: parent = {widget.parent()}")
            print(f"MINIMAL: isWindow = {widget.isWindow()}")
            print("MINIMAL: before show")
            widget.show()
            print("MINIMAL: show returned")
            print(f"MINIMAL: isVisible = {widget.isVisible()}")
            print(f"MINIMAL: isHidden = {widget.isHidden()}")
            print(f"MINIMAL: isWindow = {widget.isWindow()}")
            print(f"MINIMAL: geometry = {widget.geometry()}")
            # 保持强引用防止垃圾回收
            global _minimal_test_ref
            _minimal_test_ref = widget
        elif diag_mode == "MINIMAL-PARENTED":
            print("MINIMAL-PARENTED diagnostic starting...")
            print("MINIMAL-PARENTED: before parent construction")
            parent_widget = QWidget()
            print("MINIMAL-PARENTED: after parent construction")
            parent_widget.setWindowTitle("G-Coach Parent Diagnostic")
            parent_widget.resize(400, 300)
            print("MINIMAL-PARENTED: before parent show")
            parent_widget.show()
            print("MINIMAL-PARENTED: parent show returned")

            print("MINIMAL-PARENTED: before child construction")
            child_widget = QWidget(parent_widget)
            print("MINIMAL-PARENTED: after child construction")
            child_widget.setWindowTitle("G-Coach Child Diagnostic")
            child_widget.resize(200, 80)
            print("MINIMAL-PARENTED: before child show")
            child_widget.show()
            print("MINIMAL-PARENTED: child show returned")

            print(f"parent.parent() = {parent_widget.parent()}")
            print(f"parent.isWindow() = {parent_widget.isWindow()}")
            print(f"parent.isVisible() = {parent_widget.isVisible()}")
            print(f"child.parent() = {child_widget.parent()}")
            print(f"child.isWindow() = {child_widget.isWindow()}")
            print(f"child.isVisible() = {child_widget.isVisible()}")

            global _minimal_parented_ref
            _minimal_parented_ref = (parent_widget, child_widget)
        elif diag_mode == "POPUP-REDUCTION":
            print("POPUP-REDUCTION diagnostic starting...")
            from PyQt6.QtCore import Qt
            from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton
            from core.analysis import Finding
            from core.ui.floating_correction import FloatingCorrectionPopup

            # Stage 1 — QWidget base (unparented top-level)
            print("POPUP-REDUCTION Stage 1: before construction")
            w1 = QWidget(None)
            print("POPUP-REDUCTION Stage 1: constructed")
            w1.resize(200, 80)
            print("POPUP-REDUCTION Stage 1: before show")
            w1.show()
            print("POPUP-REDUCTION Stage 1: show returned")
            print(f"POPUP-REDUCTION Stage 1: isVisible={w1.isVisible()}, isWindow={w1.isWindow()}")

            # Stage 2 — basic layout
            print("POPUP-REDUCTION Stage 2: before construction & layout")
            w2 = QWidget(None)
            layout2 = QVBoxLayout(w2)
            layout2.setContentsMargins(10, 10, 10, 10)
            print("POPUP-REDUCTION Stage 2: constructed & layout added")
            w2.resize(200, 80)
            print("POPUP-REDUCTION Stage 2: before show")
            w2.show()
            print("POPUP-REDUCTION Stage 2: show returned")

            # Stage 3 — label/text widget
            print("POPUP-REDUCTION Stage 3: before construction & label")
            w3 = QWidget(None)
            layout3 = QVBoxLayout(w3)
            layout3.setContentsMargins(10, 10, 10, 10)
            lbl3 = QLabel("Change \"was\" to \"were\"", w3)
            layout3.addWidget(lbl3)
            print("POPUP-REDUCTION Stage 3: constructed, layout & label added")
            w3.resize(200, 80)
            print("POPUP-REDUCTION Stage 3: before show")
            w3.show()
            print("POPUP-REDUCTION Stage 3: show returned")

            # Stage 4 — buttons
            print("POPUP-REDUCTION Stage 4: before construction & buttons")
            w4 = QWidget(None)
            layout4 = QVBoxLayout(w4)
            layout4.setContentsMargins(10, 10, 10, 10)
            lbl4 = QLabel("Change \"was\" to \"were\"", w4)
            layout4.addWidget(lbl4)
            btn_layout4 = QHBoxLayout()
            b1 = QPushButton("Accept", w4)
            b2 = QPushButton("Ignore", w4)
            btn_layout4.addWidget(b1)
            btn_layout4.addWidget(b2)
            layout4.addLayout(btn_layout4)
            print("POPUP-REDUCTION Stage 4: constructed, layout, label & buttons added")
            w4.resize(200, 80)
            print("POPUP-REDUCTION Stage 4: before show")
            w4.show()
            print("POPUP-REDUCTION Stage 4: show returned")

            # Stage 5 — popup flags (FramelessWindowHint, WindowStaysOnTopHint, WindowDoesNotAcceptFocus, WA_ShowWithoutActivating)
            print("POPUP-REDUCTION Stage 5: before construction & flags")
            w5 = QWidget(None)
            w5.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
            w5.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            layout5 = QVBoxLayout(w5)
            layout5.setContentsMargins(10, 10, 10, 10)
            lbl5 = QLabel("Change \"was\" to \"were\"", w5)
            layout5.addWidget(lbl5)
            print("POPUP-REDUCTION Stage 5: constructed, flags & layout added")
            w5.resize(200, 80)
            print("POPUP-REDUCTION Stage 5: before show")
            w5.show()
            print("POPUP-REDUCTION Stage 5: show returned")

            # Stage 6 — actual FloatingCorrectionPopup initialization (parent=None, no winId(), no Tool, no ctypes, no nativeEvent)
            print("POPUP-REDUCTION Stage 6: before real FloatingCorrectionPopup(parent=None)")
            finding = Finding(
                source="Harper",
                category="grammar",
                message="Agreement",
                original="was",
                replacement="were",
                start=0,
                end=3,
            )
            real_popup = FloatingCorrectionPopup(
                finding=finding,
                target=None,
                on_accept=lambda f, t: None,
                on_ignore=lambda f: None,
                parent=None,
            )
            print("POPUP-REDUCTION Stage 6: real FloatingCorrectionPopup constructed")
            print("POPUP-REDUCTION Stage 6: before show_at")
            real_popup.show_at(200, 200)
            print("POPUP-REDUCTION Stage 6: show_at returned")

            global _popup_reduction_refs
            _popup_reduction_refs = (w1, w2, w3, w4, w5, real_popup)
        elif diag_mode == "POPUP-CONSTRUCTOR":
            print("POPUP-CONSTRUCTOR diagnostic starting...")
            from core.analysis import Finding
            from core.ui.floating_correction import FloatingCorrectionPopup

            print("[PopupCtor Diagnostic] before constructing FloatingCorrectionPopup(parent=None)")
            finding = Finding(
                source="Harper",
                category="grammar",
                message="Agreement",
                original="was",
                replacement="were",
                start=0,
                end=3,
            )
            ctor_popup = FloatingCorrectionPopup(
                finding=finding,
                target=None,
                on_accept=lambda f, t: None,
                on_ignore=lambda f: None,
                parent=None,
            )
            print("[PopupCtor Diagnostic] after constructing FloatingCorrectionPopup(parent=None)")
            print("[PopupCtor Diagnostic] before show_at")
            ctor_popup.show_at(200, 200)
            print("[PopupCtor Diagnostic] after show_at")

            global _popup_ctor_ref
            _popup_ctor_ref = ctor_popup
        elif diag_mode == "POPUP-SHOW-ISOLATION":
            print("POPUP-SHOW-ISOLATION diagnostic starting...")
            from PyQt6.QtCore import Qt
            from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton
            from core.analysis import Finding
            from core.ui.floating_correction import FloatingCorrectionPopup

            finding = Finding(
                source="Harper",
                category="grammar",
                message="Agreement",
                original="was",
                replacement="were",
                start=0,
                end=3,
            )

            # Variant A — Current production behavior (with nativeEvent override)
            print("[ShowIsolation A] before construction")
            popup_a = FloatingCorrectionPopup(
                finding=finding,
                target=None,
                on_accept=lambda f, t: None,
                on_ignore=lambda f: None,
                parent=None,
            )
            print("[ShowIsolation A] constructed")
            print("[ShowIsolation A] before move")
            popup_a.move(100, 100)
            print("[ShowIsolation A] moved")
            print("[ShowIsolation A] before show")
            popup_a.show()
            print("[ShowIsolation A] show returned")

            # Variant B — Temporarily bypass the class's nativeEvent override by monkeypatching
            print("[ShowIsolation B] before construction")
            popup_b = FloatingCorrectionPopup(
                finding=finding,
                target=None,
                on_accept=lambda f, t: None,
                on_ignore=lambda f: None,
                parent=None,
            )
            # Monkeypatch nativeEvent to call super().nativeEvent directly
            popup_b.nativeEvent = lambda eventType, msg: super(FloatingCorrectionPopup, popup_b).nativeEvent(eventType, msg)
            print("[ShowIsolation B] constructed & nativeEvent bypassed")
            print("[ShowIsolation B] before move")
            popup_b.move(300, 100)
            print("[ShowIsolation B] moved")
            print("[ShowIsolation B] before show")
            popup_b.show()
            print("[ShowIsolation B] show returned")

            # Variant C — Bare QWidget subclass with same non-native Qt flags, layout, and content (Stage 5 equivalent)
            print("[ShowIsolation C] before construction")
            class SafePopupWidget(QWidget):
                def __init__(self, finding, parent=None):
                    super().__init__(parent)
                    self.setWindowFlags(
                        Qt.WindowType.FramelessWindowHint
                        | Qt.WindowType.WindowStaysOnTopHint
                        | Qt.WindowType.WindowDoesNotAcceptFocus
                    )
                    self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
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
                    """)
                    layout = QVBoxLayout(self)
                    layout.setContentsMargins(10, 10, 10, 10)
                    layout.setSpacing(6)

                    original = finding.original
                    replacement = finding.replacement
                    action_text = f"Change \"{original}\" to \"{replacement}\"" if original else f"Insert \"{replacement}\""
                    title_label = QLabel(action_text, self)
                    title_label.setStyleSheet("font-weight: bold; color: #2c3e50; border: none;")
                    layout.addWidget(title_label)

                    btn_layout = QHBoxLayout()
                    btn_layout.setSpacing(6)
                    accept_btn = QPushButton("Accept", self)
                    btn_layout.addWidget(accept_btn)
                    ignore_btn = QPushButton("Ignore", self)
                    btn_layout.addWidget(ignore_btn)
                    layout.addLayout(btn_layout)
                    self.adjustSize()

            widget_c = SafePopupWidget(finding, parent=None)
            print("[ShowIsolation C] constructed")
            print("[ShowIsolation C] before move")
            widget_c.move(500, 100)
            print("[ShowIsolation C] moved")
            print("[ShowIsolation C] before show")
            widget_c.show()
            print("[ShowIsolation C] show returned")

            global _popup_isolation_refs
            _popup_isolation_refs = (popup_a, popup_b, widget_c)
        elif diag_mode == "POPUP-NATIVE-EVENT-BYPASS":
            print("POPUP-NATIVE-EVENT-BYPASS diagnostic starting...")
            from core.analysis import Finding
            from core.ui.floating_correction import FloatingCorrectionPopup

            finding = Finding(
                source="Harper",
                category="grammar",
                message="Agreement",
                original="was",
                replacement="were",
                start=0,
                end=3,
            )

            try:
                # Control A — Current behavior (normal nativeEvent)
                print("[NativeEventBypass Control A] before construction")
                popup_a = FloatingCorrectionPopup(
                    finding=finding,
                    target=None,
                    on_accept=lambda f, t: None,
                    on_ignore=lambda f: None,
                    parent=None,
                )
                print("[NativeEventBypass Control A] constructed")
                print("[NativeEventBypass Control A] before move")
                popup_a.move(100, 100)
                print("[NativeEventBypass Control A] moved")
                print("[NativeEventBypass Control A] before show")
                popup_a.show()
                print("[NativeEventBypass Control A] show returned")
            except Exception as e:
                print(f"[NativeEventBypass Control A] Error: {e}")

            original_native_event = None
            try:
                # Control B — Bypass nativeEvent BEFORE construction
                print("[NativeEventBypass Control B] before monkeypatching nativeEvent")
                original_native_event = FloatingCorrectionPopup.nativeEvent
                FloatingCorrectionPopup.nativeEvent = lambda self, eventType, msg: (False, 0)
                print("[NativeEventBypass Control B] nativeEvent replaced")

                print("[NativeEventBypass Control B] before construction")
                popup_b = FloatingCorrectionPopup(
                    finding=finding,
                    target=None,
                    on_accept=lambda f, t: None,
                    on_ignore=lambda f: None,
                    parent=None,
                )
                print("[NativeEventBypass Control B] constructed")
                print("[NativeEventBypass Control B] before move")
                popup_b.move(300, 100)
                print("[NativeEventBypass Control B] moved")
                print("[NativeEventBypass Control B] before show")
                popup_b.show()
                print("[NativeEventBypass Control B] show returned")
            except Exception as e:
                print(f"[NativeEventBypass Control B] Error: {e}")
            finally:
                if original_native_event is not None:
                    FloatingCorrectionPopup.nativeEvent = original_native_event

            global _popup_bypass_refs
            _popup_bypass_refs = (popup_a, popup_b)

        sys.exit(app.exec())

    if not _ensure_single_instance():
        return

    # 确保数据目录存在
    data_dir = Path.home() / ".ai_prompt_optimizer"
    data_dir.mkdir(parents=True, exist_ok=True)

    # 启用高DPI
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("AI Prompt Optimizer")
    app.setOrganizationName("AIPromptOptimizer")
    icon_path = resource_path("icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # 应用苹果风格设计系统
    apply_apple_style(app)

    # 初始化核心模块
    config_manager = ConfigManager(data_dir)
    api_client = APIClient(config_manager)
    prompt_manager = PromptManager(data_dir)

    # 创建主窗口
    window = MainWindow(config_manager, api_client, prompt_manager)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
