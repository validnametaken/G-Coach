# Phase 6: G-Coach Desktop User Interface Architecture & Integration

## Overview
Phase 6 implements the first **G-Coach desktop user interface** using PyQt6. The UI serves as a read-only presentation and inspection layer for the existing monitoring and analysis pipeline.

## UI Framework Selection
- **Chosen Framework**: PyQt6 (`pip install PyQt6`)
- **Why**: PyQt6 is a robust, production-grade desktop GUI framework supporting native Windows styling, rich widgets (`QSplitter`, `QListWidget`, `QTextEdit`), reliable background threading/timers (`QTimer`), and thread-safe UI updates. It avoids Electron, local web servers, and heavy browser runtimes.

## Architecture
```
LiveTextMonitor (Background Thread)
        │
        ▼ (MonitorState API)
  GCoachWindow (QTimer Poll @ 100ms)
        │
        ▼ (UIPresenter)
   UI Display (Status, App Info, Text Snapshot, Findings, Details & Conflicts)
```

## Key Components

1. **Presenter (`core/ui/presenter.py`)**:
   - `UIPresenter`: Pure formatting and translation utility converting `MonitorState` and `Finding` instances into UI-friendly summaries, status strings, application info, and conflict detection groups. Completely decoupled from PyQt widgets for easy unit testing.

2. **Desktop Window (`core/ui/window.py`)**:
   - `GCoachWindow`: Main application window containing:
     - **Header**: Application title, live monitoring status (`Idle`, `Waiting`, `Analyzing`, `Ready`, `Unsupported`, `Error`), application/control info, and Start/Stop monitoring buttons.
     - **Captured Text Snapshot**: Read-only display of the latest captured text snapshot.
     - **Findings List**: Displays all findings with categories, sources, and ⚠️ [CONFLICT] indicators when multiple engines suggest different replacements for the same text span.
     - **Details & Conflicts Panel**: Inspects full attributes of a selected finding (original, replacement, category, message, confidence, range) along with multi-engine conflict alternatives.

## Privacy & Security
- Read-only observation layer.
- Never modifies the source application's text.
- No telemetry, no cloud transmission, no logging of captured text.

## Scope Compliance
- No automatic correction.
- No keyboard simulation or clipboard replacement.
- No automatic rewriting.
- Uses existing `LiveTextMonitor` and `AnalysisResolver`.
