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
