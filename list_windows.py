import ctypes

user32 = ctypes.windll.user32
@ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
def cb(h, l):
    if user32.IsWindowVisible(h):
        t = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, t, 256)
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(h, cls, 256)
        print(f"HWND: {h}, Title: {t.value!r}, Class: {cls.value!r}")
    return True
user32.EnumWindows(cb, 0)
