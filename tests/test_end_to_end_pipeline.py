import unittest
from core.monitoring import MockTextSource
from core.analysis import AnalysisPipeline, AnalysisResolver, HarperAnalysisEngine, SymSpellAnalysisEngine, Finding

class TestEndToEndPipeline(unittest.TestCase):
    def test_end_to_end_pipeline_workflow(self):
        test_text = "She go to school and eat a apple."
        source = MockTextSource(initial_text=test_text, app_name="TestApp", control_id="test-ctrl-1")
        snapshot = source.get_current_text()
        self.assertEqual(snapshot.text, test_text)
        pipeline = AnalysisPipeline()
        pipeline.register_engine(HarperAnalysisEngine())
        pipeline.register_engine(SymSpellAnalysisEngine())
        raw_findings = pipeline.analyze(snapshot.text)
        resolved = AnalysisResolver().resolve(raw_findings)
        self.assertGreaterEqual(len(resolved), 1)
        for f in resolved:
            print(f"Finding: {f.original} -> {f.replacement} ({f.source})")
