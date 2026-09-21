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

### B. Direct Text Modification Without Focus (`ValuePattern` vs `TextPattern`)
- **`ValuePattern`**: Can set `.SetValue(new_text)` on many editable controls without requiring focus. However, `SetValue` replaces the entire text content. For targeted corrections (e.g., replacing `was` with `were` inside a 500-word paragraph), replacing the entire text can disrupt the user's cursor position and selection.
- **`TextPatternRange` / Selection Modification**: UIA text ranges support `.Select()` and `.ReplaceText(replacement_text)`. However, `ReplaceText` often requires the control to have focus or support selection manipulation.
- **Investigation Conclusion**: For robust, universal support across diverse apps (Telegram, browsers, Notepad), the primary modification strategy will use `ValuePattern` (for full text replacement when targeting short inputs) or localized range replacement where supported, accompanied by careful caret preservation. If a control fundamentally does not support background modification without focus, G-Coach will document the limitation and avoid unsafe mutations.

---

## 4. Target Reference Strategy (`CorrectionTarget`)

To prevent the dangerous scenario where focus changes and a finding targets the wrong control, G-Coach will encapsulate target provenance into a durable `CorrectionTarget` object associated with every `Finding`.

```python
@dataclass
class CorrectionTarget:
    control_id: str
    process_id: int
    hwnd: int
    automation_id: str
    control_type: str
    app_name: str
    initial_text_hash: str
    uia_element_ref: Optional[Any] = field(default=None, repr=False)
```

### Validation Workflow on "Accept":
1. User clicks Accept on the floating popup.
2. G-Coach inspects the currently focused control via `WindowsUIAccessibilityTextSource`.
3. G-Coach verifies that the current control's `control_id`, `process_id`, and `hwnd` match the `CorrectionTarget`.
4. G-Coach verifies that the target control's current text still contains the expected `original` text at the expected offset/context.
5. If validation succeeds, the correction is applied directly. If validation fails (e.g., user typed elsewhere or switched apps), the correction is safely discarded as stale.

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
Validate CorrectionTarget (Match control_id, hwnd, and text context)
        ↓
Apply Direct Modification (ValuePattern / TextPattern)
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
4. **Step 4**: Implement safe background text modification (`ValuePattern` / UIA text modification).
5. **Step 5**: Wire up Accept/Dismiss actions with rigorous target validation.
