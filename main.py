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
    if diag_mode in ("MINIMAL-TOPLEVEL", "MINIMAL-PARENTED"):
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
