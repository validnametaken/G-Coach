"""Regression tests for document-scoped Ignore suppression in the floating popup."""

from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock

from core.analysis import Finding
from core.correction.controller import CorrectionController
from core.monitoring import MonitorState
from core.ui.window import GCoachWindow


def make_finding(*, source="harper", original="was", replacement="were", start=4, end=7):
    return Finding(
        source=source,
        category="grammar",
        message="Agreement suggestion",
        original=original,
        replacement=replacement,
        start=start,
        end=end,
    )


def make_state(text="They was ready.", control_id="control-1"):
    return MonitorState(
        text=text,
        status="ready",
        control_id=control_id,
        app_name="TestApp",
        control_info="Editor",
        control_type="Document",
    )


def make_window_stub():
    status_bar = MagicMock()
    window = SimpleNamespace(
        _ignored_context=None,
        _ignored_finding_signatures=set(),
        correction_controller=CorrectionController(),
        active_popup=None,
        statusBar=lambda: status_bar,
    )
    window._update_ignored_context = MethodType(GCoachWindow._update_ignored_context, window)
    window._ignore_signature = GCoachWindow._ignore_signature
    window._filter_ignored_findings = MethodType(GCoachWindow._filter_ignored_findings, window)
    window._execute_uia_operation = MethodType(GCoachWindow._execute_uia_operation, window)
    return window


def filter_findings(window, findings, state):
    return GCoachWindow._filter_ignored_findings(window, findings, state)


def ignore_finding(window, finding):
    GCoachWindow._handle_popup_ignore(window, finding)


def test_ignore_survives_repeated_monitor_cycles_and_regenerated_finding_ids():
    window = make_window_stub()
    state = make_state()
    ignored = make_finding()
    other = make_finding(source="gector", original="ready", replacement="prepared", start=8, end=13)

    assert filter_findings(window, [ignored, other], state) == [ignored, other]
    ignore_finding(window, ignored)
    assert ignored.status == "ignored"

    # A new analysis run recreates Finding objects with new IDs. The ignored
    # suggestion remains suppressed while the unrelated suggestion stays visible.
    regenerated_ignored = make_finding()
    regenerated_other = make_finding(source="gector", original="ready", replacement="prepared", start=8, end=13)
    assert regenerated_ignored.id != ignored.id
    assert filter_findings(window, [regenerated_ignored, regenerated_other], state) == [regenerated_other]

    another_cycle = make_finding()
    assert another_cycle.id != regenerated_ignored.id
    assert filter_findings(window, [another_cycle, regenerated_other], state) == [regenerated_other]
    assert state.text == "They was ready."


def test_ignoring_one_finding_keeps_other_findings_accessible():
    window = make_window_stub()
    state = make_state()
    first = make_finding()
    second = make_finding(source="gector", original="ready", replacement="prepared", start=8, end=13)
    third = make_finding(source="style", original="They", replacement="The students", start=0, end=4)

    filter_findings(window, [first, second, third], state)
    ignore_finding(window, first)

    assert filter_findings(window, [first, second, third], state) == [second, third]


def test_popup_receives_only_non_ignored_findings(monkeypatch):
    import core.ui.window as window_module

    class FakeRect:
        def x(self):
            return 0

        def y(self):
            return 0

        def width(self):
            return 1920

        def height(self):
            return 1080

    fake_rect = FakeRect()
    fake_screen = SimpleNamespace(
        geometry=lambda: fake_rect,
        availableGeometry=lambda: fake_rect,
    )

    class FakeApplication:
        @staticmethod
        def primaryScreen():
            return fake_screen

        @staticmethod
        def screens():
            return [fake_screen]

        @staticmethod
        def screenAt(_position):
            return fake_screen

    class FakePopup:
        def __init__(self, **kwargs):
            self.findings = kwargs["findings"]
            self.current_index = kwargs["current_index"]
            self.shown_position = None

        def sizeHint(self):
            return SimpleNamespace(width=lambda: 260, height=lambda: 120)

        def show_at(self, x, y):
            self.shown_position = (x, y)

        def close(self):
            pass

        def set_findings(self, findings, current_index):
            self.findings = findings
            self.current_index = current_index

    monkeypatch.setattr(window_module, "QApplication", FakeApplication, raising=False)
    monkeypatch.setattr(window_module, "FloatingCorrectionPopup", FakePopup)
    monkeypatch.setattr(window_module, "calculate_popup_position", lambda *args: (10, 20))

    window = make_window_stub()
    window.last_popup_finding_signature = None
    window.last_popup_finding_id = None
    window.last_popup_findings_count = 0
    window.last_popup_index = 0
    window.pos = lambda: SimpleNamespace(x=lambda: 0, y=lambda: 0)
    window.screen = lambda: None
    window.width = lambda: 500
    window.height = lambda: 400
    window._handle_popup_accept = lambda *_args: None
    window._handle_popup_ignore = lambda *_args: None
    window._handle_popup_add_to_dict = lambda *_args: None

    state = make_state()
    ignored = make_finding()
    visible = make_finding(source="gector", original="ready", replacement="prepared", start=8, end=13)
    filter_findings(window, [ignored, visible], state)
    ignore_finding(window, ignored)

    GCoachWindow._sync_floating_popup(window, [make_finding(), visible], state)

    assert isinstance(window.active_popup, FakePopup)
    assert window.active_popup.findings == [visible]
    assert window.active_popup.current_index == 0


def test_popup_is_anchored_to_the_finding_screen_rectangle(monkeypatch):
    import core.ui.window as window_module
    from core.correction.engine import BackgroundCorrectionEngine

    fake_rect = SimpleNamespace(
        x=lambda: 0,
        y=lambda: 0,
        width=lambda: 1920,
        height=lambda: 1080,
    )
    fake_screen = SimpleNamespace(availableGeometry=lambda: fake_rect)

    class FakeApplication:
        @staticmethod
        def screenAt(_position):
            return fake_screen

        @staticmethod
        def primaryScreen():
            return fake_screen

    class FakePopup:
        def __init__(self, **kwargs):
            self.findings = kwargs["findings"]
            self.current_index = kwargs["current_index"]
            self.shown_position = None

        def sizeHint(self):
            return SimpleNamespace(width=lambda: 260, height=lambda: 120)

        def show_at(self, x, y):
            self.shown_position = (x, y)

        def close(self):
            pass

        def set_findings(self, findings, current_index):
            self.findings = findings
            self.current_index = current_index

    observed = {}

    def capture_anchor(*args):
        observed["anchor"] = args[:4]
        return (500, 300)

    monkeypatch.setattr(window_module, "QApplication", FakeApplication, raising=False)
    monkeypatch.setattr(window_module, "FloatingCorrectionPopup", FakePopup)
    monkeypatch.setattr(window_module, "calculate_popup_position", capture_anchor)
    monkeypatch.setattr(
        BackgroundCorrectionEngine,
        "get_finding_screen_rect",
        staticmethod(lambda _target, _finding: (410, 260, 38, 18)),
    )

    window = make_window_stub()
    window.last_popup_finding_signature = None
    window.last_popup_finding_id = None
    window.last_popup_findings_count = 0
    window.last_popup_index = 0
    window.pos = lambda: SimpleNamespace(x=lambda: 0, y=lambda: 0)
    window.screen = lambda: None
    window.width = lambda: 500
    window.height = lambda: 400
    window._handle_popup_accept = lambda *_args: None
    window._handle_popup_ignore = lambda *_args: None
    window._handle_popup_add_to_dict = lambda *_args: None

    finding = make_finding()
    GCoachWindow._sync_floating_popup(window, [finding], make_state())

    assert observed["anchor"] == (410, 260, 38, 18)
    assert window.active_popup.shown_position == (500, 300)


def test_text_change_resets_ignore_suppression():
    window = make_window_stub()
    original_state = make_state()
    ignored = make_finding()
    filter_findings(window, [ignored], original_state)
    ignore_finding(window, ignored)
    stale_popup = MagicMock()
    window.active_popup = stale_popup

    changed_text_state = make_state(text="They were ready.")
    same_suggestion = make_finding()
    assert filter_findings(window, [same_suggestion], changed_text_state) == [same_suggestion]
    stale_popup.close.assert_called_once_with()
    assert window.active_popup is None


def test_control_change_resets_ignore_suppression_even_when_text_is_identical():
    window = make_window_stub()
    original_state = make_state(control_id="control-1")
    ignored = make_finding()
    filter_findings(window, [ignored], original_state)
    ignore_finding(window, ignored)

    other_control_state = make_state(control_id="control-2")
    same_suggestion = make_finding()
    assert filter_findings(window, [same_suggestion], other_control_state) == [same_suggestion]


def test_stale_finding_cannot_be_ignored_into_a_new_pending_document_context():
    window = make_window_stub()
    old_state = make_state()
    stale_finding = make_finding()
    filter_findings(window, [stale_finding], old_state)

    pending_state = make_state(text="They were ready.")
    pending_state.status = "waiting"
    filter_findings(window, [], pending_state)
    ignore_finding(window, stale_finding)
    assert window._ignore_context_ready is False

    ready_state = make_state(text="They were ready.")
    new_finding = make_finding()
    assert filter_findings(window, [new_finding], ready_state) == [new_finding]


def test_empty_analysis_result_still_resets_context_for_new_document():
    window = make_window_stub()
    original_state = make_state()
    ignored = make_finding()
    filter_findings(window, [ignored], original_state)
    ignore_finding(window, ignored)

    changed_state = make_state(text="A different document.")
    assert filter_findings(window, [], changed_state) == []
    same_suggestion = make_finding()
    assert filter_findings(window, [same_suggestion], changed_state) == [same_suggestion]
