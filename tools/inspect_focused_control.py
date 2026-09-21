#!/usr/bin/env python3
"""
Phase 8A Diagnostic Tool: Inspect Currently Focused Windows Control

使用现有的 Phase 8A WindowsUIAccessibilityTextSource 持续检查当前具有键盘焦点的 Windows 控件，
并在控件或焦点发生变化时打印详细的诊断信息块（进程名、进程 ID、control ID、控件类型、标题、
是否可编辑、抓取的文本以及元数据）。
"""

import time
import sys
import platform
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.monitoring import WindowsUIAccessibilityTextSource


def main():
    if platform.system() != "Windows":
        print("[Warning] This diagnostic tool is designed for Windows platforms with UI Automation support.")
        print("[Info] Running on non-Windows platform; WindowsUIAccessibilityTextSource will return unsupported status.")

    source = WindowsUIAccessibilityTextSource()
    print("=" * 70)
    print(" G-Coach Phase 8A: Focused Control Diagnostic Inspector")
    print(" Press Ctrl+C to exit.")
    print("=" * 70)

    last_control_id = None
    last_text = None

    try:
        while True:
            snapshot = source.get_current_text()
            current_control_id = snapshot.control_id

            # 检测焦点控件或应用是否发生变化
            if current_control_id != last_control_id:
                print("\n" + "=" * 70)
                print(" [FOCUS / CONTROL CHANGED]")
                print("=" * 70)
                last_control_id = current_control_id
                last_text = None  # 强制刷新文本打印

            # 如果文本发生变化或首次进入
            if snapshot.text != last_text:
                last_text = snapshot.text
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Active Snapshot Update:")
                print(f"  - App Name     : {snapshot.app_name}")
                print(f"  - Process ID   : {snapshot.process_id}")
                print(f"  - Control Type : {snapshot.control_type}")
                print(f"  - Control Info : {snapshot.control_info}")
                print(f"  - Control ID   : {snapshot.control_id}")
                print(f"  - Is Editable  : {snapshot.is_editable}")
                print(f"  - Status       : {snapshot.status}")
                if snapshot.error_message:
                    print(f"  - Error Msg    : {snapshot.error_message}")
                print(f"  - Metadata     : {snapshot.metadata}")
                print("-" * 70)
                print(f" [Retrieved Text Content]:")
                print(f" {repr(snapshot.text)}")
                print("=" * 70)

            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n[Info] Diagnostic inspector stopped by user.")


if __name__ == "__main__":
    main()
