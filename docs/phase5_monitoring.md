# Phase 5: Live Text Monitoring Foundation Architecture & Integration

## Overview
Phase 5 establishes the internal foundation for **live text monitoring on Windows** without introducing user interface components, dialogs, overlays, or cloud services.

## Architecture
```
Windows text control
        │
        ▼
   Text Capture
        │
        ▼
   Change Detection
        │
        ▼
      Debounce (~400 ms default)
        │
        ▼
  Current Text Snapshot
        │
        ▼
 Harper + GECToR (AnalysisPipeline)
        │
        ▼
   Resolution (AnalysisResolver)
        │
        ▼
    Finding[]
        │
        ▼
   Future UI (MonitorState API)
```

## Core Components

1. **Text Capture Abstraction (`core/monitoring/capture.py`)**:
   - `TextSnapshot`: Dataclass capturing text content, generation number, timestamp, application name, control info, and status (`idle`, `ready`, `unsupported`, `error`).
   - `TextSource`: Abstract base class separating platform-specific GUI access from analysis.
   - `MockTextSource`: Fully testable mock text source for cross-platform unit testing.
   - `WindowsUIAccessibilityTextSource`: Windows-native UI Automation text source stub that safely attempts to query the active focus control and gracefully reports `unsupported` on non-Windows platforms or when unavailable.

2. **Change Detection, Debounce, & Stale Result Protection (`core/monitoring/monitor.py`)**:
   - `LiveTextMonitor`: Coordinates background polling/monitoring, debounce timing (default 400ms), generation/version tracking, asynchronous worker execution, and result publication.
   - **Stale Result Protection**: Every text modification increments a global generation counter (`_current_generation`). When background analysis completes, its target generation is strictly compared against the current generation. If a newer generation has been created in the meantime, the stale analysis result is discarded. This ensures that the monitor never returns findings for outdated text snapshots.

3. **Result API (`MonitorState`)**:
   - Exposes thread-safe snapshot states (`generation`, `text`, `findings`, `status`, `timestamp`, `app_name`, `control_info`, `error_message`) via `get_state()`.

## Privacy & Security
- Operations are strictly local and offline.
- Captured text is processed in memory and never logged or transmitted over networks.

## Scope Compliance
- No UI, no window overlays, no suggestion popups, no system tray UI, no automatic rewriting, no cloud services, and no changes to existing AI rewriting.
