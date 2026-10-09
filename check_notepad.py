import ctypes
import time

user32 = ctypes.windll.user32

def check_notepad_status():
    hwnd = user32.FindWindowW("Notepad++", None)
    if not hwnd:
        found = []
        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def cb(h, l):
            if user32.IsWindowVisible(h):
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(h, cls, 256)
                if "notepad" in cls.value.lower():
                    found.append(h)
            return True
        user32.EnumWindows(cb, 0)
        if found:
            hwnd = found[0]
            
    if hwnd and user32.IsWindow(hwnd):
        print(f"[Status Check] Notepad++ is running (HWND: {hwnd}, IsWindow: True, IsWindowVisible: {user32.IsWindowVisible(hwnd)})")
        return True
    else:
        print("[Status Check] Notepad++ is NOT running or has crashed.")
        return False

if __name__ == "__main__":
    check_notepad_status()
