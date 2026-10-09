import ctypes
import platform
from core.correction.engine import BackgroundCorrectionEngine
from core.correction.target import CorrectionTarget
from core.analysis import Finding

def run_live_correction_test():
    if platform.system() != "Windows":
        print("Not Windows; skipping live test.")
        return

    user32 = ctypes.windll.user32
    
    # 1. 直接通过 BackgroundCorrectionEngine 的标准逻辑查找或使用当前顶层窗口
    found_hwnds = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_windows_callback(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buf, 256)
            length = user32.GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
            # 只要包含 notepad 或者是 Scintilla 类
            if "notepad" in title.lower() or class_buf.value == "Notepad++" or class_buf.value == "Scintilla":
                found_hwnds.append(hwnd)
        return True

    user32.EnumWindows(enum_windows_callback, 0)
    
    if not found_hwnds:
        print("No running Notepad++ top-level window found. Please make sure Notepad++ is open.")
        return

    npp_hwnd = found_hwnds[0]
    print(f"Found Notepad++ HWND: {npp_hwnd}")
    
    # 解析 Scintilla 子窗口 HWND
    scintilla_hwnd = BackgroundCorrectionEngine._resolve_scintilla_hwnd(npp_hwnd)
    print(f"Resolved Scintilla HWND: {scintilla_hwnd}")
    
    if not scintilla_hwnd:
        print("Failed to resolve Scintilla HWND.")
        return

    # 读取当前文本
    SCI_GETTEXTLENGTH = 2183
    SCI_GETTEXT = 2182
    length = user32.SendMessageW(scintilla_hwnd, SCI_GETTEXTLENGTH, 0, 0)
    print(f"Current Scintilla document length: {length}")
    
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.SendMessageW(scintilla_hwnd, SCI_GETTEXT, length + 1, ctypes.byref(buf))
    live_text = buf.value
    print(f"Current text content: {live_text!r}")
    
    # 构造 CorrectionTarget
    target = CorrectionTarget(hwnd=npp_hwnd, app_name="notepad++.exe", original_text=live_text)
    
    print(f"Live text currently is: {live_text!r}")
    
    # 移除全文本替换自动测试，只保留安全检测与提示
    print("Live Scintilla fallback engine is ready.")
    if "teeh" in live_text:
        idx = live_text.index("teeh")
        finding = Finding(source="live_test", category="spelling", message="Fix typo", original="teeh", replacement="the", start=idx, end=idx+4)
        success = BackgroundCorrectionEngine._apply_scintilla_fallback(target, finding, live_text)
        print(f"Correction applied successfully: {success}")
    else:
        print("Tip: Type 'teeh' in Notepad++ and run this script again to test live typo correction!")


if __name__ == "__main__":
    run_live_correction_test()
