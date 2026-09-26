"""
实时文本监控器、防抖动与过期结果保护 (Live Text Monitor & Stale Result Protection) - Phase 5
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

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
        self._is_running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # 当前发布状态
        self._state = MonitorState(status="idle")

        # 正在分析或已完成的最新状态追踪
        self._analyzing_generation = 0

    def start(self) -> None:
        """启动实时监控线程"""
        with self._lock:
            if self._is_running:
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
            logger.info("LiveTextMonitor stopped.")

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
                control_type=self._state.control_type,
                error_message=self._state.error_message,
                metadata=dict(self._state.metadata),
            )

    def trigger_check(self) -> Optional[MonitorState]:
        """手动触发一次文本捕获和检查（主要用于单次测试或事件驱动触发）"""
        return self._poll_once()

    def _monitor_loop(self) -> None:
        """后台监控与防抖循环"""
        import os
        while True:
            with self._lock:
                if not self._is_running:
                    break
            
            isolation_mode = os.environ.get("GCOACH_POPUP_ISOLATION", "").strip().lower()
            if isolation_mode == "popup":
                # 隔离测试 1：POPUP-ONLY，跳过所有 UIA monitor 轮询
                time.sleep(0.1)
                continue

            if isolation_mode == "monitor":
                # 隔离测试 2：MONITOR-ONLY，正常执行 UIA 轮询并打印日志
                print("[Phase8E isolation monitor] polling UIA focus...")

            self._poll_once()
            time.sleep(self.poll_interval)

    def _poll_once(self) -> Optional[MonitorState]:
        """单次轮询：获取文本、检查变化、管理防抖并触发分析"""
        try:
            snapshot = self.text_source.get_current_text()
        except Exception as e:
            logger.error(f"Error getting text from source: {e}", exc_info=True)
            with self._lock:
                self._state.status = "error"
                self._state.error_message = str(e)
            return self.get_state()

        if snapshot.status == "unsupported" or not snapshot.is_editable:
            with self._lock:
                self._state.status = "unsupported"
                self._state.app_name = snapshot.app_name
                self._state.control_info = snapshot.control_info
                self._state.control_id = snapshot.control_id
                self._state.control_type = snapshot.control_type
                self._state.error_message = snapshot.error_message or "Control is unsupported or not editable."
                self._state.findings = []
                self._state.metadata = dict(snapshot.metadata)
            return self.get_state()

        current_control_id = snapshot.control_id
        current_text = snapshot.text
        now = time.time()

        with self._lock:
            control_changed = (current_control_id != self._last_control_id)
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
                self._state.control_type = snapshot.control_type
                self._state.findings = []  # 隔离：切换控件时清空旧 findings
                self._state.timestamp = now
                self._state.metadata = dict(snapshot.metadata)
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
                self._state.control_type = snapshot.control_type
                self._state.timestamp = now
                self._state.metadata = dict(snapshot.metadata)
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
            self._state.timestamp = time.time()
            logger.debug(f"Published analysis result for gen {target_generation} with {len(resolved_findings)} findings.")
