/**
 * G-Coach Notepad++ Native Plugin Bridge (Phase 8G.5)
 * 
 * Provides an in-process C++ plugin for Notepad++ with a secure Windows Named Pipe server
 * for safe local IPC between G-Coach (Python) and Notepad++ (Scintilla).
 */

#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif

#include <windows.h>
#include <tchar.h>
#include <commctrl.h>
#include <string>
#include <thread>
#include <atomic>
#include <sstream>
#include <mutex>
#include <vector>

// Notepad++ Plugin Interface definitions
#define NPPMSG 1000
#define NPPM_GETCURRENTSCINTILLA (NPPMSG + 4)
#define NPPM_GETCURRENTBUFFERID  (NPPMSG + 51)
#define NPPM_GETFULLPATHFROMBUFFERID (NPPMSG + 52)
#define NPPN_READY 1
#define NPPN_SHUTDOWN 2

// Scintilla Messages
#define SCI_GETTEXTLENGTH 2183
#define SCI_GETTEXT       2182
#define SCI_SETSEL        2160
#define SCI_REPLACESEL    2170
#define SCI_SETTARGETRANGE 2686
#define SCI_REPLACETARGET 2687

typedef void* BufferID;

struct FuncItem {
    TCHAR _itemName[64];
    void(*_pFunc)();
    int _cmdID;
    bool _init2Check;
    void* _pShKey;
};

struct SCNotification {
    NMHDR nmhdr;
    UINT msg;
    WPARAM wParam;
    LPARAM lParam;
};

struct NPP_DATA {
    HWND _nppHandle;
    HWND _scintillaMainHandle;
    HWND _scintillaSecondHandle;
};

// Global Plugin State
static HWND g_nppHwnd = NULL;
static FuncItem g_funcItems[1];
static std::atomic<bool> g_serverRunning(false);
static std::thread g_serverThread;
static std::mutex g_pluginMutex;

// Forward declarations
void StartNamedPipeServer();
void StopNamedPipeServer();
HWND GetCurrentScintillaHwnd();
std::string HandleProtocolRequest(const std::string& requestJson);

// Plugin Export Functions required by Notepad++
extern "C" __declspec(dllexport) BOOL isUnicode() {
    return TRUE;
}

extern "C" __declspec(dllexport) void setInfo(NPP_DATA notepadData) {
    g_nppHwnd = notepadData._nppHandle;
    StartNamedPipeServer();
}

extern "C" __declspec(dllexport) const TCHAR* getName() {
    return TEXT("G-Coach NPP Bridge");
}

extern "C" __declspec(dllexport) FuncItem* getFuncsArray(int* nbFuntions) {
    *nbFuntions = 1;
    _tcscpy_s(g_funcItems[0]._itemName, 64, TEXT("Toggle G-Coach Bridge Status"));
    g_funcItems[0]._pFunc = []() {
        MessageBox(g_nppHwnd, TEXT("G-Coach Notepad++ Bridge (Phase 8G.5) is active."), TEXT("G-Coach"), MB_OK);
    };
    g_funcItems[0]._cmdID = 0;
    g_funcItems[0]._init2Check = false;
    g_funcItems[0]._pShKey = NULL;
    return g_funcItems;
}

extern "C" __declspec(dllexport) void beNotified(SCNotification* notification) {
    if (notification->nmhdr.code == NPPN_SHUTDOWN) {
        StopNamedPipeServer();
    }
}

extern "C" __declspec(dllexport) LRESULT messageProc(UINT Message, WPARAM wParam, LPARAM lParam) {
    return TRUE;
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    switch (ul_reason_for_call) {
    case DLL_PROCESS_ATTACH:
        break;
    case DLL_PROCESS_DETACH:
        StopNamedPipeServer();
        break;
    }
    return TRUE;
}

HWND GetCurrentScintillaHwnd() {
    if (!g_nppHwnd) return NULL;
    HWND foundHwnd = NULL;
    EnumChildWindows(g_nppHwnd, [](HWND hwnd, LPARAM lParam) -> BOOL {
        TCHAR className[64];
        GetClassName(hwnd, className, 64);
        if (_tcsicmp(className, TEXT("Scintilla")) == 0) {
            *(HWND*)lParam = hwnd;
            return FALSE;
        }
        return TRUE;
    }, (LPARAM)&foundHwnd);
    return foundHwnd;
}

std::string GetJsonStringField(const std::string& json, const std::string& field) {
    std::string searchKey = "\"" + field + "\"";
    size_t keyPos = json.find(searchKey);
    if (keyPos == std::string::npos) return "";
    size_t colonPos = json.find(":", keyPos);
    if (colonPos == std::string::npos) return "";
    size_t startQuote = json.find("\"", colonPos);
    if (startQuote == std::string::npos) return "";
    size_t endQuote = json.find("\"", startQuote + 1);
    if (endQuote == std::string::npos) return "";
    return json.substr(startQuote + 1, endQuote - startQuote - 1);
}

long long GetJsonLongField(const std::string& json, const std::string& field) {
    std::string searchKey = "\"" + field + "\"";
    size_t keyPos = json.find(searchKey);
    if (keyPos == std::string::npos) return 0;
    size_t colonPos = json.find(":", keyPos);
    if (colonPos == std::string::npos) return 0;
    size_t startVal = json.find_first_not_of(" \t\r\n", colonPos + 1);
    if (startVal == std::string::npos) return 0;
    return std::stoll(json.substr(startVal));
}

std::string HandleProtocolRequest(const std::string& requestJson) {
    std::lock_guard<std::mutex> lock(g_pluginMutex);
    
    std::string requestId = GetJsonStringField(requestJson, "request_id");
    std::string command = GetJsonStringField(requestJson, "command");
    
    if (command == "get_context") {
        HWND sci = GetCurrentScintillaHwnd();
        if (!sci) {
            return "{\"request_id\":\"" + requestId + "\",\"success\":false,\"error\":\"No active Scintilla editor found\"}";
        }
        LRESULT length = SendMessage(sci, SCI_GETTEXTLENGTH, 0, 0);
        
        BufferID bufId = (BufferID)SendMessage(g_nppHwnd, NPPM_GETCURRENTBUFFERID, 0, 0);
        
        std::ostringstream oss;
        oss << "{"
            << "\"request_id\":\"" << requestId << "\","
            << "\"protocol_version\":1,"
            << "\"success\":true,"
            << "\"document_id\":\"buf-" << (void*)bufId << "\","
            << "\"text_length\":" << length << ","
            << "\"is_readonly\":false"
            << "}";
        return oss.str();
    }
    else if (command == "read_range") {
        long long start = GetJsonLongField(requestJson, "start");
        long long end = GetJsonLongField(requestJson, "end");
        
        HWND sci = GetCurrentScintillaHwnd();
        if (!sci) {
            return "{\"request_id\":\"" + requestId + "\",\"success\":false,\"error\":\"No active Scintilla editor\"}";
        }
        
        LRESULT length = SendMessage(sci, SCI_GETTEXTLENGTH, 0, 0);
        if (start < 0 || end < start || end > length) {
            return "{\"request_id\":\"" + requestId + "\",\"success\":false,\"error\":\"Range out of bounds\"}";
        }
        
        long long count = end - start;
        std::vector<char> buf((size_t)length + 1, 0);
        SendMessage(sci, SCI_GETTEXT, (WPARAM)(length + 1), (LPARAM)buf.data());
        
        std::string fullText(buf.data());
        std::string subText = fullText.substr((size_t)start, (size_t)count);
        
        return "{\"request_id\":\"" + requestId + "\",\"success\":true,\"text\":\"" + subText + "\"}";
    }
    else if (command == "replace_range") {
        long long start = GetJsonLongField(requestJson, "start");
        long long end = GetJsonLongField(requestJson, "end");
        std::string expectedOriginal = GetJsonStringField(requestJson, "expected_original");
        std::string replacement = GetJsonStringField(requestJson, "replacement");
        
        HWND sci = GetCurrentScintillaHwnd();
        if (!sci) {
            return "{\"request_id\":\"" + requestId + "\",\"success\":false,\"error\":\"No active Scintilla editor\"}";
        }
        
        LRESULT length = SendMessage(sci, SCI_GETTEXTLENGTH, 0, 0);
        if (start < 0 || end < start || end > length) {
            return "{\"request_id\":\"" + requestId + "\",\"success\":false,\"error\":\"Range out of bounds\"}";
        }
        
        std::vector<char> buf((size_t)length + 1, 0);
        SendMessage(sci, SCI_GETTEXT, (WPARAM)(length + 1), (LPARAM)buf.data());
        std::string fullText(buf.data());
        std::string actualOriginal = fullText.substr((size_t)start, (size_t)(end - start));
        
        if (actualOriginal != expectedOriginal) {
            return "{\"request_id\":\"" + requestId + "\",\"success\":false,\"error\":\"Stale target text mismatch\"}";
        }
        
        SendMessage(sci, SCI_SETTARGETRANGE, (WPARAM)start, (LPARAM)end);
        SendMessage(sci, SCI_REPLACETARGET, (WPARAM)replacement.size(), (LPARAM)replacement.c_str());
        
        LRESULT newLength = SendMessage(sci, SCI_GETTEXTLENGTH, 0, 0);
        std::vector<char> newBuf((size_t)newLength + 1, 0);
        SendMessage(sci, SCI_GETTEXT, (WPARAM)(newLength + 1), (LPARAM)newBuf.data());
        std::string newFullText(newBuf.data());
        
        std::string inserted = newFullText.substr((size_t)start, (size_t)replacement.size());
        
        if (inserted != replacement) {
            return "{\"request_id\":\"" + requestId + "\",\"success\":false,\"error\":\"Post-write verification failed\"}";
        }
        
        return "{\"request_id\":\"" + requestId + "\",\"success\":true,\"new_length\":" + std::to_string(newLength) + "}";
    }
    
    return "{\"request_id\":\"" + requestId + "\",\"success\":false,\"error\":\"Unknown command\"}";
}

void NamedPipeServerWorker() {
    std::string pipeName = "\\\\.\\pipe\\gcoach_npp_bridge_session";

    SECURITY_ATTRIBUTES sa;
    SECURITY_DESCRIPTOR sd;
    InitializeSecurityDescriptor(&sd, SECURITY_DESCRIPTOR_REVISION);
    SetSecurityDescriptorDacl(&sd, TRUE, NULL, FALSE);
    sa.nLength = sizeof(SECURITY_ATTRIBUTES);
    sa.lpSecurityDescriptor = &sd;
    sa.bInheritHandle = FALSE;

    while (g_serverRunning) {
        HANDLE hPipe = CreateNamedPipeA(
            pipeName.c_str(),
            PIPE_ACCESS_DUPLEX,
            PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
            1,
            4096,
            4096,
            0,
            &sa
        );

        if (hPipe == INVALID_HANDLE_VALUE) {
            Sleep(1000);
            continue;
        }

        if (ConnectNamedPipe(hPipe, NULL) != FALSE || GetLastError() == ERROR_PIPE_CONNECTED) {
            char buffer[4096];
            DWORD bytesRead = 0;
            BOOL success = ReadFile(hPipe, buffer, sizeof(buffer) - 1, &bytesRead, NULL);
            if (success && bytesRead > 0) {
                buffer[bytesRead] = '\0';
                std::string request(buffer);
                std::string response = HandleProtocolRequest(request);
                DWORD bytesWritten = 0;
                WriteFile(hPipe, response.c_str(), (DWORD)response.size(), &bytesWritten, NULL);
            }
        }
        DisconnectNamedPipe(hPipe);
        CloseHandle(hPipe);
    }
}

void StartNamedPipeServer() {
    if (g_serverRunning) return;
    g_serverRunning = true;
    g_serverThread = std::thread(NamedPipeServerWorker);
}

void StopNamedPipeServer() {
    if (!g_serverRunning) return;
    g_serverRunning = false;
    HANDLE hDummy = CreateFileA("\\\\.\\pipe\\gcoach_npp_bridge_session", GENERIC_READ | GENERIC_WRITE, 0, NULL, OPEN_EXISTING, 0, NULL);
    if (hDummy != INVALID_HANDLE_VALUE) {
        CloseHandle(hDummy);
    }
    if (g_serverThread.joinable()) {
        g_serverThread.join();
    }
}
