import ctypes
from core.correction.engine import BackgroundCorrectionEngine
from core.correction.target import CorrectionTarget
from core.analysis import Finding

user32 = ctypes.windll.user32

# 1. 查找 Notepad++ 窗口
hwnd = 0
@ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
def cb(h, l):
    global hwnd
    if user32.IsWindowVisible(h):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(h, cls, 256)
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, title, 256)
        if "notepad++" in cls.value.lower() or "notepad++" in title.value.lower() or cls.value == "Notepad++":
            hwnd = h
            return False
    return True
user32.EnumWindows(cb, 0)

print(f"Target Notepad++ HWND: {hwnd} (IsWindow: {user32.IsWindow(hwnd) if hwnd else False})")

if hwnd:
    sci = BackgroundCorrectionEngine._resolve_scintilla_hwnd(hwnd)
    print(f"Resolved Scintilla HWND: {sci} (IsWindow: {user32.IsWindow(sci) if sci else False})")
    
    if sci:
        SCI_GETTEXTLENGTH = 2183
        SCI_GETTEXT = 2182
        length = user32.SendMessageW(sci, SCI_GETTEXTLENGTH, 0, 0)
        print(f"Document length: {length}")
        
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.SendMessageW(sci, SCI_GETTEXT, length + 1, ctypes.byref(buf))
        live_text = buf.value
        print(f"Current text content: {live_text!r}")
        
        target = CorrectionTarget(hwnd=hwnd, app_name="notepad++.exe", original_text=live_text)
        
        # 安全测试：在末尾增加测试字符串
        replacement_text = live_text + " [live test passed]"
        finding = Finding(source="live_test", category="spelling", message="Live test correction", original=live_text, replacement=replacement_text, start=0, end=len(live_text))
        
        success = BackgroundCorrectionEngine._apply_scintilla_fallback(target, finding, live_text)
        print(f"Live correction application success: {success}")
        
        # 验证修改后内容
        new_len = user32.SendMessageW(sci, SCI_GETTEXTLENGTH, 0, 0)
        new_buf = ctypes.create_unicode_buffer(new_len + 1)
        user32.SendMessageW(sci, SCI_GETTEXT, new_len + 1, ctypes.byref(new_buf))
        print(f"Text content after correction: {new_buf.value!r}")
else:
    print("Notepad++ window not found. Please open Notepad++.")
