"""
Test script for IAccessible2 / MSAA accessibility text detection on Windows windows/controls.
"""

import sys
import ctypes
from ctypes import wintypes

# Load oleacc for MSAA / IAccessible
oleacc = ctypes.windll.oleacc
user32 = ctypes.windll.user32

# IID for IAccessible
# {618736E0-3C3D-11CF-810C-00AA00389B71}
class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8)
    ]

IID_IAccessible = GUID(0x618736E0, 0x3C3D, 0x11CF, (ctypes.c_ubyte * 8)(0x81, 0x0C, 0x00, 0xAA, 0x00, 0x38, 0x9B, 0x71))

def test_window_accessible(hwnd):
    accessible_obj = ctypes.c_void_p()
    # OBJID_CLIENT = 0xFFFFFFFC
    res = oleacc.AccessibleObjectFromWindow(hwnd, 0xFFFFFFFC, ctypes.byref(IID_IAccessible), ctypes.byref(accessible_obj))
    if res != 0:
        return f"AccessibleObjectFromWindow failed with HRESULT: 0x{res:08X}"
    
    # Query IAccessible methods or get window class/title
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    cls_name = buf.value
    
    user32.GetWindowTextW(hwnd, buf, 256)
    win_title = buf.value
    
    return f"Success! HWND={hwnd}, Class={cls_name}, Title='{win_title}', IAccessible ptr={accessible_obj.value}"

if __name__ == "__main__":
    print("Finding foreground window and testing IAccessible extraction...")
    hwnd = user32.GetForegroundWindow()
    print(test_window_accessible(hwnd))
