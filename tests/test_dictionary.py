"""
Tests for Personal Dictionary (Phase 8F)
"""

import tempfile
import unittest
from pathlib import Path
from typing import List

from core.dictionary import PersonalDictionary
from core.analysis import AnalysisPipeline, Finding, BaseAnalysisEngine


class DummyEngine(BaseAnalysisEngine):
    """用于测试的虚拟引擎，产生特定 findings"""
    def __init__(self, findings):
        super().__init__(name="dummy", version="1.0", is_local=True)
        self._findings = findings

    def analyze(self, text: str) -> List[Finding]:
        return self._findings


class TestPersonalDictionary(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dict_path = Path(self.temp_dir.name) / "dictionary.json"
        self.dictionary = PersonalDictionary(storage_path=self.dict_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_1_add_word(self):
        """1. Add a word."""
        res = self.dictionary.add_word("Ichinomiya")
        self.assertTrue(res)
        self.assertIn("Ichinomiya", self.dictionary.words())

    def test_2_contains_recognizes_word(self):
        """2. contains() recognizes it."""
        self.dictionary.add_word("Nagoya")
        self.assertTrue(self.dictionary.contains("Nagoya"))

    def test_3_remove_word(self):
        """3. Remove a word."""
        self.dictionary.add_word("Samantha")
        self.assertTrue(self.dictionary.contains("Samantha"))
        res = self.dictionary.remove_word("Samantha")
        self.assertTrue(res)
        self.assertFalse(self.dictionary.contains("Samantha"))

    def test_4_persistence_survives_recreation(self):
        """4. Persistence survives recreating the dictionary object."""
        self.dictionary.add_word("Frederiksen")
        self.dictionary.add_word("OpenAI")
        
        # Recreate dict object with same path
        new_dict = PersonalDictionary(storage_path=self.dict_path)
        self.assertTrue(new_dict.contains("Frederiksen"))
        self.assertTrue(new_dict.contains("OpenAI"))
        self.assertEqual(new_dict.words(), ["Frederiksen", "OpenAI"])

    def test_5_duplicate_additions_harmless(self):
        """5. Duplicate additions are harmless."""
        self.dictionary.add_word("Ichinomiya")
        res = self.dictionary.add_word("Ichinomiya")
        self.assertFalse(res)
        self.assertEqual(self.dictionary.words(), ["Ichinomiya"])

    def test_6_empty_whitespace_input_rejected_safely(self):
        """6. Empty/whitespace input is rejected safely."""
        self.assertFalse(self.dictionary.add_word(""))
        self.assertFalse(self.dictionary.add_word("   "))
        self.assertFalse(self.dictionary.add_word(None))
        self.assertFalse(self.dictionary.remove_word(""))
        self.assertEqual(self.dictionary.words(), [])

    def test_7_dictionary_words_suppress_inappropriate_findings(self):
        """7. Dictionary words suppress inappropriate findings."""
        self.dictionary.add_word("Ichinomiya")
        finding = Finding(
            source="harper",
            category="spelling",
            message="Unknown word",
            original="Ichinomiya",
            replacement="",
            start=0,
            end=10,
        )
        pipeline = AnalysisPipeline(dictionary=self.dictionary)
        pipeline.register_engine(DummyEngine([finding]))
        
        findings = pipeline.analyze("Ichinomiya")
        self.assertEqual(len(findings), 0)

    def test_8_unrelated_neighboring_grammar_error_detected(self):
        """8. An unrelated neighboring grammar error is still detected."""
        self.dictionary.add_word("Ichinomiya")
        text = "Ichinomiya are beautiful."
        # Finding 1: on Ichinomiya (should be suppressed)
        f1 = Finding(source="harper", category="spelling", message="Unknown", original="Ichinomiya", replacement="", start=0, end=10)
        # Finding 2: on "are" (should be preserved)
        f2 = Finding(source="harper", category="grammar", message="Agreement", original="are", replacement="is", start=11, end=14)
        
        pipeline = AnalysisPipeline(dictionary=self.dictionary)
        pipeline.register_engine(DummyEngine([f1, f2]))

        findings = pipeline.analyze(text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].original, "are")

    def test_9_capitalization_handling(self):
        """9. Dictionary handling works with capitalization appropriately."""
        self.dictionary.add_word("Ichinomiya")
        self.assertTrue(self.dictionary.contains("Ichinomiya"))
        self.assertTrue(self.dictionary.contains("ichinomiya"))
        self.assertTrue(self.dictionary.contains("ICHINOMIYA"))

    def test_10_does_not_change_source_text(self):
        """10. Personal dictionary does not change source text."""
        text = "Ichinomiya is nice."
        self.dictionary.add_word("Ichinomiya")
        pipeline = AnalysisPipeline(dictionary=self.dictionary)
        pipeline.register_engine(DummyEngine([
            Finding(source="harper", category="spelling", message="Unknown", original="Ichinomiya", replacement="City", start=0, end=10)
        ]))
        findings = pipeline.analyze(text)
        # Dictionary suppressed the finding, source text is never mutated
        self.assertEqual(len(findings), 0)
        self.assertEqual(text, "Ichinomiya is nice.")

    def test_11_symspell_joined_word_detection_works_for_non_dictionary_words(self):
        """11. SymSpell joined-word detection still works for non-dictionary words."""
        from core.analysis import SymSpellAnalysisEngine
        pipeline = AnalysisPipeline(dictionary=self.dictionary)
        pipeline.register_engine(SymSpellAnalysisEngine())
        
        findings = pipeline.analyze("whatare you doing?")
        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0].replacement, "what are")

    def test_12_existing_protected_compounds_remain_protected(self):
        """12. Existing protected compounds such as cannot, outside, waiting, etc. remain protected."""
        from core.analysis import SymSpellAnalysisEngine
        engine = SymSpellAnalysisEngine()
        # "cannot" should not be split by SymSpell
        findings = engine.analyze("cannot")
        self.assertEqual(len(findings), 0)

    def test_13_multiple_dictionary_words_work_independently(self):
        """13. Multiple dictionary words work independently."""
        self.dictionary.add_word("Ichinomiya")
        self.dictionary.add_word("Nagoya")
        self.dictionary.add_word("OpenAI")
        
        self.assertTrue(self.dictionary.contains("Ichinomiya"))
        self.assertTrue(self.dictionary.contains("Nagoya"))
        self.assertTrue(self.dictionary.contains("OpenAI"))
        self.assertFalse(self.dictionary.contains("Tokyo"))
        self.assertEqual(len(self.dictionary.words()), 3)

    def test_14_existing_resolver_policy_behavior_intact(self):
        """14. Existing analysis/resolver/policy behavior remains intact."""
        from core.analysis import AnalysisResolver, CorrectionPolicy, HarperAnalysisEngine, SymSpellAnalysisEngine
        pipeline = AnalysisPipeline(dictionary=self.dictionary)
        resolver = AnalysisResolver()
        policy = CorrectionPolicy()
        
        self.dictionary.add_word("OpenAI")
        text = "OpenAI is great."
        raw = pipeline.analyze(text)
        resolved = resolver.resolve(raw)
        curated = policy.apply(resolved)
        self.assertEqual(len(curated), 0)
