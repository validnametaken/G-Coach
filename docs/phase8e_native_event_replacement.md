# Phase 8E Design Document: Native Event Replacement & Non-Activating Popup Architecture

## 1. Current Implementation & Purpose of `nativeEvent`

### What `nativeEvent` Currently Does
In `core/ui/floating_correction.py`, `FloatingCorrectionPopup` overrides `nativeEvent(self, eventType: Any, message: int)` to intercept raw Windows native messages (`MSG` struct via ctypes). Specifically, it checks for `WM_MOUSEACTIVATE` (`0x0021`) and returns `(True, 3)` where `3` corresponds to `MA_NOACTIVATE`.

### Why Message Handling Was Introduced
When a standard top-level PyQt6 window (even with `Qt.WindowStaysOnTopHint` and `Qt.WindowDoesNotAcceptFocus`) receives a mouse click on Windows, the Windows Window Manager (`USER32`) by default sends `WM_MOUSEACTIVATE` to determine whether the window should become active (taking focus). By intercepting `WM_MOUSEACTIVATE` and returning `MA_NOACTIVATE`, the original intent was to prevent Windows from activating the floating popup window when clicked, ensuring the external target application (e.g., Telegram, Firefox, Notepad) retains keyboard focus.

---

### Why It Causes a Native Crash
Through exhaustive incremental reduction diagnostics (Stages 1 through 6) and A/B testing (Commit `ffc22c5`), we established that:
- Constructing `FloatingCorrectionPopup(parent=None)` with standard safe Qt flags and attributes succeeds.
- Moving and calling `.show()` on an unparented top-level PyQt6 window when `nativeEvent` is present and performs raw ctypes pointer casting (`ctypes.cast(ptr, ctypes.POINTER(MSG))`) during native window activation/show events causes an unhandled access violation / native crash on Windows.
- When `nativeEvent` is monkeypatched to bypass this ctypes message parsing before construction, `.show()` completes successfully (`isVisible: True`) without crashing.

---

## 2. Evidence Summary (A/B Diagnostic Results)

- **Control A (Production `nativeEvent`)**:
  - Reaches constructor, configures flags, but terminates natively during or immediately upon entering window activation/creation events in `show()`.
- **Control B (Monkeypatched `nativeEvent` returning `(False, 0)`)**:
  - Successfully completes construction, moves, calls `.show()`, returns cleanly, and reports `isVisible: True`.

**Conclusion**: The ctypes pointer extraction and WM_MOUSEACTIVATE handling inside `nativeEvent` is unsafe during native window show/activation on Windows Python/PyQt6 and is directly responsible for the crash.

---

## 3. Qt-Only Alternatives & Evaluation

To eliminate the crashing `nativeEvent` override while satisfying the non-activating UX requirement, we evaluate the following Qt-native mechanisms:

### A. Window Flags (`Qt.WindowStaysOnTopHint`, `Qt.FramelessWindowHint`, `Qt.Tool`)
- **Evaluation**: Necessary for floating above other applications without taskbar presence, but insufficient on their own on Windows to prevent focus stealing upon mouse clicks.

### B. `Qt.WindowDoesNotAcceptFocus` Window Flag
- **Evaluation**: Instructs Qt and the window manager that the window does not accept input focus. However, on Windows, top-level frameless windows can still receive activation unless supported by OS-level attributes.

### C. `WA_ShowWithoutActivating` Attribute
- **Evaluation**: Calling `self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)` before showing ensures that Qt invokes native show APIs without bringing the window to the foreground or stealing focus. This is safe and fully supported across Qt6 platforms.

### D. Qt Event Filters / Mouse Event Handling
- **Evaluation**: Qt handles mouse events cleanly via normal event propagation (`mousePressEvent`). Because `WA_ShowWithoutActivating` and `Qt.WindowDoesNotAcceptFocus` prevent activation at show time, clicking buttons inside the popup (`Accept`, `Ignore`) dispatches click events to the buttons without triggering a window activation (`WM_ACTIVATE`) sequence that steals focus from the underlying target application.

---

## 4. Recommended Approach

We recommend removing the raw ctypes `nativeEvent()` override entirely and relying exclusively on Qt-native window flags and attributes:

1. **Remove `nativeEvent`**: Eliminate the ctypes `MSG` parsing and `WM_MOUSEACTIVATE` interception.
2. **Leverage Qt-Native Attributes**:
   - `Qt.WindowType.Tool`
   - `Qt.WindowType.FramelessWindowHint`
   - `Qt.WindowType.WindowStaysOnTopHint`
   - `Qt.WindowType.WindowDoesNotAcceptFocus`
   - `self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)`
3. **Behavioral Mapping**:
   - **What was required**: Prevent focus stealing and keep target app active.
   - **What `nativeEvent` was providing**: Low-level `MA_NOACTIVATE` via `USER32` message hooking.
   - **What Qt achieves natively**: `WA_ShowWithoutActivating` + `WindowDoesNotAcceptFocus` achieves non-activating show and interaction without unsafe raw pointer casting in `nativeEvent`.

---

## 5. Verification Plan (Native Windows Test Matrix)

Once implemented, the following verification plan must be executed on Windows:

1. **Popup Construction**: Verify `FloatingCorrectionPopup(parent=None)` instantiates without errors.
2. **Popup Visibility**: Verify `.show_at(x, y)` successfully displays the popup near the target text.
3. **Target Focus Preservation**: Verify the external application (e.g. Notepad / Telegram) remains active and focused while the popup is visible.
4. **Popup Clickability**: Verify clicking **Accept** or **Ignore** on the popup responds correctly.
5. **Accept Action**: Verify clicking **Accept** successfully applies the correction to the original text via background UI Automation without activating G-Coach.
6. **Ignore Action**: Verify clicking **Ignore** dismisses the popup cleanly.
7. **Continuous Typing**: Verify the user can continue typing in the target application uninterrupted.
8. **Application Switching**: Verify switching between external applications functions normally.
9. **Stale Correction Rejection**: Verify corrections are correctly rejected if the user focuses another control or edits the text before accepting.
