# Phase 8E Design Document: Floating Correction Interaction

## 1. Current Problem

G-Coach currently features a centralized PyQt6 main window where findings and suggestions are listed, and users must click "Accept Correction" inside the G-Coach window.

### The Focus-Stealing Problem
1. User types in an external target application (e.g., Telegram, Firefox, Notepad).
2. `LiveTextMonitor` and the analysis pipeline detect a grammar finding (e.g., `was` → `were`).
3. User clicks **Accept Correction** inside the G-Coach main window.
4. **Focus shifts** from the target application (Telegram) to the G-Coach application.
5. `LiveTextMonitor` polls focus and detects that the active control is now the G-Coach window (or no longer Telegram).
6. The correction controller attempts to apply the finding against the newly focused control, detects that the control/text context has changed, and correctly rejects it as stale.

While this stale-finding protection prevents corrupting wrong text, it creates a poor user experience. Users are forced to leave their target application, click into G-Coach, and lose their writing flow.

---

## 2. Desired UX (Grammarly-Style Floating Interaction)

G-Coach should operate without stealing focus:
- The target application (Telegram, Firefox, Word) remains the active, focused window.
- A small, non-activating floating correction popup appears near the detected text error.
- The popup displays the suggestion with an **Accept** button and a **Dismiss (×)** button.
- Clicking **Accept** modifies the text directly in the original target control via Windows UI Automation **without activating the target window or stealing focus**.

---

## 3. Windows UI Automation Investigation Findings

### A. Finding Text Coordinates & Bounding Rectangles (`TextPattern` / `TextPatternRange`)
- **Capability**: UIA `TextPattern` supports `DocumentRange` and navigating ranges by units (character, word, line). Furthermore, `TextPatternRange` supports `GetBoundingRectangles()`, which returns an array of bounding boxes `[left, top, width, height]` in screen coordinates for the text range.
- **Support Matrix**:
  - **Standard Rich Edit / Notepad / Word / Modern Win32 / UWP Text Controls**: Full `TextPattern` and `GetBoundingRectangles()` support.
  - **Browsers (Firefox / Chromium / ChatGPT Web via ProseMirror)**: Partial/Mixed support. While Chromium-based apps expose robust UIA text patterns, Firefox and some Electron apps may expose accessible text through `LegacyIAccessiblePattern` or `ValuePattern` rather than full line/character `TextPatternRange` coordinates.
  - **Fallback Strategy**: If `TextPattern` bounding rectangles are unavailable or return empty for a given control (e.g., custom web editors or plain `ValuePattern` inputs), the floating popup can fall back to positioning relative to the target window rectangle (`NativeWindowHandle` bounding box) or near the caret/cursor location.

### B. Localized Text Modification While Preserving Target Focus (`ValuePattern` vs `TextPattern`)
- **`ValuePattern`**: Can set `.SetValue(new_text)` on many editable controls without requiring focus. However, `SetValue` replaces the entire text content. For targeted corrections (e.g., replacing `was` with `were` inside a 500-word paragraph), replacing the entire text can disrupt the user's cursor position and selection.
- **`TextPatternRange` / Selection Modification**: UIA text ranges support `.Select()` and `.ReplaceText(replacement_text)`. However, `ReplaceText` often requires the control to have focus or support selection manipulation.
- **Current implementation**: G-Coach deliberately avoids `ValuePattern.SetValue` and `LegacyIAccessible.SetValue`, because those replace the entire value and can disturb unrelated text or the caret. It uses a verified localized `TextPattern` range and keyboard input only while the original target remains focused. Controls that cannot provide the required identity, readable range, exact selection, or post-write verification fail closed; there is no full-document write fallback.

---

## 4. Target Reference Strategy (`CorrectionTarget`)

To prevent the dangerous scenario where focus changes and a finding targets the wrong control, G-Coach encapsulates target provenance into a `CorrectionTarget` associated with every popup. The target contains only plain Python identity and text values; it never stores an apartment-bound UIA object.

```python
@dataclass
class CorrectionTarget:
    control_id: str
    process_id: int
    hwnd: int
    automation_id: str
    control_name: str
    control_type: str
    app_name: str
    initial_text_hash: str
```

### Validation Workflow on "Accept":
1. User clicks Accept on the non-activating floating popup.
2. G-Coach queues the operation onto the `LiveTextMonitor` UIA-owning thread and reacquires the currently focused control there.
3. G-Coach verifies the process, native handle (when available), AutomationId or control name, and control type against the `CorrectionTarget`.
4. G-Coach verifies the complete live document and exact finding range; it then confirms UIA selected the exact range and rechecks focus and text immediately before input.
5. G-Coach applies the localized replacement and verifies the complete resulting document. If any check fails (for example, focus changed, the editor does not expose the required patterns, or the document changed), the correction is refused.

---

## 5. Popup Strategy (Non-Activating Qt Window)

To ensure the floating popup never steals focus from the target application:
- **Qt Window Flags**:
  - `Qt.Tool` (prevents showing in taskbar as a primary window)
  - `Qt.FramelessWindowHint` (no standard OS title bar)
  - `Qt.WindowStaysOnTopHint` (remains visible above other windows)
- **Windows API Integration (`WS_EX_NOACTIVATE` / `WS_EX_TOOLWINDOW`)**:
  - Override native window creation or apply Win32 extended window styles (`GWL_EXSTYLE`) to include `WS_EX_NOACTIVATE` (0x08000000).
  - This ensures that clicking buttons inside the floating popup generates mouse events without sending WM_ACTIVATE or stealing keyboard focus from Telegram/Firefox.

---

## 6. Interaction Lifecycle & Data Flow

```
Windows UI Automation
        ↓
TextSnapshot (with Control Identity)
        ↓
AnalysisPipeline (Harper + GECToR)
        ↓
AnalysisResolver (Findings)
        ↓
CorrectionTarget (Bound to Finding)
        ↓
FloatingCorrectionPopup (Positioned via Bounding Rectangles, Non-activating)
        ↓
User clicks Accept on Popup
        ↓
Reacquire and validate CorrectionTarget on the UIA owner thread
        ↓
Select exact TextPattern range and apply verified keyboard replacement
        ↓
Re-poll Text Snapshot & Re-analyze
        ↓
Dismiss Popup
```

---

## 7. Safety & Stale Protection Guarantees
- **Generation Tracking**: Existing `_current_generation` ensures stale background analysis results are discarded.
- **Target Validation**: `CorrectionTarget` ID checks ensure corrections are never applied to a different application or control.
- **Context Validation**: Text hash / substring checks ensure corrections are not applied if the user has already modified that sentence.

---

## 8. Recommended Phase 8E Implementation Steps
1. **Step 1**: Implement `CorrectionTarget` data structure and bind it during resolution.
2. **Step 2**: Create the non-activating floating popup widget (`FloatingCorrectionPopup`) with `Qt.Tool`, `Qt.WindowStaysOnTopHint`, and `WS_EX_NOACTIVATE`.
3. **Step 3**: Implement bounding-rectangle coordinate resolution using UIA `TextPatternRange`.
4. **Step 4**: Implement safe localized modification while the original target retains focus, with exact selection and post-write verification.
5. **Step 5**: Wire up Accept/Dismiss actions with rigorous target validation.

## 9. Popup Positioning Implementation Status

The desktop window now attempts to position each popup beside the exact finding:

1. It reacquires the currently focused control on the monitor's UIA-owning thread and verifies that the complete text snapshot and finding range are still unchanged.
2. It builds the exact range using strict offset validation, then reads `GetBoundingRectangles()` without selecting or modifying text.
3. It anchors to the final visible rectangle for multi-line findings and selects the screen containing that rectangle.
4. If range geometry is unavailable, it falls back to the target control's window rectangle, then to the G-Coach window.

The positioning and fallback logic is covered by unit tests. Real-editor validation across Notepad, Word, browsers, and Electron applications remains a manual Windows verification task; unsupported controls are expected to use the fallback path.

## 10. UI Automation COM Thread Ownership

The installed `uiautomation` package documents that a `Control` or `Pattern` created on one thread must not be used from another thread. The application therefore keeps all UI Automation operations on the `LiveTextMonitor` thread:

1. The monitor thread initializes UI Automation when it starts and releases its COM client when it exits.
2. Focus capture, exact-range geometry lookup, correction selection/input, and post-write verification execute on that same thread.
3. `TextSnapshot`, `MonitorState`, and `CorrectionTarget` carry only ordinary Python values and stable control identity. They never retain a UIA `Control`, `Pattern`, or range object.
4. The Qt thread requests geometry and correction through `run_on_monitor_thread()` and receives only a rectangle, boolean, or monitor-state snapshot.

This avoids using apartment-bound COM wrappers across the monitoring and Qt threads. The change is covered by unit tests for owner-thread dispatch, source initialization/shutdown, target identity revalidation, and the absence of UIA references in snapshots. Real-editor validation is still required on Windows.
