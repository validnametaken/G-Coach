import ctypes
from core.correction.engine import BackgroundCorrectionEngine
from core.correction.target import CorrectionTarget
from core.analysis import Finding

user32 = ctypes.windll.user32

# 1. 查找 Notepad++ 窗口
hwnd = user32.FindWindowW("Notepad++", None)
print(f"FindWindowW('Notepad++'): {hwnd}")

if not hwnd:
    # 遍历查找
    found = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, l):
        if user32.IsWindowVisible(h):
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h, cls, 256)
            if cls.value == "Notepad++":
                found.append(h)
        return True
    user32.EnumWindows(cb, 0)
    if found:
        hwnd = found[0]

print(f"Target Notepad++ HWND: {hwnd}")

if hwnd:
    # 2. 解析 Scintilla HWND
    sci = BackgroundCorrectionEngine._resolve_scintilla_hwnd(hwnd)
    print(f"Resolved Scintilla HWND: {sci}")
    
    if sci:
        SCI_GETTEXTLENGTH = 2183
        SCI_GETTEXT = 2182
        length = user32.SendMessageW(sci, SCI_GETTEXTLENGTH, 0, 0)
        print(f"Document length: {length}")
        
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.SendMessageW(sci, SCI_GETTEXT, length + 1, ctypes.byref(buf))
        print(f"Document text: {buf.value!r}")
