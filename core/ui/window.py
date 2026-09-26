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
    from PyQt6.QtCore import Qt, QTimer
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
from .floating_correction import FloatingCorrectionPopup
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

        self.setWindowTitle("G-Coach - Personal Writing Assistant")
        self.resize(900, 700)

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
        main_layout.addWidget(splitter, stretch=1)

        # 左侧容器
        left_widget = QWidget(self)
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

        splitter.setSizes([500, 400])

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
        if is_cand:
            self.btn_add_to_dict.setEnabled(True)
            self.btn_accept.setEnabled(False)
        else:
            self.btn_add_to_dict.setEnabled(False)
            self.btn_accept.setEnabled(True)
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

    def _sync_floating_popup(self, findings: List[Finding], state: MonitorState):
        """根据当前 findings 和 monitor state 同步浮动纠正弹窗的显示与隐藏（支持多发现导航）"""
        if not findings:
            if self.active_popup:
                self.active_popup.close()
                self.active_popup = None
                self.last_popup_finding_id = None
                self.last_popup_finding_signature = None
                self.last_popup_findings_count = 0
            return

        current_findings_count = len(findings)
        active_index = getattr(self, "last_popup_index", 0)
        if active_index >= current_findings_count:
            active_index = current_findings_count - 1

        active_finding = findings[active_index] if findings else findings[0]
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
                if getattr(self, "last_popup_findings_count", 0) == current_findings_count and self.active_popup.findings == findings:
                    self.active_popup.set_findings(findings, active_index)
                    self.last_popup_finding_signature = active_signature
                    return

                print(f"[Phase8E diagnostic] Finding changed or popup recreation requested. Closing old popup.")
                self.active_popup.close()
                self.active_popup = None

            primary_screen = QApplication.primaryScreen()
            primary_geom = primary_screen.geometry() if primary_screen else "None"
            all_screens_geom = [s.geometry() for s in QApplication.screens()]
            print(f"[Phase8E Screen Diagnostic] Primary screen: {primary_geom}, All screens: {all_screens_geom}")

            import os
            test_mode = os.environ.get("GCOACH_POPUP_TEST", "").strip().upper()
            popup_parent = self if test_mode == "Q-PARENT" else None
            target = CorrectionTarget.from_snapshot(state)
            
            def handle_navigate(new_idx: int):
                self.last_popup_index = new_idx
                nav_finding = findings[new_idx] if 0 <= new_idx < len(findings) else findings[0]
                self.last_popup_finding_signature = (
                    nav_finding.source,
                    nav_finding.original,
                    nav_finding.replacement,
                    nav_finding.start,
                    nav_finding.end,
                    len(findings),
                    new_idx
                )
                print(f"[Phase8E Navigation] Navigated to index {new_idx}: {nav_finding.original} -> {nav_finding.replacement}")

            self.active_popup = FloatingCorrectionPopup(
                findings=findings,
                current_index=active_index,
                target=target,
                on_accept=self._handle_popup_accept,
                on_ignore=self._handle_popup_ignore,
                on_navigate=handle_navigate,
                on_add_to_dict=self._handle_popup_add_to_dict,
                parent=popup_parent,
            )
            print(f"[Phase8E diagnostic] Multi-finding popup constructed (total: {current_findings_count}, index: {active_index})")
            self.last_popup_finding_id = active_finding.id
            self.last_popup_finding_signature = active_signature
            self.last_popup_findings_count = current_findings_count
            self.last_popup_index = active_index

            main_pos = self.pos()
            popup_x = main_pos.x() + self.width() + 20
            popup_y = main_pos.y() + 150
            print(f"[Phase8E diagnostic] Popup showing at ({popup_x}, {popup_y}) [Main pos: {main_pos}, width: {self.width()}]")
            self.active_popup.show_at(popup_x, popup_y)
            print(f"[Phase8E diagnostic] Popup shown")
        else:
            if self.active_popup:
                self.active_popup.set_findings(findings, active_index)

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
        print(f"[Phase8E Click Diagnostic] GCoachWindow._handle_popup_accept() entered for finding '{finding.original}' -> '{finding.replacement}'")
        print(f"[Phase8E Click Diagnostic] target: {target}")
        success = BackgroundCorrectionEngine.apply_correction_to_target(target, finding)
        print(f"[Phase8E Click Diagnostic] apply_correction_to_target returned success={success}")
        if success:
            self.statusBar().showMessage(f"Successfully applied background correction: {finding.original} → {finding.replacement}")
            finding.status = "accepted"
            if hasattr(self.monitor.text_source, "set_text"):
                # 如果是 Mock Text Source，同时更新其内部文本并触发检查
                current_t = getattr(self.monitor.text_source, "text", "")
                print(f"[Phase8E Click Diagnostic] text_source has set_text, current_t='{current_t}'")
                if current_t:
                    new_t = current_t[:finding.start] + finding.replacement + current_t[finding.end:]
                    print(f"[Phase8E Click Diagnostic] updating text_source to '{new_t}'")
                    self.monitor.text_source.set_text(new_t)
                    self.monitor.trigger_check()
            else:
                print("[Phase8E Click Diagnostic] text_source has no set_text")
        else:
            print("[Phase8E Click Diagnostic] correction failed")
            QMessageBox.warning(self, "Correction Failed", f"Background correction failed for finding '{finding.original}'.")
            self.statusBar().showMessage(f"Background correction failed for finding '{finding.original}'.")

        if self.active_popup:
            self.active_popup.close()
            self.active_popup = None
            self.last_popup_finding_id = None
            self.last_popup_finding_signature = None

    def _handle_popup_ignore(self, finding: Finding):
        """处理浮动弹窗的 Ignore 点击"""
        print(f"[Phase8E Click Diagnostic] GCoachWindow._handle_popup_ignore() entered for finding '{finding.original}'")
        self.correction_controller.mark_ignored(finding)
        self.statusBar().showMessage(f"Finding ignored: {finding.original} → {finding.replacement}")
        if self.active_popup:
            self.active_popup.close()
            self.active_popup = None
            self.last_popup_finding_id = None
            self.last_popup_finding_signature = None

    def _handle_popup_add_to_dict(self, finding: Finding):
        """处理浮动弹窗或主界面的 Add to dictionary 点击：将原词加入个人词典，不修改文本，并触发重新检查"""
        print(f"[Phase8F.1 Click Diagnostic] GCoachWindow._handle_popup_add_to_dict() entered for finding '{finding.original}'")
        if not finding or not finding.original:
            return
        word = finding.original.strip()
        if word:
            p_dict = PersonalDictionary()
            added = p_dict.add_word(word)
            logger.info(f"Added word to personal dictionary from UI: '{word}' (added={added})")
            self.statusBar().showMessage(f"Added '{word}' to Personal Dictionary.")
            if hasattr(self.monitor, "trigger_check"):
                self.monitor.trigger_check()
            elif hasattr(self.monitor, "text_source") and hasattr(self.monitor.text_source, "set_text"):
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


def main():
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
    app = QApplication(sys.argv) if PYQT_AVAILABLE else None
    if not app:
        logger.error("Cannot launch G-Coach UI: PyQt6 is not available.")
        sys.exit(1)

    # 2. 创建分析管道与引擎
    pipeline = AnalysisPipeline()
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
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
