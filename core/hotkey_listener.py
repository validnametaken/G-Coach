"""
Global Hotkey Listener - Captures selected text and replaces it
Using keyboard library for global shortcuts
"""

import threading
import time
import ctypes
import os
from pathlib import Path
from typing import Callable
import pyperclip

from core.selection_resolver import SelectionResolver


class HotkeyListener:
    """Global hotkey listener + selected text replacement."""

    def __init__(self, config_manager, api_client, prompt_manager):
        self.config_manager = config_manager
        self.api_client = api_client
        self.prompt_manager = prompt_manager
        self._hotkey_id = None
        self._running = False
        self._hotkey_pressed = False
        self._workflow_lock = threading.Lock()
        self._on_status: Callable[[str], None] = lambda msg: None
        self._on_processing_start: Callable[[], None] = lambda: None
        self._on_processing_end: Callable[[], None] = lambda: None

        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32
        self._run_id = f"{os.getpid()}-{int(time.time() * 1000) % 1000000}"
        self._log_file = Path.home() / ".ai_prompt_optimizer" / "hotkey_debug.log"
        self._selection_resolver = SelectionResolver(self._log)

        self._log("INIT", "Initialization completed")

    def _log(self, event: str, message: str = ""):
        line = f"[HotkeyListener][pid={os.getpid()}][run={self._run_id}][{event}] {message}"
        print(line)
        try:
            self._log_file.parent.mkdir(parents=True, exist_ok=True)
            with self._log_file.open("a", encoding="utf-8") as f:
                f.write(f"{time.time():.3f} {line}\n")
        except Exception:
            pass

    def set_status_callback(self, callback):
        self._on_status = callback

    def set_processing_callbacks(self, start_callback, end_callback):
        self._on_processing_start = start_callback
        self._on_processing_end = end_callback

    def start(self):
        if self._running:
            return
        self._running = True
        try:
            self._register_hotkey()
            hotkey_str = self._build_hotkey_string()
            self._on_status(f"Global hotkey active: {hotkey_str}")
            self._log("START", f"Started successfully, hotkey: {hotkey_str}")
        except Exception as e:
            self._running = False
            self._on_status(f"Failed to start hotkey: {e}")
            self._log("START_FAIL", f"Start failed: {e}")

    def stop(self):
        self._running = False
        self._unregister_hotkey()
        self._on_status("Global hotkey stopped")

    def restart(self):
        was_running = self._running
        self.stop()
        if was_running:
            self.start()

    def _build_hotkey_string(self) -> str:
        hotkey_config = self.config_manager.get_hotkey()
        modifiers = hotkey_config.get("modifiers", ["ctrl", "shift"])
        key = hotkey_config.get("key", "o")
        return "+".join(modifiers + [key])

    def _register_hotkey(self):
        import keyboard
        hotkey_str = self._build_hotkey_string()
        self._hotkey_id = keyboard.add_hotkey(
            hotkey_str,
            self._on_hotkey_triggered,
            suppress=False,
            trigger_on_release=False,
        )

    def _unregister_hotkey(self):
        import keyboard
        if self._hotkey_id is not None:
            try:
                keyboard.remove_hotkey(self._hotkey_id)
            except Exception:
                pass
            self._hotkey_id = None

    def _on_hotkey_triggered(self):
        self._log("TRIGGER", "Hotkey triggered")
        if not self._workflow_lock.acquire(blocking=False):
            self._log("TRIGGER_IGNORED", "Workflow already in progress")
            return
        if self._hotkey_pressed:
            self._log("TRIGGER_IGNORED", "Status still processing")
            self._workflow_lock.release()
            return
        self._hotkey_pressed = True
        try:
            threading.Thread(target=self._replace_workflow, daemon=True).start()
        except Exception:
            self._hotkey_pressed = False
            self._workflow_lock.release()
            raise

    def _release_modifiers(self):
        """Release all modifier keys."""
        for vk in [0x11, 0x10, 0x12, 0x5B]:  # Ctrl, Shift, Alt, Win
            self._user32.keybd_event(vk, 0, 2, 0)  # KEYEVENTF_KEYUP

    def _bring_to_front(self, hwnd):
        """Bring window to foreground."""
        target_tid = self._user32.GetWindowThreadProcessId(hwnd, None)
        my_tid = self._kernel32.GetCurrentThreadId()
        if target_tid != my_tid:
            self._user32.AttachThreadInput(my_tid, target_tid, True)
        self._user32.SetForegroundWindow(hwnd)
        self._user32.BringWindowToTop(hwnd)
        if target_tid != my_tid:
            self._user32.AttachThreadInput(my_tid, target_tid, False)

    def _replace_workflow(self):
        """Replacement workflow."""
        processing_started = False
        import time
        self._log("WORKFLOW_START", "Workflow started, resetting status")
        # Ensure starting from clean status, reset loading window
        self._on_processing_end()
        try:
            self._log("WORKFLOW_RESET_DONE", "Status reset completed")
            self._log("WORKFLOW_RUNNING", "Starting workflow")

            # 1. Save target window
            target_hwnd = self._user32.GetForegroundWindow()
            title_len = self._user32.GetWindowTextLengthW(target_hwnd)
            if title_len > 0:
                buf = ctypes.create_unicode_buffer(title_len + 1)
                self._user32.GetWindowTextW(target_hwnd, buf, title_len + 1)
                self._log("TARGET", f"Target window: {buf.value}")

            # 2. Release modifier keys
            self._release_modifiers()
            time.sleep(0.05)

            # 3. Update status first without showing loading animation; confirm clear selection before processing
            self._on_status("Fetching selected text...")

            # 4. Ensure target window still has focus
            current_hwnd = self._user32.GetForegroundWindow()
            if current_hwnd != target_hwnd:
                print(f"[HotkeyListener] Focus lost, restoring...")
                self._bring_to_front(target_hwnd)
                time.sleep(0.1)

            # 5. Use layered selection resolver: UIA/Accessibility preferred; clipboard enabled only for whitelisted standard apps.
            capture = self._selection_resolver.capture(target_hwnd)
            if not capture.ok:
                self._log(
                    "CAPTURE_REJECTED",
                    f"method={capture.method} app={capture.source_app} reason={capture.blocked_reason}",
                )
                self._on_processing_end()
                self._on_status("No explicit text selection detected")
                self._hotkey_pressed = False
                return
            selected_text = capture.text
            self._log(
                "SELECTED_TEXT",
                f"method={capture.method} app={capture.source_app} text={repr(selected_text[:50])}",
            )

            # 6. Get prompt
            active_id = self.config_manager.get_active_prompt_id()
            prompt = self.prompt_manager.get_by_id(active_id)
            if not prompt:
                self._on_status("Active prompt not found")
                self._hotkey_pressed = False
                self._on_processing_end()
                return
            self._log("PROMPT_SELECTED", f"Using prompt: {prompt['name']}")
            self._on_processing_start()
            processing_started = True
            self._on_status("Invoking AI...")

            # 11. Call API
            result_holder = {"text": None, "error": None}
            event = threading.Event()

            def on_success(text):
                result_holder["text"] = text
                event.set()

            def on_error(error):
                result_holder["error"] = error
                event.set()

            self.api_client.call(
                user_input=selected_text,
                prompt_template=prompt["content"],
                on_success=on_success,
                on_error=on_error,
            )

            self._log("API_ENTER", "Waiting for API response")
            if not event.wait(timeout=20):
                self._log("API_TIMEOUT", "API no response for 20s")
                self._on_status("API timeout")
                self._on_processing_end()
                processing_started = False
                self._hotkey_pressed = False
                return

            if result_holder["error"]:
                self._log("API_ERROR", result_holder["error"])
                self._on_status(f"Error: {result_holder['error']}")
                self._on_processing_end()
                processing_started = False
                self._hotkey_pressed = False
                return

            if result_holder["text"] is None:
                self._log("API_TIMEOUT", "API returned empty")
                self._on_status("API timeout")
                self._on_processing_end()
                processing_started = False
                self._hotkey_pressed = False
                return

            optimized_text = result_holder["text"].strip()
            self._log("API_RESULT", f"Optimized result: {repr(optimized_text[:50])}")

            # 12. Copy result and paste
            self._log("PASTE_ENTER", "Preparing to copy result and paste")
            pyperclip.copy(optimized_text)
            time.sleep(0.1)

            # Ensure target window has focus
            current_hwnd = self._user32.GetForegroundWindow()
            if current_hwnd != target_hwnd:
                self._bring_to_front(target_hwnd)
                time.sleep(0.1)

            self._user32.keybd_event(0x11, 0, 0, 0)   # Ctrl down
            time.sleep(0.02)
            self._user32.keybd_event(0x56, 0, 0, 0)    # V down
            time.sleep(0.02)
            self._user32.keybd_event(0x56, 0, 2, 0)    # V up
            time.sleep(0.02)
            self._user32.keybd_event(0x11, 0, 2, 0)    # Ctrl up

            self._on_status("Replacement completed!")

        except Exception as e:
            print(f"[HotkeyListener] Exception: {e}")
            import traceback
            traceback.print_exc()
            self._on_status(f"Error: {str(e)}")
        finally:
            if processing_started:
                self._on_processing_end()
            self._hotkey_pressed = False
