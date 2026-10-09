"""
Unit tests for CorrectionPolicy layer (CorrectionPolicy)
"""

import unittest
from core.analysis import Finding, AnalysisResolver, CorrectionPolicy, AnalysisPipeline, HarperAnalysisEngine, SymSpellAnalysisEngine, GectorAnalysisEngine


class TestCorrectionPolicy(unittest.TestCase):
    """测试 CorrectionPolicy 候选精炼层的各项冲突裁决、规则优先级与集成行为"""

    def setUp(self):
        self.resolver = AnalysisResolver()
        self.policy = CorrectionPolicy()

    def test_policy_empty_and_single(self):
        self.assertEqual(self.policy.apply([]), [])
        f = Finding(source="harper", category="capitalization", message="Cap", original="are", replacement="Are", start=30, end=33)
        resolved = self.resolver.resolve([f])
        curated = self.policy.apply(resolved)
        self.assertEqual(len(curated), 1)
        self.assertEqual(curated[0].replacement, "Are")

    def test_symspell_beats_harper_capitalization_whatare(self):
        """1. SymSpell WORD_BOUNDARY beats Harper capitalization for whatare → Whatare vs whatare → what are"""
        f_harper = Finding(source="harper", category="capitalization", message="Cap", original="whatare", replacement="Whatare", start=35, end=42)
        f_symspell = Finding(source="symspell", category="word_boundary", message="Boundary", original="whatare", replacement="what are", start=35, end=42)
        
        resolved = self.resolver.resolve([f_harper, f_symspell])
        curated = self.policy.apply(resolved)
        
        self.assertEqual(len(curated), 1)
        self.assertEqual(curated[0].replacement, "what are")
        self.assertEqual(curated[0].source, "symspell")

    def test_symspell_beats_harper_bad_suggestion_goodmorning(self):
        """2. SymSpell WORD_BOUNDARY beats Harper bad suggestion for Goodmorning → Woodworking vs Good morning"""
        f_harper = Finding(source="harper", category="spelling", message="Spelling", original="Goodmorning", replacement="Woodworking", start=0, end=11)
        f_symspell = Finding(source="symspell", category="word_boundary", message="Boundary", original="Goodmorning", replacement="Good morning", start=0, end=11)
        
        resolved = self.resolver.resolve([f_harper, f_symspell])
        curated = self.policy.apply(resolved)
        
        self.assertEqual(len(curated), 1)
        self.assertEqual(curated[0].replacement, "Good morning")
        self.assertEqual(curated[0].source, "symspell")

    def test_symspell_beats_harper_truncation_thankyou(self):
        """3. SymSpell WORD_BOUNDARY beats Harper truncation for Thankyou → Thank vs Thank you"""
        f_harper = Finding(source="harper", category="spelling", message="Spelling", original="Thankyou", replacement="Thank", start=0, end=8)
        f_symspell = Finding(source="symspell", category="word_boundary", message="Boundary", original="Thankyou", replacement="Thank you", start=0, end=8)
        
        resolved = self.resolver.resolve([f_harper, f_symspell])
        curated = self.policy.apply(resolved)
        
        self.assertEqual(len(curated), 1)
        self.assertEqual(curated[0].replacement, "Thank you")
        self.assertEqual(curated[0].source, "symspell")

    def test_identical_harper_gector_merged(self):
        """4. Identical Harper/GECToR correction remains merged: go → goes"""
        f_harper = Finding(source="harper", category="grammar", message="Agreement", original="go", replacement="goes", start=4, end=6)
        f_gector = Finding(source="gector", category="verb_form", message="Agreement", original="go", replacement="goes", start=4, end=6)
        
        resolved = self.resolver.resolve([f_harper, f_gector])
        curated = self.policy.apply(resolved)
        
        self.assertEqual(len(curated), 1)
        self.assertEqual(curated[0].replacement, "goes")
        self.assertTrue(curated[0].metadata.get("is_merged", False))
        self.assertIn("harper", curated[0].metadata["sources"])
        self.assertIn("gector", curated[0].metadata["sources"])

    def test_independent_findings_remain(self):
        """5. Independent findings remain: has → have and a → an"""
        f1 = Finding(source="harper", category="grammar", message="Agreement", original="has", replacement="have", start=2, end=5)
        f2 = Finding(source="harper", category="grammar", message="Article", original="a", replacement="an", start=6, end=7)
        
        resolved = self.resolver.resolve([f1, f2])
        curated = self.policy.apply(resolved)
        
        self.assertEqual(len(curated), 2)
        replacements = {f.original: f.replacement for f in curated}
        self.assertEqual(replacements["has"], "have")
        self.assertEqual(replacements["a"], "an")

    def test_gector_morphology_survives(self):
        """6. GECToR morphology correction survives: was → were"""
        f_gector = Finding(source="gector", category="morphology", message="Tense", original="was", replacement="were", start=12, end=15)
        
        resolved = self.resolver.resolve([f_gector])
        curated = self.policy.apply(resolved)
        
        self.assertEqual(len(curated), 1)
        self.assertEqual(curated[0].replacement, "were")
        self.assertEqual(curated[0].source, "gector")

    def test_harper_capitalization_survives(self):
        """7. Harper capitalization survives when there is no competing correction: are → Are"""
        f_harper = Finding(source="harper", category="capitalization", message="Cap", original="are", replacement="Are", start=30, end=33)
        
        resolved = self.resolver.resolve([f_harper])
        curated = self.policy.apply(resolved)
        
        self.assertEqual(len(curated), 1)
        self.assertEqual(curated[0].replacement, "Are")
        self.assertEqual(curated[0].source, "harper")

    def test_policy_determinism_regardless_of_order(self):
        """8. Policy is deterministic regardless of input finding order."""
        f_harper = Finding(source="harper", category="capitalization", message="Cap", original="whatare", replacement="Whatare", start=0, end=7)
        f_symspell = Finding(source="symspell", category="word_boundary", message="Boundary", original="whatare", replacement="what are", start=0, end=7)
        
        resolved_1 = self.resolver.resolve([f_harper, f_symspell])
        curated_1 = self.policy.apply(resolved_1)

        resolved_2 = self.resolver.resolve([f_symspell, f_harper])
        curated_2 = self.policy.apply(resolved_2)

        self.assertEqual(len(curated_1), 1)
        self.assertEqual(len(curated_2), 1)
        self.assertEqual(curated_1[0].replacement, curated_2[0].replacement)
        self.assertEqual(curated_1[0].source, curated_2[0].source)

    def test_policy_does_not_modify_finding_text_or_ranges(self):
        """9. Policy does not modify finding text/ranges itself."""
        f = Finding(source="symspell", category="word_boundary", message="Boundary", original="whatare", replacement="what are", start=10, end=17)
        resolved = self.resolver.resolve([f])
        curated = self.policy.apply(resolved)
        
        self.assertEqual(curated[0].start, 10)
        self.assertEqual(curated[0].end, 17)
        self.assertEqual(curated[0].original, "whatare")
        self.assertEqual(curated[0].replacement, "what are")

    def test_pipeline_integration(self):
        """10. Integration test showing Pipeline → Resolver → CorrectionPolicy produces expected curated findings."""
        pipeline = AnalysisPipeline()
        pipeline.register_engine(SymSpellAnalysisEngine())
        pipeline.register_engine(HarperAnalysisEngine())

        text = "Please review whatare you doing."
        raw = pipeline.analyze(text)
        resolved = self.resolver.resolve(raw)
        curated = self.policy.apply(resolved)

        # 确保精炼后无冲突残留，且保留了 symspell 的 word_boundary 替换
        for f in curated:
            self.assertFalse(f.metadata.get("has_conflict", False))
        
        word_boundary_found = any(f.replacement == "what are" for f in curated)
        self.assertTrue(word_boundary_found)
