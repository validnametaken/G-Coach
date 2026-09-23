# AGENTS.md - Repository Knowledge & Developer Guide for G-Coach

## Project Overview
**G-Coach** is an advanced, offline-capable Windows desktop writing assistant and grammar correction tool built with PyQt6. It features:
- Real-time text monitoring across applications (`core/monitoring/`)
- Unified analysis pipelines integrating Harper and GECToR (`core/analysis/`)
- Non-activating floating correction popups with Grammarly-style interaction (`core/ui/floating_correction.py`)
- Robust Windows UI Automation selection & correction engine (`core/correction/`)
- Modern PyQt6 desktop UI (`ui/`)

## Architecture & Core Modules
- **`core/analysis/`**: Standardized findings (`Finding`), abstract base engine (`BaseAnalysisEngine`), analysis pipeline, Harper runner (`harper.py`), and GECToR engine (`gector.py`).
- **`core/monitoring/`**: Live text monitoring and window focus/caret capture.
- **`core/correction/`**: Correction controllers, targets, and execution engines.
- **`core/ui/`**: Window management, presenters, settings dialogs, prompt dialogs, and floating correction popups.
- **`ui/`**: Apple-style styling (`apple_style.py`), custom titlebars, and PyQt components.

## Dependencies & Requirements
The project dependencies are specified in `requirements.txt`:
```
PyQt6>=6.6.0
pyperclip>=1.9.0
keyboard>=0.13.5
pywin32>=306
httpx>=0.27.0
uiautomation>=2.0.29
```

## Development & Testing Commands
- **Install Dependencies**: `pip install -r requirements.txt`
- **Run Tests**: `pytest` or `python gcoach_test.py`
- **Run Application**: `python main.py`

## Coding & Style Guidelines
- **Language**: Use clean, idiomatic English for all code, docstrings, comments, print statements, and documentation.
- **Minimal Changes**: Keep implementations focused, robust, and minimally invasive.
- **Thread Safety & UI**: Respect thread separation between background monitoring/analysis engines and the PyQt6 main thread.

