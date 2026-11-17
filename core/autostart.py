"""
Auto-start Manager - Windows Registry Method
"""

import sys
import winreg
from pathlib import Path


class AutoStartManager:
    """Manages Windows system startup auto-start."""
    
    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "GCoach"
    
    @staticmethod
    def is_enabled() -> bool:
        """Check whether auto-start is enabled."""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                AutoStartManager.REG_PATH,
                0,
                winreg.KEY_READ
            )
            try:
                winreg.QueryValueEx(key, AutoStartManager.APP_NAME)
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception:
            return False
    
    @staticmethod
    def enable():
        """Enable auto-start."""
        try:
            exe_path = sys.executable
            if not exe_path.lower().endswith('.exe'):
                # Development environment, launch using pythonw
                exe_path = f'pythonw.exe "{Path(__file__).parent.parent / "main.py"}"'
            
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                AutoStartManager.REG_PATH,
                0,
                winreg.KEY_WRITE
            )
            winreg.SetValueEx(
                key,
                AutoStartManager.APP_NAME,
                0,
                winreg.REG_SZ,
                f'"{exe_path}"'
            )
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"[AutoStart] Failed to enable: {e}")
            return False
    
    @staticmethod
    def disable():
        """Disable auto-start."""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                AutoStartManager.REG_PATH,
                0,
                winreg.KEY_WRITE
            )
            try:
                winreg.DeleteValue(key, AutoStartManager.APP_NAME)
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"[AutoStart] Failed to disable: {e}")
            return False
