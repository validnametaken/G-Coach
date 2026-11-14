"""
实时文本监控器、防抖动与过期结果保护 (Live Text Monitor & Stale Result Protection) - Phase 5
"""

import logging
import queue
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

from core.analysis import Finding, AnalysisPipeline, AnalysisResolver
from .capture import TextSource, TextSnapshot, MockTextSource

logger = logging.getLogger(__name__)


@dataclass
class MonitorState:
    """监控器状态快照（Monitor State API）

    供未来 UI 消费的完整状态对象。
    """
    generation: int = 0
    text: str = ""
    findings: List[Finding] = field(default_factory=list)
    status: str = "idle"  # "idle", "waiting", "analyzing", "ready", "unsupported", "error"
    timestamp: float = field(default_factory=time.time)
    app_name: str = ""
    control_info: str = ""
    control_id: str = ""
    process_id: int = 0
    control_type: str = ""
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class LiveTextMonitor:
    """实时文本监控器（Live Text Monitor）

    协调文本捕获、防抖动（Debounce）、代数追踪（Generation Tracking）、
    过期结果保护（Stale Result Protection）以及后台分析管道与消解层。
    """

    def __init__(
        self,
        text_source: TextSource,
        pipeline: AnalysisPipeline,
        resolver: AnalysisResolver,
        debounce_interval: float = 0.4,  # 默认 400 ms
        poll_interval: float = 0.05,     # 内部轮询检查间隔
    ):
        self.text_source = text_source
        self.pipeline = pipeline
        self.resolver = resolver
        self.debounce_interval = debounce_interval
        self.poll_interval = poll_interval

        self._current_generation = 0
        self._last_captured_text = ""
        self._last_control_id = ""
        self._last_change_time = 0.0
        # Keep capture failures distinct from analysis failures. Both are
        # exposed as status="error", but only a capture failure means the
        # current editor context was lost and must be reacquired as new.
        self._capture_failed = False
        self._is_running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        # UI Automation COM objects are apartment-bound. Keep every UIA read,
        # geometry query, and correction on the one thread that owns the UIA
        # client, rather than passing Control/Pattern objects to the Qt thread.
        self._monitor_commands: queue.Queue = queue.Queue()

        # 当前发布状态
        self._state = MonitorState(status="idle")

        # 正在分析或已完成的最新状态追踪
        self._analyzing_generation = 0

    def start(self) -> None:
        """启动实时监控线程"""
        with self._lock:
            if self._is_running:
                return
            if self._monitor_thread and self._monitor_thread.is_alive():
                logger.warning("Cannot restart LiveTextMonitor while its previous thread is still stopping.")
                return
            self._is_running = True
            self._state.status = "waiting"
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()
            logger.info("LiveTextMonitor started.")

    def stop(self) -> None:
        """停止实时监控线程"""
        with self._lock:
            if not self._is_running:
                return
            self._is_running = False
            self._state.status = "idle"
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("LiveTextMonitor did not stop within the join timeout.")
        else:
            logger.info("LiveTextMonitor stopped.")

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._is_running

    def run_on_monitor_thread(self, callback: Callable[..., Any], *args, **kwargs) -> Any:
        """Run a synchronous operation on the monitor thread.

        This is the only supported route for UIA operations initiated by the
        GUI. It keeps COM-backed controls and patterns inside their creating
        apartment while returning only ordinary Python results to the caller.
        """
        if threading.current_thread() is self._monitor_thread:
            return callback(*args, **kwargs)

        with self._lock:
            if not self._is_running or not self._monitor_thread or not self._monitor_thread.is_alive():
                raise RuntimeError("The UI Automation monitor thread is not running.")
            future: Future = Future()
            self._monitor_commands.put((callback, args, kwargs, future))

        return future.result()

    def get_state(self) -> MonitorState:
        """获取当前的监控器状态（线程安全）"""
        with self._lock:
            # 返回状态副本以防外部修改
            return MonitorState(
                generation=self._state.generation,
                text=self._state.text,
                findings=list(self._state.findings),
                status=self._state.status,
                timestamp=self._state.timestamp,
                app_name=self._state.app_name,
                control_info=self._state.control_info,
                control_id=self._state.control_id,
                process_id=self._state.process_id,
                control_type=self._state.control_type,
                error_message=self._state.error_message,
                metadata=dict(self._state.metadata),
            )

    def trigger_check(self) -> Optional[MonitorState]:
        """手动触发一次文本捕获和检查（主要用于单次测试或事件驱动触发）"""
        if self.is_running and threading.current_thread() is not self._monitor_thread:
            return self.run_on_monitor_thread(self._poll_once)
        return self._poll_once()

    def force_recheck(self) -> Optional[MonitorState]:
        """强制对当前文本重新执行分析（即使文本未发生变化），用于词典更新等场景"""
        with self._lock:
            gen_to_analyze = self._current_generation + 1
            self._current_generation = gen_to_analyze
            text_to_analyze = self._last_captured_text
            self._state.generation = gen_to_analyze
            self._state.status = "analyzing"
            self._analyzing_generation = gen_to_analyze

            worker = threading.Thread(
                target=self._run_analysis_async,
                args=(gen_to_analyze, text_to_analyze),
                daemon=True,
            )
            worker.start()
            logger.info(f"Forced re-check triggered for gen {gen_to_analyze}.")
        return self.get_state()

    def _monitor_loop(self) -> None:
        """后台监控与防抖循环"""
        import os
        initialize_uia = getattr(self.text_source, "initialize_for_current_thread", None)
        uninitialize_uia = getattr(self.text_source, "uninitialize_for_current_thread", None)
        try:
            if callable(initialize_uia):
                initialize_uia()

            while True:
                with self._lock:
                    if not self._is_running:
                        break

                try:
                    command = self._monitor_commands.get(timeout=self.poll_interval)
                except queue.Empty:
                    command = None

                if command is not None:
                    callback, args, kwargs, future = command
                    if future.set_running_or_notify_cancel():
                        try:
                            future.set_result(callback(*args, **kwargs))
                        except Exception as exc:
                            future.set_exception(exc)
                            logger.error("Monitor-thread operation failed: %s", exc, exc_info=True)

                with self._lock:
                    if not self._is_running:
                        break

                isolation_mode = os.environ.get("GCOACH_POPUP_ISOLATION", "").strip().lower()
                if isolation_mode == "popup":
                    # Isolated popup tests must not perform global UIA polling.
                    continue

                if isolation_mode == "monitor":
                    print("[Phase8E isolation monitor] polling UIA focus...")

                self._poll_once()
        except Exception as exc:
            logger.error("LiveTextMonitor thread failed: %s", exc, exc_info=True)
            with self._lock:
                self._is_running = False
                self._state.status = "error"
                self._state.error_message = str(exc)
        finally:
            self._fail_pending_monitor_commands()
            if callable(uninitialize_uia):
                try:
                    uninitialize_uia()
                except Exception as exc:
                    logger.error("Could not uninitialize UI Automation on its owner thread: %s", exc, exc_info=True)

    def _fail_pending_monitor_commands(self) -> None:
        """Wake GUI callers if the monitor stops before their command runs."""
        while True:
            try:
                _callback, _args, _kwargs, future = self._monitor_commands.get_nowait()
            except queue.Empty:
                return
            if not future.done():
                future.set_exception(RuntimeError("The UI Automation monitor thread stopped before the operation ran."))

    def _poll_once(self) -> Optional[MonitorState]:
        """单次轮询：获取文本、检查变化、管理防抖并触发分析"""
        try:
            snapshot = self.text_source.get_current_text()
        except Exception as e:
            logger.error(f"Error getting text from source: {e}", exc_info=True)
            with self._lock:
                # A failed capture must invalidate any analysis still running
                # for the last successful snapshot. Otherwise that old result
                # can repopulate findings while the current target is unknown.
                if (
                    self._state.status != "error"
                    or self._last_control_id
                    or self._last_captured_text
                    or self._state.findings
                ):
                    self._current_generation += 1
                self._capture_failed = True
                self._last_control_id = ""
                self._last_captured_text = ""
                self._last_change_time = time.time()
                self._state.generation = self._current_generation
                self._state.text = ""
                self._state.findings = []
                self._state.app_name = ""
                self._state.control_info = ""
                self._state.control_id = ""
                self._state.process_id = 0
                self._state.control_type = ""
                self._state.metadata = {}
                self._state.timestamp = time.time()
                self._state.status = "error"
                self._state.error_message = str(e)
            return self.get_state()

        if (
            snapshot.metadata.get("foreground_is_self")
            or snapshot.metadata.get("uia_focus_is_self")
        ):
            # G-Coach-owned windows can briefly become foreground, or one of
            # their non-activating child controls can receive UIA focus while
            # the editor remains foreground. Keep the last external editor;
            # the next external foreground process will still trigger a real
            # context switch.
            logger.debug(
                "Ignoring G-Coach-owned UI focus (foreground_hwnd=%r, "
                "foreground_pid=%r, uia_control_type=%r, uia_control_name=%r); "
                "retaining the last external editing target.",
                snapshot.metadata.get("foreground_hwnd"),
                snapshot.metadata.get("foreground_process_id"),
                snapshot.metadata.get("uia_control_type"),
                snapshot.metadata.get("uia_control_name"),
            )
            return self.get_state()

        # UIA focus can move between child elements while the foreground app
        # remains unchanged. Track the real foreground process separately and
        # invalidate the snapshot if that process genuinely changes.
        with self._lock:
            previous_metadata = dict(self._state.metadata)
            previous_control_id = self._state.control_id
        previous_foreground_identity = previous_metadata.get("foreground_identity")
        current_foreground_identity = snapshot.metadata.get("foreground_identity")
        foreground_changed = bool(
            previous_foreground_identity
            and current_foreground_identity
            and previous_foreground_identity != current_foreground_identity
        )
        if snapshot.control_id != previous_control_id or foreground_changed:
            logger.info(
                "Focus identity changed: previous foreground=(hwnd=%r, pid=%r, exe=%r), "
                "current foreground=(hwnd=%r, pid=%r, exe=%r), "
                "focused UIA=(pid=%r, hwnd=%r, type=%r, name=%r, automation_id=%r).",
                previous_metadata.get("foreground_hwnd"),
                previous_metadata.get("foreground_process_id"),
                previous_metadata.get("foreground_app_name"),
                snapshot.metadata.get("foreground_hwnd"),
                snapshot.metadata.get("foreground_process_id"),
                snapshot.metadata.get("foreground_app_name"),
                snapshot.process_id,
                snapshot.metadata.get("hwnd"),
                snapshot.control_type,
                snapshot.metadata.get("control_name"),
                snapshot.metadata.get("automation_id"),
            )

        if snapshot.status == "unsupported" or not snapshot.is_editable:
            with self._lock:
                # Treat an unsupported target as a context boundary. Invalidate
                # in-flight analysis, discard stale text/findings, and remember
                # the unavailable control so returning to the same editor is
                # detected as a fresh context even when its text is unchanged.
                if (
                    self._state.status != "unsupported"
                    or snapshot.control_id != self._last_control_id
                    or foreground_changed
                    or bool(self._last_captured_text)
                ):
                    self._current_generation += 1
                self._capture_failed = False
                self._last_control_id = snapshot.control_id
                self._last_captured_text = ""
                self._last_change_time = time.time()
                self._state.generation = self._current_generation
                self._state.text = ""
                self._state.timestamp = self._last_change_time
                self._state.status = "unsupported"
                self._state.app_name = snapshot.app_name
                self._state.control_info = snapshot.control_info
                self._state.control_id = snapshot.control_id
                self._state.process_id = snapshot.process_id
                self._state.control_type = snapshot.control_type
                self._state.error_message = snapshot.error_message or "Control is unsupported or not editable."
                self._state.findings = []
                self._state.metadata = dict(snapshot.metadata)
            return self.get_state()

        current_control_id = snapshot.control_id
        current_text = snapshot.text
        now = time.time()

        with self._lock:
            recovered_from_capture_error = self._capture_failed
            self._capture_failed = False
            # Returning after a capture failure or unsupported target is a new
            # context even if the same control ID and text reappear. An
            # analysis error alone does not invalidate the captured context.
            control_changed = (
                current_control_id != self._last_control_id
                or foreground_changed
                or self._state.status == "unsupported"
                or recovered_from_capture_error
            )
            text_changed = (current_text != self._last_captured_text) or control_changed

            if control_changed:
                # 聚焦控件发生变化（切换应用/控件）：立即隔离并重置状态，防止混淆不同控件的文本
                self._last_control_id = current_control_id
                self._current_generation += 1
                self._last_captured_text = current_text
                self._last_change_time = now
                self._state.generation = self._current_generation
                self._state.text = current_text
                self._state.app_name = snapshot.app_name
                self._state.control_info = snapshot.control_info
                self._state.control_id = current_control_id
                self._state.process_id = snapshot.process_id
                self._state.control_type = snapshot.control_type
                self._state.findings = []  # 隔离：切换控件时清空旧 findings
                self._state.timestamp = now
                self._state.metadata = dict(snapshot.metadata)
                self._state.error_message = None
                if not current_text.strip():
                    self._state.status = "ready"
                else:
                    self._state.status = "waiting"
                logger.debug(f"Control changed to {current_control_id}. New generation: {self._current_generation}")
                return self.get_state()

            if text_changed:
                self._current_generation += 1
                self._last_captured_text = current_text
                self._last_change_time = now
                self._state.generation = self._current_generation
                self._state.text = current_text
                self._state.app_name = snapshot.app_name
                self._state.control_info = snapshot.control_info
                self._state.control_id = current_control_id
                self._state.process_id = snapshot.process_id
                self._state.control_type = snapshot.control_type
                self._state.timestamp = now
                self._state.metadata = dict(snapshot.metadata)
                self._state.error_message = None
                if not current_text.strip():
                    self._state.status = "ready"
                    self._state.findings = []  # 空文本立即清空 findings
                else:
                    self._state.status = "waiting"
                logger.debug(f"Text changed in control {current_control_id}. New generation: {self._current_generation}")
                return self.get_state()

            # 文本未变：检查防抖期是否已过
            if self._state.status == "waiting":
                elapsed = now - self._last_change_time
                if elapsed >= self.debounce_interval:
                    # 防抖期已过，且文本处于静止状态：启动分析
                    gen_to_analyze = self._current_generation
                    text_to_analyze = self._last_captured_text
                    self._state.status = "analyzing"
                    self._analyzing_generation = gen_to_analyze

                    # 在后台线程中异步执行分析，避免阻塞监控循环
                    worker = threading.Thread(
                        target=self._run_analysis_async,
                        args=(gen_to_analyze, text_to_analyze),
                        daemon=True,
                    )
                    worker.start()

        return self.get_state()

    def _run_analysis_async(self, target_generation: int, text: str) -> None:
        """异步执行分析管道与消解层，并应用过期结果保护（Stale Result Protection）"""
        try:
            raw_findings = self.pipeline.analyze(text)
            resolved_findings = self.resolver.resolve(raw_findings)
        except Exception as e:
            logger.error(f"Error during async analysis for gen {target_generation}: {e}", exc_info=True)
            with self._lock:
                # 如果当前代数仍然是这个代数，则设置错误状态
                if self._current_generation == target_generation:
                    self._state.status = "error"
                    self._state.error_message = str(e)
            return

        with self._lock:
            # Stale Result Protection:
            # 严格检查目标代数是否仍等于当前最新的全局代数。
            if target_generation != self._current_generation:
                logger.debug(f"Discarding stale analysis result for gen {target_generation} (current gen: {self._current_generation})")
                return

            # 发布最新有效结果
            self._state.generation = target_generation
            self._state.text = text
            self._state.findings = resolved_findings
            self._state.status = "ready"
            self._state.error_message = None
            self._state.timestamp = time.time()
            logger.debug(f"Published analysis result for gen {target_generation} with {len(resolved_findings)} findings.")
