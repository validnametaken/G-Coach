# G-Coach Notepad++ Native Plugin Bridge Build & Deployment Guide (Phase 8G.6 / Troubleshooting)

## Overview
To provide G-Coach with secure, in-process read/write access to Notepad++ documents without cross-process memory violations or application crashes, G-Coach uses a native C++ plugin (`GCoachNppBridge.dll`) running inside `notepad++.exe`.

Named Pipe endpoint exposed by the plugin:
```text
\\.\pipe\gcoach_npp_bridge_session
```

---

## 1. Prerequisites & Toolchain
- **Operating System**: Windows 64-bit
- **Compiler**: Microsoft Visual Studio (Community/Professional/Enterprise) with C++ Desktop Development workload (MSVC `cl.exe`, Windows SDK).
- **Target Architecture**: x64 (64-bit), matching the user's 64-bit Notepad++ installation.

---

## 2. Compilation Instructions (MSVC)
To compile `plugins/npp_bridge/npp_bridge.cpp` into `GCoachNppBridge.dll`:

1. Open **Developer Command Prompt for VS** (or configure MSVC environment).
2. Run the build command:
```cmd
cl /O2 /LD /EHsc plugins\npp_bridge\npp_bridge.cpp /Fe:GCoachNppBridge.dll /link user32.lib kernel32.lib advapi32.lib
```
This produces `GCoachNppBridge.dll`.

---

## 3. Installation Location
Notepad++ loads plugins from specific directories. For 64-bit Notepad++ on Windows, the per-user plugin directory is typically:
```text
%APPDATA%\Notepad++\plugins\GCoachNppBridge\GCoachNppBridge.dll
```
*(Note: Notepad++ expects each plugin to reside in a subfolder whose name matches the DLL name without extension, i.e., `GCoachNppBridge\GCoachNppBridge.dll`).*

*Initialization Note*: The plugin starts its secure Named Pipe server immediately upon loading inside `setInfo()`, guaranteeing that `\\.\pipe\gcoach_npp_bridge_session` is active as soon as Notepad++ initializes the plugin.*

---

## 4. Verification & Troubleshooting
1. **Launch Notepad++**: Start Notepad++.
2. **Check Plugins Menu**: Confirm "G-Coach NPP Bridge" appears under the Plugins menu or plugin list.
3. **Verify Named Pipe**: While Notepad++ is running, confirm the named pipe is active:
   ```cmd
   sc query
   ```
   or via PowerShell:
   ```powershell
   [System.IO.Pipes.NamedPipeClientStream]::new(".", "gcoach_npp_bridge_session", [System.IO.Pipes.PipeDirection]::InOut).Connect(1000)
   ```
4. **Test via G-Coach Python Client**:
   ```python
   from core.correction.npp_client import NppBridgeClient
   client = NppBridgeClient()
   print(client.get_context())
   ```
