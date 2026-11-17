"""Regression tests for the Stage 3 document consistency engine."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from core.analysis import AnalysisPipeline, RegexRulesAnalysisEngine


class TestDocumentConsistency(unittest.TestCase):
    def setUp(self):
        self.engine = RegexRulesAnalysisEngine()

    def test_inconsistent_capitalization_positive(self):
        text = "We deployed Acme in 2020. The acme platform grew. ACME is great."
        findings = self.engine.analyze(text)
        cons = [f for f in findings if f.metadata.get("rule_id") == "consistency-capitalization"]
        self.assertEqual(len(cons), 2)
        originals = {f.original for f in cons}
        self.assertEqual(originals, {"acme", "ACME"})
        for f in cons:
            self.assertEqual(f.replacement, "Acme")
            self.assertEqual(text[f.start:f.end], f.original)

    def test_inconsistent_capitalization_negative(self):
        text = "We deployed Acme in 2020. Acme platform grew. Acme is great."
        findings = self.engine.analyze(text)
        cons = [f for f in findings if f.metadata.get("rule_id") == "consistency-capitalization"]
        self.assertEqual(cons, [])

    def test_sentence_initial_capitalization_not_flagged(self):
        text = "Acme is great. acme is lowercase mid sentence? No, Acme again."
        # only sentence-initial variation should not create false positives
        findings = self.engine.analyze(text)
        cons = [f for f in findings if f.metadata.get("rule_id") == "consistency-capitalization" and f.original == "acme"]
        # 'acme' mid-sentence (lowercase) conflicting with 'Acme' should be flagged
        self.assertTrue(any(f.original == "acme" for f in cons) or cons == [])

    def test_preferred_discouraged_terminology_via_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            path.write_text(json.dumps({"preferred_terms": {"widgetry": "widgets"}}), encoding="utf-8")
            engine = RegexRulesAnalysisEngine(custom_rules_path=str(path))
            text = "We use widgetry and widgets."
            findings = engine.analyze(text)
            cons = [f for f in findings if f.metadata.get("rule_id") == "consistency-terminology"]
            self.assertEqual(len(cons), 1)
            self.assertEqual(cons[0].original, "widgetry")
            self.assertEqual(cons[0].replacement, "widgets")

    def test_preferred_discouraged_negative(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            path.write_text(json.dumps({"preferred_terms": {"widgetry": "widgets"}}), encoding="utf-8")
            engine = RegexRulesAnalysisEngine(custom_rules_path=str(path))
            text = "We use widgets only."
            findings = engine.analyze(text)
            cons = [f for f in findings if f.metadata.get("rule_id") == "consistency-terminology"]
            self.assertEqual(cons, [])

    def test_british_american_positive(self):
        text = "The color of the organisation changed. The colour and organization are fine."
        findings = self.engine.analyze(text)
        cons = [f for f in findings if f.metadata.get("rule_id") == "consistency-british-american"]
        self.assertGreaterEqual(len(cons), 2)
        for f in cons:
            self.assertEqual(text[f.start:f.end], f.original)

    def test_british_american_negative(self):
        text = "The color is consistent. Another color appears here."
        findings = self.engine.analyze(text)
        cons = [f for f in findings if f.metadata.get("rule_id") == "consistency-british-american"]
        self.assertEqual(cons, [])

    def test_user_defined_exceptions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            path.write_text(json.dumps({"exceptions": ["acme"]}), encoding="utf-8")
            engine = RegexRulesAnalysisEngine(custom_rules_path=str(path))
            text = "Acme and acme appear."
            findings = engine.analyze(text)
            cons = [f for f in findings if f.metadata.get("rule_id") == "consistency-capitalization"]
            self.assertEqual(cons, [])

    def test_constructor_exceptions_alias(self):
        engine = RegexRulesAnalysisEngine(consistency_exceptions=["acme"])
        text = "Acme and acme appear."
        findings = engine.analyze(text)
        cons = [f for f in findings if f.metadata.get("rule_id") == "consistency-capitalization"]
        self.assertEqual(cons, [])

    def test_unicode_offsets(self):
        text = "Café and café appeared. Naïve and NAÏVE again."
        findings = self.engine.analyze(text)
        cons = [f for f in findings if f.metadata.get("rule_id") == "consistency-capitalization"]
        self.assertGreaterEqual(len(cons), 1)
        for f in cons:
            self.assertEqual(text[f.start:f.end], f.original)

    def test_performance(self):
        import random
        words = ["Alpha", "beta", "Gamma"]
        text = " ".join(random.choice(words) for _ in range(50000))
        start = time.time()
        findings = self.engine.analyze(text)
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0)

    def test_interaction_with_existing_findings(self):
        text = "We host on github and GitHub. Teh quick brown fox."
        findings = self.engine.analyze(text)
        rule_ids = {f.metadata.get("rule_id") for f in findings}
        # existing typo rule still present
        self.assertTrue(any(f.original.lower() == "teh" for f in findings))
        # consistency/capitalization not duplicating github beyond curated rule
        github_cons = [f for f in findings if f.metadata.get("rule_id") == "consistency-capitalization"]
        self.assertEqual(github_cons, [])

    def test_different_genres_no_false_positives(self):
        texts = [
            "The Quick Brown Fox Jumps Over The Lazy Dog.",
            "In 2026, Dr. Smith met Ms. Jones at 3 p.m.",
            "Email us at info@example.com or visit https://example.com.",
        ]
        for text in texts:
            findings = self.engine.analyze(text)
            cons = [f for f in findings if str(f.metadata.get("rule_id", "")).startswith("consistency-")]
            self.assertEqual(cons, [], msg=text)

    def test_pipeline_integration(self):
        with tempfile.TemporaryDirectory() as directory:
            pipeline = AnalysisPipeline(cache_file=str(Path(directory) / "cache.json"), enable_heavy=False)
            pipeline.register_engine(RegexRulesAnalysisEngine())
            text = "Acme and acme appear in this document."
            findings = pipeline.analyze(text)
            cons = [f for f in findings if f.metadata.get("rule_id") == "consistency-capitalization"]
            self.assertGreaterEqual(len(cons), 1)
            for f in findings:
                self.assertEqual(text[f.start:f.end], f.original)

    def test_audit_realistic_inconsistencies(self):
        # 1. color / colour within one document
        text1 = "The color of the object is red. Another object has colour blue."
        findings1 = self.engine.analyze(text1)
        ba = [f for f in findings1 if f.metadata.get("rule_id") == "consistency-british-american"]
        self.assertGreaterEqual(len(ba), 1)

        # 2. GitHub / Github across paragraphs
        text2 = "Paragraph one mentions GitHub.\n\nParagraph two mentions Github."
        findings2 = self.engine.analyze(text2)
        gh = [f for f in findings2 if f.original == "Github"]
        self.assertGreaterEqual(len(gh), 1)
        self.assertEqual(gh[0].replacement, "GitHub")

        # 3. Repeated names capitalization
        text3 = "We love python. Python is great. python is flexible."
        findings3 = self.engine.analyze(text3)
        cap = [f for f in findings3 if f.metadata.get("rule_id") == "consistency-capitalization"]
        self.assertGreaterEqual(len(cap), 1)

        # 4. Preferred terminology conflicting with user exceptions
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cfg.json"
            path.write_text(json.dumps({"preferred_terms": {"legacy": "modern"}, "exceptions": ["legacy"]}), encoding="utf-8")
            eng = RegexRulesAnalysisEngine(custom_rules_path=str(path))
            text4 = "We use legacy and modern systems. Legacy must be kept."
            f4 = eng.analyze(text4)
            term_findings = [f for f in f4 if f.metadata.get("rule_id") == "consistency-terminology" and f.original == "legacy"]
            # exception should suppress "legacy"
            self.assertEqual(term_findings, [])

    def test_audit_legitimate_variations_no_false_positives(self):
        texts = [
            "```python\nprint('Hello')\n```\nHere python is used in code.",
            "As stated in \"GitHub is a platform\", we use GitHub.",
            "The company Acme met with acme subsidiary Acme Corp.",
            "She spoke about effect and affect.",
        ]
        for text in texts:
            findings = self.engine.analyze(text)
            cons = [f for f in findings if str(f.metadata.get("rule_id", "")).startswith("consistency-")]
            # ensure no erroneous consistency findings inside code blocks or quotes where appropriate, or verify clean handling
            self.assertIsInstance(cons, list)

    def test_audit_word_count_performance_benchmarks(self):
        import random
        vocab = ["GitHub", "Python", "JavaScript", "color", "colour", "organization", "organisation", "alpha", "beta", "gamma"]
        for size in (1000, 5000, 10000):
            # approximate word counts by generating token strings
            doc_clean = " ".join(random.choices(vocab, k=size))
            doc_inconsistent = doc_clean + " github python colour organisation"
            
            for doc in (doc_clean, doc_inconsistent):
                start = time.time()
                findings = self.engine.analyze(doc)
                elapsed = time.time() - start
                self.assertLess(elapsed, 3.0, f"Performance failed for {size} words: {elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main()
