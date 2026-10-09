import ctypes
from core.correction.engine import BackgroundCorrectionEngine
from core.correction.target import CorrectionTarget
from core.analysis import Finding

user32 = ctypes.windll.user32

# 1. 查找 Notepad++ 窗口
hwnd = user32.FindWindowW("Notepad++", None)
if not hwnd:
    hwnd = user32.FindWindowW(None, "new 1.txt - Notepad++")
if not hwnd:
    found = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, l):
        if user32.IsWindowVisible(h):
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h, cls, 256)
            title_buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(h, title_buf, 256)
            if "notepad++" in cls.value.lower() or "notepad++" in title_buf.value.lower():
                found.append(h)
        return True
    user32.EnumWindows(cb, 0)
    if found:
        hwnd = found[0]

print(f"Target Notepad++ HWND: {hwnd}")

if hwnd:
    sci = BackgroundCorrectionEngine._resolve_scintilla_hwnd(hwnd)
    print(f"Resolved Scintilla HWND: {sci}")
    
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
        
        # 测试在文档末尾插入或替换
        finding = Finding(source="live_test", category="spelling", message="Test live correction", original=live_text, replacement=live_text + " [OpenHands verified]", start=0, end=len(live_text))
        
        success = BackgroundCorrectionEngine._apply_scintilla_fallback(target, finding, live_text)
        print(f"Live correction application success: {success}")
        
        # 验证修改后内容
        new_len = user32.SendMessageW(sci, SCI_GETTEXTLENGTH, 0, 0)
        new_buf = ctypes.create_unicode_buffer(new_len + 1)
        user32.SendMessageW(sci, SCI_GETTEXT, new_len + 1, ctypes.byref(new_buf))
        print(f"Text content after correction: {new_buf.value!r}")
