import ctypes

user32 = ctypes.windll.user32

@ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
def cb(h, l):
    if user32.IsWindowVisible(h):
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, title, 256)
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(h, cls, 256)
        print(f"HWND: {h}, Class: {cls.value!r}, Title: {title.value!r}")
    return True

user32.EnumWindows(cb, 0)
