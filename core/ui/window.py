"""
G-Coach Desktop Window (PyQt6) - Phase 6
使用 PyQt6 构建的 G-Coach 桌面主窗口。订阅 LiveTextMonitor 状态，
展示监控状态、应用信息、当前文本快照、发现列表（支持合并与冲突展示）及详细属性面板。
严格遵守只读检查和线程安全原则，绝不自动修改用户文本。
"""

import sys
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

try:
    from PyQt6.QtCore import Qt, QTimer, QPoint
    from PyQt6.QtWidgets import (
        QApplication,
        QMainWindow,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QTextEdit,
        QListWidget,
        QListWidgetItem,
        QSplitter,
        QGroupBox,
        QMessageBox,
    )
    PYQT_AVAILABLE = True
except (ImportError, OSError) as e:
    logger.warning(f"PyQt6 or system GUI libraries (e.g. libEGL) not available: {e}. GUI window disabled.")
    PYQT_AVAILABLE = False
    QMainWindow = object  # type: ignore
    QMessageBox = object  # type: ignore

from core.monitoring import LiveTextMonitor, MonitorState
from core.analysis import Finding
from core.correction import CorrectionController
from core.correction.target import CorrectionTarget
from core.correction.engine import BackgroundCorrectionEngine
from core.dictionary import is_dictionary_candidate, PersonalDictionary
from .floating_correction import FloatingCorrectionPopup, calculate_popup_position
from .presenter import UIPresenter


class GCoachWindow(QMainWindow if PYQT_AVAILABLE else object):
    """G-Coach 桌面主窗口"""

    def __init__(self, monitor: LiveTextMonitor):
        if not PYQT_AVAILABLE:
            raise RuntimeError("PyQt6 is not available in this environment (headless container).")
        super().__init__()
        self.monitor = monitor
        self.current_findings: List[Finding] = []
        self.correction_controller = CorrectionController()
        self.active_popup: Optional[FloatingCorrectionPopup] = None
        self.last_popup_finding_id: Optional[str] = None
        self.last_popup_finding_signature: Optional[Tuple[str, str, str, int, int]] = None
        # Ignore is scoped to one exact control/text snapshot. The signature deliberately
        # excludes Finding.id because analysis engines may recreate IDs on every run.
        self._ignored_context = None
        self._ignored_finding_signatures = set()
        self._ignore_context_ready = False
        self._last_monitor_app_name = ""
        self._last_monitor_status = ""
        self._last_monitor_foreground_key = None

        self.setWindowTitle("G-Coach - Personal Writing Assistant")
        # Preserve room for both panes and the action row at smaller window sizes.
        self.setMinimumSize(760, 560)
        self.resize(980, 720)

        self._init_ui()

        # 设置定时器用于定期从 monitor 获取最新状态（主线程安全轮询）
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(100)  # 每 100ms 刷新一次 UI
        self.update_timer.timeout.connect(self._poll_monitor_state)
        self.update_timer.start()

        # 隔离测试 1：POPUP-ONLY 如果环境变量设置为 popup，在窗口打开后 500ms 自动注入确定性 Finding 并测试弹窗渲染
        import os
        if os.environ.get("GCOACH_POPUP_ISOLATION", "").strip().lower() == "popup":
            QTimer.singleShot(500, self._inject_test_popup_isolation)

    def _init_ui(self):
        """初始化 UI 布局与控件"""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        self.setStyleSheet("""
            QMainWindow { background-color: #F3F5F8; }
            QGroupBox {
                background-color: #FFFFFF;
                border: 1px solid #DDE2EA;
                border-radius: 8px;
                margin-top: 12px;
                padding: 10px;
                color: #253247;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
            }
            QTextEdit, QListWidget {
                background-color: #FFFFFF;
                border: 1px solid #DDE2EA;
                border-radius: 6px;
                padding: 6px;
                selection-background-color: #DBEAFE;
                selection-color: #1D4ED8;
            }
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #D5DBE5;
                border-radius: 6px;
                padding: 7px 12px;
                color: #253247;
            }
            QPushButton:hover {
                background-color: #EFF6FF;
                border-color: #93BDF5;
            }
            QPushButton:disabled {
                background-color: #F1F3F6;
                color: #9AA3B2;
                border-color: #E1E5EB;
            }
            QPushButton#startMonitoringButton {
                background-color: #2563EB;
                border-color: #2563EB;
                color: #FFFFFF;
                font-weight: 600;
            }
            QPushButton#startMonitoringButton:hover {
                background-color: #1D4ED8;
                border-color: #1D4ED8;
            }
            QSplitter::handle { background-color: #E1E5EC; }
            QSplitter::handle:hover { background-color: #93BDF5; }
            QStatusBar {
                background-color: #F3F5F8;
                border-top: 1px solid #DDE2EA;
                color: #64748B;
            }
        """)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # 1. 顶部 Header 与监控控制区
        header_layout = QHBoxLayout()
        
        title_label = QLabel("G-Coach", self)
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.status_label = QLabel("Status: Idle", self)
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e67e22;")
        header_layout.addWidget(self.status_label)

        self.app_info_label = QLabel("Application: Unknown", self)
        self.app_info_label.setStyleSheet("font-size: 13px; color: #7f8c8d;")
        header_layout.addWidget(self.app_info_label)

        header_layout.addStretch()

        self.start_btn = QPushButton("Start Monitoring", self)
        self.start_btn.clicked.connect(self._on_start_clicked)
        header_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop Monitoring", self)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        self.stop_btn.setEnabled(False)
        header_layout.addWidget(self.stop_btn)

        main_layout.addLayout(header_layout)

        # 2. 主体分栏：左侧为文本快照与发现列表，右侧为详细属性/冲突面板
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setObjectName("mainSplitter")
        splitter.setHandleWidth(7)
        splitter.setChildrenCollapsible(False)
        main_layout.addWidget(splitter, stretch=1)

        # 左侧容器
        left_widget = QWidget(self)
        left_widget.setMinimumWidth(300)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 2.1 当前文本快照框
        text_group = QGroupBox("Captured Text Snapshot (Read-Only)", self)
        text_layout = QVBoxLayout(text_group)
        self.text_snapshot_edit = QTextEdit(self)
        self.text_snapshot_edit.setReadOnly(True)
        self.text_snapshot_edit.setPlaceholderText("Captured text snapshot will appear here...")
        text_layout.addWidget(self.text_snapshot_edit)
        left_layout.addWidget(text_group, stretch=1)

        # 2.2 发现列表（Findings）
        findings_group = QGroupBox("Findings & Suggestions", self)
        findings_layout = QVBoxLayout(findings_group)
        self.findings_list_widget = QListWidget(self)
        self.findings_list_widget.itemSelectionChanged.connect(self._on_finding_selected)
        findings_layout.addWidget(self.findings_list_widget)
        left_layout.addWidget(findings_group, stretch=1)

        splitter.addWidget(left_widget)

        # 右侧容器：详细信息与冲突面板
        right_widget = QWidget(self)
        right_widget.setMinimumWidth(400)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        details_group = QGroupBox("Finding Details & Conflicts", self)
        details_layout = QVBoxLayout(details_group)

        self.details_text_edit = QTextEdit(self)
        self.details_text_edit.setReadOnly(True)
        self.details_text_edit.setPlaceholderText("Select a finding on the left to inspect details, metadata, confidence, or multi-engine conflicts.")
        details_layout.addWidget(self.details_text_edit)

        # Phase 7: Interactive Correction Actions (Accept / Add to Dictionary / Ignore)
        actions_layout = QHBoxLayout()
        self.btn_accept = QPushButton("Accept Correction", self)
        self.btn_accept.setEnabled(False)
        self.btn_accept.clicked.connect(self._on_accept_clicked)
        actions_layout.addWidget(self.btn_accept)

        self.btn_add_to_dict = QPushButton("Add to Dictionary", self)
        self.btn_add_to_dict.setEnabled(False)
        self.btn_add_to_dict.clicked.connect(self._on_add_to_dict_clicked)
        actions_layout.addWidget(self.btn_add_to_dict)

        self.btn_ignore = QPushButton("Ignore Finding", self)
        self.btn_ignore.setEnabled(False)
        self.btn_ignore.clicked.connect(self._on_ignore_clicked)
        actions_layout.addWidget(self.btn_ignore)

        details_layout.addLayout(actions_layout)

        right_layout.addWidget(details_group)
        splitter.addWidget(right_widget)

        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([500, 420])
        self.start_btn.setObjectName("startMonitoringButton")

        # 3. 底部状态栏
        self.statusBar().showMessage("Ready. No text modifications will be performed.")

    def _on_start_clicked(self):
        """点击开始监控"""
        self.monitor.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.statusBar().showMessage("Monitoring started.")

    def _on_stop_clicked(self):
        """点击停止监控"""
        self.monitor.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.statusBar().showMessage("Monitoring stopped.")

    def _poll_monitor_state(self):
        """轮询从 monitor 获取最新状态并在 UI 线程上刷新"""
        import os
        isolation_mode = os.environ.get("GCOACH_POPUP_ISOLATION", "").strip().lower()
        if isolation_mode == "popup":
            # 隔离测试 1：POPUP-ONLY（不启动监控，直接注入确定性 Finding 并测试弹窗渲染）
            return

        try:
            state = self.monitor.get_state()
            self._update_ui_from_state(state)
        except Exception as e:
            logger.error(f"Error polling monitor state: {e}", exc_info=True)

    def _update_ui_from_state(self, state: MonitorState):
        """根据 MonitorState 刷新所有 UI 元素"""
        # Reset ignore suppression as soon as the monitored document or control changes,
        # including while the monitor is still waiting for a fresh analysis result.
        self._update_ignored_context(state)
        summary = UIPresenter.format_state_summary(state)

        # 更新状态标签
        self.status_label.setText(f"Status: {summary['status_text']}")
        self.app_info_label.setText(summary['app_info'])

        # 如果状态为错误，显示错误信息
        if state.status == "error" and state.error_message:
            self.statusBar().showMessage(f"Error: {state.error_message}")
        elif state.status == "unsupported":
            self.statusBar().showMessage(f"Unsupported control/application: {state.app_name}")

        # 更新文本快照（仅当文本发生变化时重设以保持光标舒适）
        if self.text_snapshot_edit.toPlainText() != summary['text']:
            self.text_snapshot_edit.setPlainText(summary['text'])

        # Phase 6.x: 如果处于等待或分析中状态，在状态栏提示正在检查，避免用户误认旧结果
        if summary['is_pending']:
            self.statusBar().showMessage(summary['pending_message'])
        else:
            # 更新 Findings 列表
            new_findings = summary['findings']
            if new_findings != self.current_findings:
                self.current_findings = new_findings
                self.findings_list_widget.clear()

                # 检查是否有冲突
                groups = UIPresenter.group_findings_by_text(new_findings)

                for finding in new_findings:
                    summary_line = UIPresenter.format_finding_summary(finding)
                    
                    # 如果同一原始文本存在多个引擎的建议（冲突），加上标记
                    if len(groups.get(finding.original, [])) > 1:
                        summary_line = f"⚠️ [CONFLICT] {summary_line}"

                    item = QListWidgetItem(summary_line)
                    item.setData(Qt.ItemDataRole.UserRole, finding)
                    self.findings_list_widget.addItem(item)

            # 无论 findings 是否与上一代对象列表完全一致，一旦进入 ready 状态，状态栏必须刷新显示 Ready
            if summary['has_conflicts']:
                self.statusBar().showMessage(f"Found {len(new_findings)} findings with multi-engine conflicts.")
            else:
                self.statusBar().showMessage(f"Found {len(new_findings)} findings (Ready).")

            # Phase 8E: 管理和同步浮动纠正弹窗 (Floating Correction Popup)
            self._sync_floating_popup(new_findings, state)

    def _on_finding_selected(self):
        """当用户在列表中选择某条 Finding 时展示其详情与冲突分析"""
        selected_items = self.findings_list_widget.selectedItems()
        if not selected_items:
            self.details_text_edit.clear()
            self.btn_accept.setEnabled(False)
            self.btn_add_to_dict.setEnabled(False)
            self.btn_ignore.setEnabled(False)
            return

        item = selected_items[0]
        finding: Finding = item.data(Qt.ItemDataRole.UserRole)
        if not finding:
            return

        is_cand = is_dictionary_candidate(finding)
        has_replacement = bool(finding.replacement and finding.replacement.strip())
        # A spelling suggestion may be accepted or added to the personal
        # dictionary; these actions are alternatives, not mutually exclusive.
        self.btn_add_to_dict.setEnabled(is_cand)
        self.btn_accept.setEnabled(has_replacement)
        self.btn_ignore.setEnabled(True)

        details = UIPresenter.format_finding_details(finding)
        
        # 检查是否有关联冲突（相同 original 文本的其他 findings）
        conflicting_findings = [
            f for f in self.current_findings
            if f.original == finding.original and f.source != finding.source
        ]

        details_str = "=== Finding Details ===\n"
        for k, v in details.items():
            details_str += f"{k}: {v}\n"

        if conflicting_findings:
            details_str += "\n=== ⚠️ Conflicting Suggestions for \"" + finding.original + "\" ===\n"
            details_str += f"- {finding.source}: {finding.original} → {finding.replacement}\n"
            for cf in conflicting_findings:
                details_str += f"- {cf.source}: {cf.original} → {cf.replacement}\n"
            details_str += "\n(Note: G-Coach presents alternative suggestions without selecting a winner.)"

        self.details_text_edit.setPlainText(details_str)

    def _on_accept_clicked(self):
        """用户点击接受修正按钮"""
        selected_items = self.findings_list_widget.selectedItems()
        if not selected_items:
            return
        item = selected_items[0]
        finding: Finding = item.data(Qt.ItemDataRole.UserRole)
        if not finding:
            return

        current_text = self.text_snapshot_edit.toPlainText()
        result = self.correction_controller.apply_acceptance(
            current_text, finding, all_findings=self.current_findings
        )

        if result.success:
            self.statusBar().showMessage(result.message)
            if hasattr(self.monitor.text_source, "set_text"):
                self.monitor.text_source.set_text(result.new_text)
                self.monitor.trigger_check()
            else:
                self.text_snapshot_edit.setPlainText(result.new_text)
            
            # 移除已接受的项
            row = self.findings_list_widget.row(item)
            self.findings_list_widget.takeItem(row)
            self.details_text_edit.clear()
            self.btn_accept.setEnabled(False)
            self.btn_ignore.setEnabled(False)
        else:
            QMessageBox.warning(self, "Correction Failed", result.error_message or "Could not apply correction.")
            self.statusBar().showMessage(f"Correction failed: {result.error_message}")

    def _on_ignore_clicked(self):
        """用户点击忽略/丢弃 Finding 按钮"""
        selected_items = self.findings_list_widget.selectedItems()
        if not selected_items:
            return
        item = selected_items[0]
        finding: Finding = item.data(Qt.ItemDataRole.UserRole)
        if not finding:
            return

        self._handle_popup_ignore(finding)

    @staticmethod
    def _ignore_signature(finding: Finding):
        """Return a stable identity for a finding, independent of its generated ID."""
        return (
            finding.source,
            finding.category,
            finding.original,
            finding.replacement,
            finding.start,
            finding.end,
        )

    def _update_ignored_context(self, state: MonitorState):
        """Reset ignored findings when the document text or target control changes."""
        metadata = getattr(state, "metadata", {}) or {}
        if metadata.get("foreground_is_self"):
            # Defensive counterpart to LiveTextMonitor's self-window filter:
            # never dismiss a document popup merely because a G-Coach-owned
            # dropdown or other transient window received foreground focus.
            return

        foreground_key = GCoachWindow._foreground_application_key(state)
        previous_foreground_key = getattr(self, "_last_monitor_foreground_key", None)
        foreground_changed = bool(
            previous_foreground_key is not None
            and foreground_key is not None
            and previous_foreground_key != foreground_key
        )

        # Popup lifetime follows the actual foreground application, not the
        # currently focused UIA child element. UIA may report EditControl on
        # one poll and ListItemControl on the next without the user leaving the
        # editor; that must not dismiss the correction popup.
        if foreground_changed and getattr(self, "active_popup", None):
            logger.warning(
                "Closing floating correction popup because the foreground application changed "
                "(previous_foreground=%r, current_foreground=%r, foreground_hwnd=%r, "
                "foreground_pid=%r, foreground_exe=%r, uia_control_type=%r).",
                previous_foreground_key,
                foreground_key,
                metadata.get("foreground_hwnd"),
                metadata.get("foreground_process_id"),
                metadata.get("foreground_app_name"),
                state.control_type,
            )
            self.active_popup.close()
            self.active_popup = None
            self.last_popup_finding_id = None
            self.last_popup_finding_signature = None
            self.last_popup_findings_count = 0
            self.last_popup_index = 0

        if foreground_key is not None:
            self._last_monitor_foreground_key = foreground_key

        if state.control_id:
            control_key = ("id", state.control_id)
        else:
            # Some text sources cannot provide a stable control ID. Use their available
            # identifying metadata rather than accidentally sharing suppression globally.
            control_key = (
                "fallback",
                state.app_name,
                state.control_info,
                state.control_type,
            )
        context = (control_key, state.text)
        previous_context = getattr(self, "_ignored_context", None)

        if previous_context != context:
            # A changed document buffer invalidates the popup's original text
            # range and correction target. A UIA child/control identity change
            # alone does not: transient child focus must not dismiss it.
            text_changed = (
                previous_context is not None
                and len(previous_context) > 1
                and previous_context[1] != state.text
            )
            if text_changed and getattr(self, "active_popup", None):
                logger.info("Closing floating correction popup because the document text changed.")
                self.active_popup.close()
                self.active_popup = None
                self.last_popup_finding_id = None
                self.last_popup_finding_signature = None
                self.last_popup_findings_count = 0
                self.last_popup_index = 0

            self._ignored_context = context
            self._ignored_finding_signatures = set()
            self._ignore_context_ready = state.status == "ready"
        elif state.status == "ready":
            # A new analysis result for this context is now available.
            self._ignore_context_ready = True

        self._last_monitor_app_name = state.app_name
        self._last_monitor_status = state.status

    @staticmethod
    def _foreground_application_key(state: MonitorState):
        """Return a stable foreground-process key, excluding UIA child identity."""
        metadata = getattr(state, "metadata", {}) or {}
        if "foreground_identity" in metadata:
            identity = metadata.get("foreground_identity")
            if identity:
                return ("foreground", str(identity).casefold())

        # Explicit foreground metadata means this is a real Windows capture.
        # If identity lookup failed, do not fall back to a UIA ControlType.
        if "foreground_process_id" in metadata or "foreground_app_name" in metadata:
            try:
                process_id = int(metadata.get("foreground_process_id") or 0)
            except (TypeError, ValueError):
                process_id = 0
            if process_id:
                return ("pid", process_id)
            executable = str(metadata.get("foreground_app_name") or "").strip()
            if executable:
                executable = executable.replace("/", "\\").rsplit("\\", 1)[-1]
                return ("exe", executable.casefold())
            return None

        # Non-Windows/test sources do not expose foreground metadata. Their
        # app_name remains the only available application-level identifier.
        app_name = str(getattr(state, "app_name", "") or "").strip()
        if not app_name:
            return None
        app_name = app_name.replace("/", "\\").rsplit("\\", 1)[-1]
        return ("app", app_name.casefold())

    def _filter_ignored_findings(self, findings: List[Finding], state: MonitorState) -> List[Finding]:
        """Exclude findings ignored for this unchanged control and text snapshot."""
        self._update_ignored_context(state)
        ignored = getattr(self, "_ignored_finding_signatures", set())
        return [finding for finding in findings if self._ignore_signature(finding) not in ignored]

    def _execute_uia_operation(self, callback, *args, default=None):
        """Run UIA work on the monitor's COM-owning thread, never on the Qt thread."""
        runner = getattr(getattr(self, "monitor", None), "run_on_monitor_thread", None)
        if callable(runner):
            if not getattr(self.monitor, "is_running", False):
                logger.warning("Skipped UI Automation operation because the monitor thread is not running.")
                return default
            try:
                return runner(callback, *args)
            except Exception as exc:
                logger.error("Monitor-thread UI Automation operation failed: %s", exc, exc_info=True)
                return default

        # Lightweight test doubles and non-monitor integrations do not own a
        # UIA thread; retain their direct callback behavior for unit testing.
        try:
            return callback(*args)
        except Exception as exc:
            logger.error("UI Automation operation failed: %s", exc, exc_info=True)
            return default

    def _sync_floating_popup(self, findings: List[Finding], state: MonitorState):
        """根据当前 findings 和 monitor state 同步浮动纠正弹窗的显示与隐藏（支持多发现导航）"""
        visible_findings = self._filter_ignored_findings(findings, state)
        if not visible_findings:
            if self.active_popup:
                logger.info(
                    "Closing floating correction popup because no visible findings remain "
                    "(status=%s, app=%r, control_type=%s, source_finding_count=%s).",
                    state.status,
                    state.app_name,
                    state.control_type,
                    len(findings),
                )
                self.active_popup.close()
            self.active_popup = None
            self.last_popup_finding_id = None
            self.last_popup_finding_signature = None
            self.last_popup_findings_count = 0
            self.last_popup_index = 0
            return

        current_findings_count = len(visible_findings)
        active_index = getattr(self, "last_popup_index", 0)
        if active_index >= current_findings_count:
            active_index = current_findings_count - 1

        active_finding = visible_findings[active_index]
        active_signature = (
            active_finding.source,
            active_finding.original,
            active_finding.replacement,
            active_finding.start,
            active_finding.end,
            current_findings_count,
            active_index
        )

        if self.active_popup is None or getattr(self, "last_popup_finding_signature", None) != active_signature:
            if self.active_popup:
                if getattr(self, "last_popup_findings_count", 0) == current_findings_count and self.active_popup.findings == visible_findings:
                    self.active_popup.set_findings(visible_findings, active_index)
                    self.last_popup_finding_signature = active_signature
                    return

                logger.info(
                    "Recreating floating correction popup because the visible finding set changed "
                    "(previous_count=%s, current_count=%s).",
                    getattr(self, "last_popup_findings_count", 0),
                    current_findings_count,
                )
                self.active_popup.close()
                self.active_popup = None

            import os
            test_mode = os.environ.get("GCOACH_POPUP_TEST", "").strip().upper()
            popup_parent = self if test_mode == "Q-PARENT" else None
            target = CorrectionTarget.from_snapshot(state)
            
            def handle_navigate(new_idx: int):
                self.last_popup_index = new_idx
                nav_finding = visible_findings[new_idx] if 0 <= new_idx < len(visible_findings) else visible_findings[0]
                self.last_popup_finding_signature = (
                    nav_finding.source,
                    nav_finding.original,
                    nav_finding.replacement,
                    nav_finding.start,
                    nav_finding.end,
                    len(visible_findings),
                    new_idx
                )
                logger.debug("Correction popup navigated to finding index %s.", new_idx)

            self.active_popup = FloatingCorrectionPopup(
                findings=visible_findings,
                current_index=active_index,
                target=target,
                on_accept=self._handle_popup_accept,
                on_ignore=self._handle_popup_ignore,
                on_navigate=handle_navigate,
                on_add_to_dict=self._handle_popup_add_to_dict,
                parent=popup_parent,
                on_accept_all=getattr(self, "_handle_popup_accept_all", None),
            )
            print(f"[Phase8E diagnostic] Multi-finding popup constructed (total: {current_findings_count}, index: {active_index})")
            self.last_popup_finding_id = active_finding.id
            self.last_popup_finding_signature = active_signature
            self.last_popup_findings_count = current_findings_count
            self.last_popup_index = active_index

            # Prefer the exact UIA range geometry so the popup appears beside
            # the text being reviewed, rather than beside the G-Coach window.
            anchor_rect = self._execute_uia_operation(
                BackgroundCorrectionEngine.get_finding_screen_rect,
                target,
                active_finding,
                default=None,
            )
            if anchor_rect is None:
                anchor_rect = GCoachWindow._get_target_window_rect(target)

            if anchor_rect is None:
                main_pos = self.pos()
                anchor_rect = (main_pos.x(), main_pos.y(), self.width(), self.height())

            anchor_x, anchor_y, anchor_width, anchor_height = anchor_rect
            screen_point = QPoint(
                anchor_x + max(anchor_width, 1) // 2,
                anchor_y + max(anchor_height, 1) // 2,
            )
            screen = QApplication.screenAt(screen_point)
            if screen is None and hasattr(self, "screen"):
                screen = self.screen()
            if screen is None:
                screen = QApplication.primaryScreen()
            screen_geom = screen.availableGeometry() if screen else type("Rect", (), {"x": lambda: 0, "y": lambda: 0, "width": lambda: 1920, "height": lambda: 1080})()

            popup_size = self.active_popup.sizeHint()
            p_w = max(popup_size.width(), 260)
            p_h = max(popup_size.height(), 120)

            popup_x, popup_y = calculate_popup_position(
                anchor_x,
                anchor_y,
                anchor_width,
                anchor_height,
                p_w,
                p_h,
                screen_geom.x(),
                screen_geom.y(),
                screen_geom.width(),
                screen_geom.height(),
            )
            self.active_popup.show_at(popup_x, popup_y)
        else:
            if self.active_popup:
                self.active_popup.set_findings(visible_findings, active_index)

    @staticmethod
    def _get_target_window_rect(target: CorrectionTarget):
        """Return the target control's screen rectangle when UIA range geometry is unavailable."""
        if not getattr(target, "hwnd", 0):
            return None
        try:
            import win32gui

            left, top, right, bottom = win32gui.GetWindowRect(int(target.hwnd))
            if right > left and bottom > top:
                return (left, top, right - left, bottom - top)
        except Exception as exc:
            logger.debug("Unable to resolve target control window bounds: %s", exc)
        return None

    def _inject_test_popup_isolation(self):
        """隔离测试 1：POPUP-ONLY 确定性注入 Finding 并调用 _sync_floating_popup"""
        print("[Phase8E isolation] 1. creating finding")
        finding = Finding(
            source="Harper",
            category="grammar",
            message="Test grammar error",
            original="was",
            replacement="were",
            start=13,
            end=16,
        )
        state = MonitorState(
            text="The students was happy.",
            status="ready",
            control_id="isolation-ctrl-1",
            app_name="IsolationApp",
        )
        print("[Phase8E isolation] 2. calling _sync_floating_popup")
        self._sync_floating_popup([finding], state)
        print("[Phase8E isolation] injection completed")

    def _handle_popup_accept(self, finding: Finding, target: CorrectionTarget):
        """处理浮动弹窗的 Accept 点击：通过 BackgroundCorrectionEngine 无焦点直接修改目标控件"""
        attempt = self._execute_uia_operation(
            BackgroundCorrectionEngine.apply_correction_to_target_detailed,
            target,
            finding,
            default=None,
        )
        success = bool(attempt and attempt.success)
        logger.info("Floating correction completed (success=%s).", success)
        if success:
            self.statusBar().showMessage(f"Successfully applied background correction: {finding.original} → {finding.replacement}")
            finding.status = "accepted"
            if hasattr(self.monitor.text_source, "set_text"):
                # 如果是 Mock Text Source，同时更新其内部文本并触发检查
                current_t = getattr(self.monitor.text_source, "text", "")
                if current_t:
                    new_t = current_t[:finding.start] + finding.replacement + current_t[finding.end:]
                    self.monitor.text_source.set_text(new_t)
            # Re-capture the edited document immediately. The monitor will
            # perform one fresh analysis for this new snapshot as before.
            if self.monitor and hasattr(self.monitor, "trigger_check"):
                self.monitor.trigger_check()
        else:
            reason = getattr(attempt, "reason", "") or "The target editor rejected the correction."
            message = f"Could not correct '{finding.original}'.\n\n{reason}"
            QMessageBox.warning(self, "Correction Failed", message)
            self.statusBar().showMessage(f"Correction failed: {reason}")

        if self.active_popup:
            self.active_popup.close()
            self.active_popup = None
            self.last_popup_finding_id = None
            self.last_popup_finding_signature = None

    def _handle_popup_accept_all(self, findings: List[Finding], target: CorrectionTarget):
        """Apply independent popup findings in one verified pass, then re-analyse once."""
        result = self._execute_uia_operation(
            BackgroundCorrectionEngine.apply_corrections_to_target,
            target,
            findings,
            default=None,
        )
        applied = int(getattr(result, "applied_count", 0) or 0)
        skipped = int(getattr(result, "skipped_count", len(findings)) or 0)
        reason = getattr(result, "reason", "") or ""

        if applied:
            summary = f"Applied {applied} corrections in one pass."
            if skipped:
                summary += f" {skipped} suggestions were skipped because they were conflicting, overlapping, or stale."
            if reason:
                summary += f" Batch stopped safely: {reason}"
            self.statusBar().showMessage(summary)
            # The edits are already verified. Trigger one capture so the monitor
            # analyses the final document once rather than after every edit.
            if self.monitor and hasattr(self.monitor, "trigger_check"):
                self.monitor.trigger_check()
        else:
            message = reason or "No independent suggestions could be safely applied."
            QMessageBox.warning(self, "Batch Correction", message)
            self.statusBar().showMessage(f"Batch correction not applied: {message}")

        if self.active_popup:
            self.active_popup.close()
            self.active_popup = None
            self.last_popup_finding_id = None
            self.last_popup_finding_signature = None
            self.last_popup_findings_count = 0

    def _handle_popup_ignore(self, finding: Finding):
        """处理浮动弹窗的 Ignore 点击"""
        self.correction_controller.mark_ignored(finding)
        # Do not carry a stale finding forward when the monitor has noticed a new
        # document/control but has not published its analysis result yet.
        if getattr(self, "_ignore_context_ready", False):
            self._ignored_finding_signatures.add(self._ignore_signature(finding))
        self.statusBar().showMessage(f"Finding ignored: {finding.original} → {finding.replacement}")
        if self.active_popup:
            self.active_popup.close()
            self.active_popup = None
            self.last_popup_finding_id = None
            self.last_popup_finding_signature = None

    def _handle_popup_add_to_dict(self, finding: Finding):
        """处理浮动弹窗或主界面的 Add to dictionary 点击：将原词加入共享个人词典，不修改文本，并强制触发重新分析检查"""
        if not finding or not finding.original:
            return
        word = finding.original.strip()
        if word:
            # 使用与 AnalysisPipeline 共享的 PersonalDictionary 实例
            p_dict = None
            if self.monitor and hasattr(self.monitor, "pipeline") and hasattr(self.monitor.pipeline, "dictionary"):
                p_dict = self.monitor.pipeline.dictionary
            if not p_dict:
                p_dict = PersonalDictionary()
            
            added = p_dict.add_word(word)
            logger.info("Personal dictionary entry processed (added=%s).", added)
            self.statusBar().showMessage(f"Added '{word}' to Personal Dictionary.")
            
            if self.monitor and hasattr(self.monitor, "force_recheck"):
                self.monitor.force_recheck()
            elif self.monitor and hasattr(self.monitor, "trigger_check"):
                self.monitor.trigger_check()

        if self.active_popup:
            self.active_popup.close()
            self.active_popup = None
            self.last_popup_finding_id = None
            self.last_popup_finding_signature = None

    def _on_add_to_dict_clicked(self):
        """主界面点击 Add to Dictionary 按钮"""
        selected_items = self.findings_list_widget.selectedItems()
        if not selected_items:
            return
        item = selected_items[0]
        finding: Finding = item.data(Qt.ItemDataRole.UserRole)
        if not finding or not finding.original:
            return
        self._handle_popup_add_to_dict(finding)
        row = self.findings_list_widget.row(item)
        self.findings_list_widget.takeItem(row)
        self.details_text_edit.clear()
        self.btn_add_to_dict.setEnabled(False)
        self.btn_ignore.setEnabled(False)

    def closeEvent(self, event):
        """窗口关闭时确保监控器和后台线程干净停止"""
        try:
            if self.monitor:
                self.monitor.stop()
        except Exception as e:
            logger.error(f"Error stopping monitor on close: {e}", exc_info=True)
        event.accept()


def main() -> int:
    """G-Coach 桌面应用主入口（Phase 8B 应用生命周期与启动集成）

    1. 初始化 PyQt6 QApplication
    2. 创建 AnalysisPipeline 并注册 HarperAnalysisEngine 与 GectorAnalysisEngine
    3. 创建 AnalysisResolver
    4. 根据平台创建文本源（在 Windows 上使用 WindowsUIAccessibilityTextSource，在非 Windows 上或测试中使用 MockTextSource）
    5. 创建 LiveTextMonitor 并启动监控
    6. 创建 GCoachWindow 并显示
    7. 进入 Qt 事件循环，并在退出时清理/停止监控器
    """
    import platform
    from core.analysis import AnalysisPipeline, AnalysisResolver, HarperAnalysisEngine, GectorAnalysisEngine
    from core.monitoring import WindowsUIAccessibilityTextSource, MockTextSource, LiveTextMonitor

    # 1. 初始化 Qt 应用
    # Let the command-line launcher own argument parsing; Qt only needs argv[0].
    app = QApplication([sys.argv[0]]) if PYQT_AVAILABLE else None
    if not app:
        logger.error("Cannot launch G-Coach UI: PyQt6 is not available.")
        return 1

    # 2. 创建共享词典与分析管道
    shared_dictionary = PersonalDictionary()
    pipeline = AnalysisPipeline(dictionary=shared_dictionary)
    pipeline.register_engine(HarperAnalysisEngine())
    pipeline.register_engine(GectorAnalysisEngine())

    # 3. 创建消解层
    resolver = AnalysisResolver()

    # 4. 创建文本源（Windows 自动选择 UIA 文本源，非 Windows 使用 Mock 文本源以便在开发或测试环境中正常运行）
    if platform.system() == "Windows":
        text_source = WindowsUIAccessibilityTextSource()
        logger.info("Initialized WindowsUIAccessibilityTextSource for global Windows monitoring.")
    else:
        text_source = MockTextSource(initial_text="G-Coach Phase 8B running in non-Windows mode.", app_name="DevelopmentMock")
        logger.info("Initialized MockTextSource for non-Windows development mode.")

    # 5. 创建 LiveTextMonitor
    monitor = LiveTextMonitor(
        text_source=text_source,
        pipeline=pipeline,
        resolver=resolver,
        debounce_interval=0.4,
        poll_interval=0.05,
    )

    # 6. 默认启动监控（如果在 isolation popup 模式下，则不启动监控线程和 UIA）
    import os
    isolation_mode = os.environ.get("GCOACH_POPUP_ISOLATION", "").strip().lower()
    if isolation_mode == "popup":
        logger.info("[Phase8E isolation] GCOACH_POPUP_ISOLATION=popup detected: skipping monitor.start()")
        print("[Phase8E isolation] Monitor is NOT running (isolated popup mode)")
    else:
        monitor.start()

    # 7. 创建主窗口
    window = GCoachWindow(monitor)
    window.show()

    # 8. 运行 Qt 事件循环
    exit_code = app.exec()

    # 9. 干净退出时停止监控器
    if isolation_mode != "popup":
        monitor.stop()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
