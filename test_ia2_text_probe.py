"""
Extended probe test to query IAccessibleText interface from the accessible object.
"""
import ctypes
from ctypes import wintypes

oleacc = ctypes.windll.oleacc
user32 = ctypes.windll.user32

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8)
    ]

IID_IAccessible = GUID(0x618736E0, 0x3C3D, 0x11CF, (ctypes.c_ubyte * 8)(0x81, 0x0C, 0x00, 0xAA, 0x00, 0x38, 0x9B, 0x71))
# IID_IAccessibleText: {24FD2F6F-3C90-4fed-B58D-029D671B5F37}
IID_IAccessibleText = GUID(0x24FD2F6F, 0x3C90, 0x4fed, (ctypes.c_ubyte * 8)(0xB5, 0x8D, 0x02, 0x9D, 0x67, 0x1B, 0x5F, 0x37))

def probe_text_interface(hwnd):
    acc = ctypes.c_void_p()
    res = oleacc.AccessibleObjectFromWindow(hwnd, 0xFFFFFFFC, ctypes.byref(IID_IAccessible), ctypes.byref(acc))
    if res != 0 or not acc.value:
        return f"AccessibleObjectFromWindow failed: 0x{res:08X}"
    
    # Try QueryInterface for IAccessibleText
    text_interface = ctypes.c_void_p()
    # IAccessible vtable QueryInterface is at index 0
    # In ctypes, we can call QueryInterface via COM vtable or use IUnknown interface casting.
    # Let's inspect vtable pointer
    vtable = ctypes.cast(acc.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    # QueryInterface is index 0 of IUnknown (which IAccessible inherits from)
    # prototype: HRESULT QueryInterface(REFIID riid, void **ppvObject)
    QI_func_type = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
    qi_func = QI_func_type(vtable[0])
    
    text_interface = ctypes.c_void_p()
    try:
        hr = qi_func(acc.value, ctypes.byref(IID_IAccessibleText), ctypes.byref(text_interface))
    except Exception as e:
        hr = -1

    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    cls_name = buf.value
    user32.GetWindowTextW(hwnd, buf, 256)
    win_title = buf.value

    if hr == 0 and text_interface.value:
        return f"[{cls_name}] '{win_title}': Supports IAccessibleText! (ptr={text_interface.value})"
    else:
        return f"[{cls_name}] '{win_title}': Standard MSAA / No IAccessibleText (HRESULT=0x{hr & 0xFFFFFFFF:08X})"

if __name__ == "__main__":
    hwnd = user32.GetForegroundWindow()
    print(probe_text_interface(hwnd))
