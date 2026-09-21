# Phase 8A Diagnostic Tool Usage Note

This document describes how to use the Phase 8A focused control diagnostic tool on Windows.

## Purpose

`tools/inspect_focused_control.py` is a lightweight, diagnostic-only script designed to verify what Windows UI Automation exposes from real applications (such as Notepad, Word, Firefox, Telegram, Discord, etc.) when they have keyboard focus.

It uses the existing Phase 8A `WindowsUIAccessibilityTextSource` implementation without introducing a separate monitoring stack.

## How to Run on Windows

1. Open a Windows Command Prompt or PowerShell in your G-Coach repository root.
2. Run the diagnostic tool with Python:

   ```bash
   python tools/inspect_focused_control.py
   ```

3. Click into different applications (e.g., Notepad, Word, browser text fields) and type or change focus.

## What Information is Displayed

When focused control changes or text updates, the tool prints a clear diagnostic block containing:
- Timestamp
- Application / Process name (`app_name`)
- Process ID (`process_id`)
- Control ID (`control_id`)
- Control Type (`control_type`)
- Control Name / Title (`control_info`)
- Editable Status (`is_editable`)
- Status (`status`) and any Error Messages
- Exposed Metadata (Automation ID, HWND, Class Name)
- The retrieved text content (`text`)

## Cleaning Up

Because this is strictly a diagnostic tool, you can delete `tools/inspect_focused_control.py` and `docs/phase8a_diagnostics.md` at any time once manual inspection is complete.
