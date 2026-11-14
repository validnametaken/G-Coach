"""Ensure normal analysis and correction diagnostics do not disclose source text."""

import json
import logging
from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock

from core.analysis import BaseAnalysisEngine, Finding
from core.analysis.harper import HarperAnalysisEngine
from core.analysis.pipeline import AnalysisPipeline
from core.correction.target import CorrectionTarget
from core.ui.window import GCoachWindow


class _SingleFindingEngine(BaseAnalysisEngine):
    def __init__(self, finding):
        super().__init__(name="privacy-test", version="1", is_local=True)
        self.finding = finding

    @property
    def supported_types(self):
        return ["spelling"]

    @property
    def supports_auto_fix(self):
        return True

    def analyze(self, _text):
        return [self.finding]


class _MatchingDictionary:
    def contains(self, word):
        return word == "private-term"


def test_harper_offset_diagnostic_does_not_log_source_text(monkeypatch, caplog):
    engine = HarperAnalysisEngine()

    payload = [{
        "original": "different-term",
        "start": 0,
        "end": 6,
        "replacements": [],
        "category": "spelling",
        "message": "Diagnostic test",
    }]
    monkeypatch.setattr(
        "core.analysis.harper.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(payload).encode("utf-8"),
            stderr=b"",
        ),
    )

    with caplog.at_level(logging.DEBUG):
        engine.analyze("secret-source-text")

    assert "secret-source-text" not in caplog.text
    assert "different-term" not in caplog.text


def test_dictionary_suppression_does_not_log_private_word(caplog):
    finding = Finding(
        source="test",
        category="spelling",
        message="Private term",
        original="private-term",
        replacement="",
        start=0,
        end=12,
    )
    pipeline = AnalysisPipeline(dictionary=_MatchingDictionary())
    pipeline.register_engine(_SingleFindingEngine(finding))

    with caplog.at_level(logging.DEBUG):
        assert pipeline.analyze("private-term") == []

    assert "private-term" not in caplog.text


def test_popup_accept_does_not_print_finding_or_target_text(monkeypatch, capsys):
    finding = Finding(
        source="test",
        category="grammar",
        message="Test correction",
        original="private-term",
        replacement="public-term",
        start=0,
        end=12,
    )
    target = CorrectionTarget(original_text="private-term in a private sentence")
    source = SimpleNamespace(text="private-term in a private sentence")
    source.set_text = lambda value: setattr(source, "text", value)
    monitor = SimpleNamespace(text_source=source, trigger_check=lambda: None)
    window = SimpleNamespace(
        monitor=monitor,
        active_popup=None,
        statusBar=lambda: MagicMock(),
    )
    window._execute_uia_operation = MethodType(GCoachWindow._execute_uia_operation, window)

    monkeypatch.setattr(
        "core.ui.window.BackgroundCorrectionEngine.apply_correction_to_target_detailed",
        lambda *_args: SimpleNamespace(
            success=True,
            reason="",
            resulting_text="public-term in a private sentence",
        ),
    )

    GCoachWindow._handle_popup_accept(window, finding, target)

    output = capsys.readouterr()
    assert "private-term" not in output.out
    assert "private sentence" not in output.out

