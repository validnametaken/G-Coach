"""
G-Coach Test Launcher (Temporary Manual Testing Script for Phases 1–6)
=====================================================================
Usage on Windows:
    python gcoach_test.py

This script:
1. Creates a PyQt6 QApplication.
2. Initializes a MockTextSource with sample test text ("She go to school and eat a apple.") and allows live text editing/injection for testing analysis.
3. Builds an AnalysisPipeline containing:
   - HarperAnalysisEngine
   - GectorAnalysisEngine (with model directory check & graceful fallback if model files are missing)
4. Passes the pipeline through AnalysisResolver.
5. Connects the pipeline and text source to LiveTextMonitor.
6. Launches the G-Coach Phase 6 UI (GCoachWindow) clearly marked as "G-Coach Test (Phases 1–6)".
7. Does NOT modify main.py, existing AI_Prompt_Optimizer UI, or behavior.
8. Strictly read-only observation; no text modifications.
"""

import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("gcoach_test")

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QApplication,
        QVBoxLayout,
        QWidget,
        QLabel,
        QLineEdit,
        QPushButton,
        QHBoxLayout,
        QMessageBox,
    )
    from core.monitoring import MockTextSource, LiveTextMonitor
    from core.analysis import AnalysisPipeline, AnalysisResolver, HarperAnalysisEngine, GectorAnalysisEngine
    from core.ui import GCoachWindow
    PYQT_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import PyQt6 or G-Coach modules: {e}")
    PYQT_AVAILABLE = False


class GCoachTestLauncherWindow(GCoachWindow):
    """继承 GCoachWindow，添加用于测试的输入编辑区，以便手动输入或修改测试文本并触发分析"""

    def __init__(self, monitor: LiveTextMonitor, text_source: MockTextSource):
        super().__init__(monitor)
        self.text_source = text_source
        self.setWindowTitle("G-Coach Test (Phases 1–6) - Manual Testing Launcher")
        self._add_test_input_bar()

    def _add_test_input_bar(self):
        """在窗口顶部插入一个测试文本输入框，方便在没有 Windows UI Automation 真实控件时手动输入测试文本"""
        central_widget = self.centralWidget()
        main_layout = central_widget.layout()

        test_group = QWidget(self)
        test_layout = QHBoxLayout(test_group)
        test_layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("Test Input Text:", self)
        label.setStyleSheet("font-weight: bold;")
        test_layout.addWidget(label)

        self.input_line = QLineEdit(self)
        self.input_line.setText(self.text_source.text)
        self.input_line.setPlaceholderText("Type test text here (e.g. 'She go to school and eat a apple.') and click Update Text...")
        test_layout.addWidget(self.input_line, stretch=1)

        update_btn = QPushButton("Update Test Text", self)
        update_btn.clicked.connect(self._on_update_text_clicked)
        test_layout.addWidget(update_btn)

        # 插入到布局的最上方 (索引 0)
        main_layout.insertWidget(0, test_group)

    def _on_update_text_clicked(self):
        new_text = self.input_line.text()
        self.text_source.set_text(new_text)
        self.monitor.trigger_check()
        logger.info(f"Updated test text source to: '{new_text}' (gen: {self.text_source.generation})")
        self.statusBar().showMessage(f"Test text updated to gen {self.text_source.generation}. Waiting for debounce & analysis...")


def main():
    if not PYQT_AVAILABLE:
        print("ERROR: PyQt6 or required G-Coach modules are not available.")
        sys.exit(1)

    app = QApplication(sys.argv)

    # 1. 创建 MockTextSource，预置测试文本
    initial_sample_text = "She go to school and eat a apple."
    text_source = MockTextSource(initial_text=initial_sample_text, app_name="G-Coach Test Sandbox", status="ready")

    # 2. 构建 AnalysisPipeline
    pipeline = AnalysisPipeline()

    # 2.1 添加 Harper 引擎
    try:
        harper_engine = HarperAnalysisEngine()
        pipeline.register_engine(harper_engine)
        logger.info("HarperAnalysisEngine registered successfully.")
    except Exception as e:
        logger.warning(f"Could not register HarperAnalysisEngine: {e}")

    # 2.2 添加 GECToR 引擎（带模型文件检查与优雅回退）
    gector_model_dir = Path("models/gector")
    if gector_model_dir.exists() and any(gector_model_dir.iterdir()):
        try:
            gector_engine = GectorAnalysisEngine(model_dir=str(gector_model_dir))
            pipeline.register_engine(gector_engine)
            logger.info(f"GectorAnalysisEngine registered successfully from {gector_model_dir}.")
        except Exception as e:
            logger.warning(f"Could not initialize GectorAnalysisEngine: {e}")
    else:
        logger.warning(
            f"GECToR model directory '{gector_model_dir}' not found or empty. "
            "GectorAnalysisEngine will be skipped for this test run. "
            "To enable GECToR, place trained model files in models/gector/."
        )

    # 3. 创建 AnalysisResolver
    resolver = AnalysisResolver()

    # 4. 创建 LiveTextMonitor
    monitor = LiveTextMonitor(
        text_source=text_source,
        pipeline=pipeline,
        resolver=resolver,
        debounce_interval=0.3,
        poll_interval=0.05,
    )

    # 5. 创建并显示测试主窗口
    window = GCoachTestLauncherWindow(monitor, text_source)
    window.show()

    # 弹出提示说明
    QMessageBox.information(
        window,
        "G-Coach Test Launcher (Phases 1–6)",
        "Welcome to the G-Coach Test Launcher!\n\n"
        "• This launcher connects MockTextSource, Harper, GECToR, AnalysisResolver, LiveTextMonitor, and the PyQt6 UI.\n"
        "• You can edit the test text in the top input box and click 'Update Test Text'.\n"
        "• The UI will display live analysis findings, confidence scores, source engines, and multi-engine conflicts.\n"
        "• All operations are strictly read-only; no automatic text modifications are performed.",
    )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
