# G-Coach Notepad++ Native Plugin Bridge (Phase 8G.5)

## Architecture Overview
To solve the cross-process pointer corruption and Scintilla crash issue encountered in Phase 8G, G-Coach utilizes a dedicated native C++ plugin (`gcoach_npp_bridge.dll`) running **in-process** inside `notepad++.exe`.

```text
G-Coach Python Process
        │
        │ Windows Named Pipe (\\.\pipe\gcoach_npp_bridge_session)
        ▼
G-Coach Notepad++ Bridge DLL (In-Process)
        │
        │ Direct Win32 / Scintilla Messages (SendMessage)
        ▼
Notepad++ Active Scintilla Document
```

## Why Direct Cross-Process SendMessage Failed
In Windows, Scintilla messages such as `SCI_GETTEXT` (`2182`) require a caller-supplied buffer pointer in `lparam`. When an external process (`G-Coach`) sends `SCI_GETTEXT` across process boundaries with a pointer residing in G-Coach's virtual memory address space, Notepad++ experiences an Access Violation / memory corruption trying to write to unmapped memory, resulting in an application crash. 

Moving the Scintilla interaction **in-process** via a native plugin DLL entirely eliminates cross-process pointer passing.

---

## IPC Protocol & Commands

Communication occurs via JSON payloads over a secure per-user Windows Named Pipe.

### 1. Get Context
```json
{
  "request_id": "req-1",
  "command": "get_context",
  "protocol_version": 1
}
```
**Response:**
```json
{
  "request_id": "req-1",
  "protocol_version": 1,
  "success": true,
  "document_id": "buf-0000021A4C20A880",
  "text_length": 150,
  "is_readonly": false
}
```

### 2. Read Range
```json
{
  "request_id": "req-2",
  "command": "read_range",
  "protocol_version": 1,
  "start": 10,
  "end": 13
}
```
**Response:**
```json
{
  "request_id": "req-2",
  "success": true,
  "text": "was"
}
```

### 3. Replace Range (with Stale Check & Post-Write Verification)
```json
{
  "request_id": "req-3",
  "command": "replace_range",
  "protocol_version": 1,
  "start": 10,
  "end": 13,
  "expected_original": "was",
  "replacement": "were"
}
```
**Response:**
```json
{
  "request_id": "req-3",
  "success": true,
  "new_length": 151
}
```

---

## Security Model
- **Named Pipe ACLs**: The Named Pipe is created using a security descriptor that allows access strictly to the currently logged-on user SID (`InitializeSecurityDescriptor` + default user ACL), preventing unauthorized local processes from issuing editing commands.
- **Local-Only**: No TCP sockets or network ports are opened.

---

## Manual Native Test Procedure
1. Launch Notepad++ (x64) with `gcoach_npp_bridge.dll` installed in `%APPDATA%\Notepad++\plugins\GCoachBridge\`.
2. Open a document containing test text.
3. Run the Python test client or invoke `NppBridgeClient` methods.
4. Verify context retrieval, range reading, and verified replacement.
