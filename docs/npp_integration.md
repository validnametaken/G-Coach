# G-Coach Notepad++ Correction Integration (Phase 8G.6)

## Architecture & Integration Overview
Phase 8G.6 connects the native Notepad++ plugin bridge (`plugins/npp_bridge/npp_bridge.cpp` + `core/correction/npp_client.py`) directly into G-Coach's background correction engine (`core/correction/engine.py`) via an application-specific adapter (`core/correction/npp_adapter.py`).

```text
CorrectionController (UI Accept)
        │
        ▼
BackgroundCorrectionEngine.apply_correction_to_target()
        │
        ├── If Notepad++ target ──► NppCorrectionAdapter.apply_bridge_correction()
        │                                   │
        │                                   ▼
        │                           NppBridgeClient (Named Pipe)
        │                                   │
        │                                   ▼
        │                           gcoach_npp_bridge.dll (In-Process N++)
        │                                   │
        │                                   ▼
        │                           Scintilla Buffer (Verified & Replaced)
        │
        └── Else ────────────────► Existing UIA Path (Telegram, Firefox, etc.)
```

## Safety & Security Protections Maintained
- **Zero Cross-Process Memory Corruption**: All Scintilla operations occur exclusively in-process inside `notepad++.exe`.
- **Stale Protection**: Pre-write range read validates that `expected_original` matches the live Scintilla text at `[start:end]`.
- **Post-Write Verification**: Post-write text read validates that the replacement was correctly inserted.
- **Application Isolation**: Non-Notepad++ applications (Telegram, Firefox, etc.) continue using the existing robust UIA path without interference.
- **Named Pipe Security**: Windows Security Descriptors restrict pipe access strictly to the current user session SID.

## Documentation Updates (Phase 8G.5 vs 8G.6)
- **Phase 8G.5**: Established the native C++ plugin bridge, Named Pipe server protocol, and Python test client.
- **Phase 8G.6**: Integrated the bridge into G-Coach's correction pipeline (`BackgroundCorrectionEngine` -> `NppCorrectionAdapter` -> `NppBridgeClient`), enabling seamless one-click corrections from the floating popup in Notepad++.
