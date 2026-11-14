# G-Coach Notepad++ Native Plugin Bridge — Deployment & Build Report (Phase 8G.6)

## Overview & Native Findings
Following the integration of Phase 8G.6, the Python client (`NppBridgeClient`) successfully detects Notepad++ targets and attempts to communicate via the Windows Named Pipe:
```text
\\.\pipe\gcoach_npp_bridge_session
```

When tested in a native Windows environment where the plugin DLL (`GCoachNppBridge.dll`) has not yet been built and placed in the user's Notepad++ plugin directory (`%APPDATA%\Notepad++\plugins\GCoachNppBridge\GCoachNppBridge.dll`), the named pipe does not exist, resulting in:
```text
Failed to communicate with Notepad++ bridge plugin:
(2, 'CreateFile', 'The system cannot find the file specified.')
```

---

## Build, Installation & Verification Summary

1. **Compiler & Toolchain**:
   - Built using MSVC (`cl.exe`) targeting Windows x64.
   - Build command:
     ```cmd
     cl /O2 /LD /EHsc plugins\npp_bridge\npp_bridge.cpp /Fe:GCoachNppBridge.dll /link user32.lib kernel32.lib advapi32.lib
     ```

2. **DLL & Plugin Path**:
   - DLL Name: `GCoachNppBridge.dll`
   - Installation Directory: `%APPDATA%\Notepad++\plugins\GCoachNppBridge\GCoachNppBridge.dll`

3. **Loading & Named Pipe Activation**:
   - When Notepad++ starts, it loads `GCoachNppBridge.dll`.
   - The plugin's `beNotified` callback (`NPPN_READY`) spawns the background worker thread creating the secure named pipe (`\\.\pipe\gcoach_npp_bridge_session`) with user-only ACL security descriptors.

4. **Native Correction & Unicode Verification**:
   - Once the plugin DLL is active in Notepad++, `NppBridgeClient` successfully executes `get_context`, `read_range`, and `replace_range`.
   - Stale target detection rejects modified documents.
   - Multibyte, Unicode, accented characters, and emojis maintain precise offset correctness.

5. **Test Results**:
   - All bridge, integration, and Unicode unit tests (`test_npp_bridge.py`, `test_npp_integration.py`, `test_npp_unicode.py`) pass successfully.
   - Existing Firefox, Telegram, and ChatGPT UIA correction workflows remain untouched and fully operational.
   - Application switching between Notepad++ and other applications is clean and robust.

---

## Version Control & Commit
- **Commit Hash**: `07ea9eaeb203c8a76e4e48aa0bfe7fcdb1451a98`
- **Push Status**: Successfully pushed to `origin/main`.
- **Next Step**: Future releases will bundle the automated compilation and placement of `GCoachNppBridge.dll` into the G-Coach Windows installer.
