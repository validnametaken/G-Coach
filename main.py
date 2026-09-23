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
    if diag_mode in ("MINIMAL-TOPLEVEL", "MINIMAL-PARENTED", "POPUP-REDUCTION", "POPUP-CONSTRUCTOR"):
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
