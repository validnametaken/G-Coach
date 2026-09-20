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
    )
    PYQT_AVAILABLE = True
except (ImportError, OSError) as e:
    logger.warning(f"PyQt6 or system GUI libraries (e.g. libEGL) not available: {e}. GUI window disabled.")
    PYQT_AVAILABLE = False
    QMainWindow = object  # type: ignore

from core.monitoring import LiveTextMonitor, MonitorState
from core.analysis import Finding
from .presenter import UIPresenter


class GCoachWindow(QMainWindow if PYQT_AVAILABLE else object):
    """G-Coach 桌面主窗口"""

    def __init__(self, monitor: LiveTextMonitor):
        if not PYQT_AVAILABLE:
            raise RuntimeError("PyQt6 is not available in this environment (headless container).")
        super().__init__()
        self.monitor = monitor
        self.current_findings: List[Finding] = []

        self.setWindowTitle("G-Coach - Personal Writing Assistant")
        self.resize(900, 700)

        self._init_ui()

        # 设置定时器用于定期从 monitor 获取最新状态（主线程安全轮询）
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(100)  # 每 100ms 刷新一次 UI
        self.update_timer.timeout.connect(self._poll_monitor_state)
        self.update_timer.start()

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

        # Phase 6.x: 如果处于等待或分析中状态，在 findings 列表或状态栏提示正在检查，避免用户误认旧结果
        if summary['is_pending']:
            self.statusBar().showMessage(summary['pending_message'])
            # 可以在列表显示一个临时的检查提示项，让用户感知正在为新生成文本工作
            if self.findings_list_widget.count() == 0 or not any("Checking" in self.findings_list_widget.item(i).text() for i in range(self.findings_list_widget.count())):
                # 仅当没有临时提示时添加
                pass
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

                if summary['has_conflicts']:
                    self.statusBar().showMessage(f"Found {len(new_findings)} findings with multi-engine conflicts.")
                else:
                    self.statusBar().showMessage(f"Found {len(new_findings)} findings (Ready).")

    def _on_finding_selected(self):
        """当用户在列表中选择某条 Finding 时展示其详情与冲突分析"""
        selected_items = self.findings_list_widget.selectedItems()
        if not selected_items:
            self.details_text_edit.clear()
            return

        item = selected_items[0]
        finding: Finding = item.data(Qt.ItemDataRole.UserRole)
        if not finding:
            return

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

    def closeEvent(self, event):
        """窗口关闭时确保监控器和后台线程干净停止"""
        try:
            if self.monitor:
                self.monitor.stop()
        except Exception as e:
            logger.error(f"Error stopping monitor on close: {e}", exc_info=True)
        event.accept()
