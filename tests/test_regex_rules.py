"""
Unit tests for RegexRulesAnalysisEngine (OpenGrammar-style Fast Supplement Engine)
"""

import unittest
import tempfile
from pathlib import Path
from core.analysis import RegexRulesAnalysisEngine, AnalysisPipeline


class TestRegexRulesAnalysisEngine(unittest.TestCase):
    """测试极速正则规则引擎 (RegexRulesAnalysisEngine)"""

    def setUp(self):
        self.engine = RegexRulesAnalysisEngine()

    def test_engine_metadata(self):
        self.assertEqual(self.engine.name, "regex_rules")
        self.assertEqual(self.engine.tier, "fast")
        self.assertTrue(self.engine.is_local)
        self.assertTrue(self.engine.supports_auto_fix)

    def test_detects_common_typos(self):
        findings = self.engine.analyze("Please check teh document and recieve the package.")
        self.assertEqual(len(findings), 2)
        
        self.assertEqual(findings[0].original, "teh")
        self.assertEqual(findings[0].replacement, "the")
        self.assertEqual(findings[0].category, "spelling")

        self.assertEqual(findings[1].original, "recieve")
        self.assertEqual(findings[1].replacement, "receive")
        self.assertEqual(findings[1].category, "spelling")

    def test_detects_duplicate_repetitions(self):
        findings = self.engine.analyze("I went to the the store.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].original, "the the")
        self.assertEqual(findings[0].replacement, "the")
        self.assertEqual(findings[0].category, "style")

    def test_detects_wordy_phrases(self):
        findings = self.engine.analyze("We left due to the fact that it was raining, in order to stay dry.")
        self.assertEqual(len(findings), 2)
        
        self.assertEqual(findings[0].original, "due to the fact that")
        self.assertEqual(findings[0].replacement, "because")

        self.assertEqual(findings[1].original, "in order to")
        self.assertEqual(findings[1].replacement, "to")

    def test_detects_confusable_phrases_and_spacing(self):
        findings = self.engine.analyze("You should of known. Hello , world .")
        self.assertGreaterEqual(len(findings), 3)

        originals = [f.original for f in findings]
        self.assertIn("should of", originals)
        self.assertIn(" ,", originals)
        self.assertIn(" .", originals)

    def test_detects_prose_linters_rules(self):
        findings = self.engine.analyze("It is important to note that low-hanging fruit is very unique. It seems that we must make a decision.")
        self.assertEqual(len(findings), 5)

        self.assertEqual(findings[0].original, "It is important to note that")
        self.assertEqual(findings[1].original, "low-hanging fruit")
        self.assertEqual(findings[2].original, "very unique")
        self.assertEqual(findings[3].original, "It seems that")
        self.assertEqual(findings[4].original, "make a decision")

    def test_pipeline_integration_with_regex_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            pipeline = AnalysisPipeline(cache_file=str(Path(directory) / "cache.json"))
            pipeline.register_engine(self.engine)

            findings = pipeline.analyze("It is teh best.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].source, "regex_rules")
        self.assertEqual(findings[0].replacement, "the")

    def test_pipeline_preserves_unicode_document_offsets_across_sentences(self):
        text = "😀 日本語. Café has teh typo. Résumé has recieve."
        with tempfile.TemporaryDirectory() as directory:
            pipeline = AnalysisPipeline(cache_file=str(Path(directory) / "cache.json"))
            pipeline.register_engine(RegexRulesAnalysisEngine(custom_rules_path=str(
                Path(directory) / "no-custom-rules.json"
            )))
            findings = pipeline.analyze(text)

        originals = {finding.original: finding for finding in findings}
        self.assertIn("teh", originals)
        self.assertIn("recieve", originals)
        for finding in findings:
            self.assertEqual(text[finding.start:finding.end], finding.original)
        self.assertEqual(originals["teh"].start, text.index("teh"))
        self.assertEqual(originals["recieve"].start, text.index("recieve"))

    def test_pipeline_runs_scope_specific_rules_against_correct_buffers(self):
        yaml_rules = """\
rules:
  - id: live-rule
    pattern: 'live'
    replacement: current
    category: grammar
    message: Live scope.
    scope: live
  - id: sentence-rule
    pattern: 'word'
    replacement: term
    category: grammar
    message: Sentence scope.
    scope: sentence
  - id: document-rule
    pattern: 'document'
    replacement: file
    category: grammar
    message: Document scope.
    scope: document
"""
        with tempfile.TemporaryDirectory() as directory:
            rules_path = Path(directory) / "scopes.yaml"
            rules_path.write_text(yaml_rules, encoding="utf-8")
            pipeline = AnalysisPipeline(cache_file=str(Path(directory) / "cache.json"))
            pipeline.register_engine(RegexRulesAnalysisEngine(custom_rules_path=str(rules_path)))
            text = "live. word. document."
            findings = pipeline.analyze(text)

        self.assertEqual(
            {finding.metadata.get("rule_id") for finding in findings},
            {"live-rule", "sentence-rule", "document-rule"},
        )
        for finding in findings:
            self.assertEqual(text[finding.start:finding.end], finding.original)


if __name__ == "__main__":
    unittest.main()
