"""Positive/negative coverage for the shipped native prose rule library."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.analysis import AnalysisPipeline, BaseAnalysisEngine, Finding, RegexRulesAnalysisEngine
from core.correction.controller import CorrectionController


RULE_EXAMPLES = {
    # Wordiness and genuine redundancy
    "prose-redundant-basic-fundamentals": (
        "We reviewed the basic fundamentals.", "We reviewed the fundamentals.",
        "basic fundamentals", "fundamentals", "sentence",
    ),
    "prose-redundant-end-result": (
        "The end result was positive.", "The final result was positive.",
        "end result", "result", "sentence",
    ),
    "prose-redundant-completely-eliminate": (
        "We must completely eliminate the delay.", "We must reduce the delay.",
        "completely eliminate", "eliminate", "sentence",
    ),
    "prose-redundant-close-proximity": (
        "The hotel is in close proximity to the station.", "The hotel is near the station.",
        "in close proximity to", "near", "sentence",
    ),
    "prose-redundant-past-history": (
        "The report covers past history.", "The report covers history.",
        "past history", "history", "sentence",
    ),
    "prose-redundant-advance-planning": (
        "The team completed advance planning.", "The team completed planning.",
        "advance planning", "planning", "sentence",
    ),
    "prose-redundant-future-plans": (
        "We discussed our future plans.", "We discussed our plans.",
        "future plans", "plans", "sentence",
    ),
    "prose-redundant-unexpected-surprise": (
        "It was an unexpected surprise.", "It was a surprise.",
        "unexpected surprise", "surprise", "sentence",
    ),
    "prose-redundant-free-gift": (
        "The store included a free gift.", "The store included a gift.",
        "free gift", "gift", "sentence",
    ),
    "prose-redundant-added-bonus": (
        "The discount is an added bonus.", "The discount is a bonus.",
        "added bonus", "bonus", "sentence",
    ),
    "prose-redundant-new-innovation": (
        "The company announced a new innovation.", "The company announced an innovation.",
        "new innovation", "innovation", "sentence",
    ),
    "prose-redundant-final-outcome": (
        "The final outcome was unclear.", "The outcome was unclear.",
        "final outcome", "outcome", "sentence",
    ),
    "prose-redundant-actual-fact": (
        "That is an actual fact.", "That is a fact.",
        "actual fact", "fact", "sentence",
    ),
    # Preferred plain-language terminology (suggestions, not grammar errors)
    "prose-terminology-utilize": (
        "Please utilize the new form.", "Please use the new form.",
        "utilize", "use", "sentence",
    ),
    "prose-terminology-commence": (
        "The meeting will commence at noon.", "The meeting will begin at noon.",
        "commence", "begin", "sentence",
    ),
    "prose-terminology-prior-to": (
        "Prior to launch, test the system.", "Before launch, test the system.",
        "Prior to", "Before", "sentence",
    ),
    "prose-terminology-subsequent-to": (
        "Subsequent to launch, monitor the system.", "After launch, monitor the system.",
        "Subsequent to", "After", "sentence",
    ),
    "prose-terminology-endeavor-to": (
        "Endeavor to remain calm.", "Try to remain calm.",
        "Endeavor to", "Try to", "sentence",
    ),
    "prose-terminology-is-able-to": (
        "The user is able to export files.", "The user can export files.",
        "is able to", "can", "sentence",
    ),
    # Commonly confused expressions
    "prose-confused-your-invited": (
        "Your invited to the event.", "Your invitation arrived.",
        "Your invited", "You're invited", "sentence",
    ),
    "prose-confused-their-is": (
        "Their is a problem.", "Their house is nearby.",
        "Their is", "There is", "sentence",
    ),
    "prose-confused-their-are": (
        "Their are three options.", "Their cars are outside.",
        "Their are", "There are", "sentence",
    ),
    "prose-confused-more-then": (
        "There are more then ten items.", "There are more than ten items.",
        "more then", "more than", "sentence",
    ),
    "prose-confused-less-then": (
        "The result took less then a minute.", "The result took less than a minute.",
        "less then", "less than", "sentence",
    ),
    "prose-confused-loose-weight": (
        "She wants to loose weight.", "The shirt is loose.",
        "loose weight", "lose weight", "sentence",
    ),
    "prose-confused-apart-of": (
        "I am apart of the group.", "I live apart from the group.",
        "apart of", "a part of", "sentence",
    ),
    "prose-confused-suppose-to": (
        "You are suppose to call.", "You are supposed to call.",
        "suppose to", "supposed to", "sentence",
    ),
    "prose-confused-between-you-and-i": (
        "This stays between you and I.", "This stays between you and me.",
        "between you and I", "between you and me", "sentence",
    ),
    "prose-confused-one-in-the-same": (
        "They are one in the same.", "They are one and the same.",
        "one in the same", "one and the same", "sentence",
    ),
    "prose-confused-mute-point": (
        "That is a mute point.", "That is a moot point.",
        "mute point", "moot point", "sentence",
    ),
    "prose-confused-peak-my-interest": (
        "The topic may peak my interest.", "The topic may pique my interest.",
        "peak my interest", "pique my interest", "sentence",
    ),
    "prose-confused-deep-seeded": (
        "It is a deep-seeded belief.", "It is a deep-seated belief.",
        "deep-seeded", "deep-seated", "sentence",
    ),
    "prose-confused-escape-goat": (
        "They made him the escape goat.", "They made him the scapegoat.",
        "escape goat", "scapegoat", "sentence",
    ),
    "prose-confused-all-intensive-purposes": (
        "For all intensive purposes, it is done.", "For all intents and purposes, it is done.",
        "all intensive purposes", "all intents and purposes", "sentence",
    ),
    "prose-confused-first-come-first-serve": (
        "Admission is first come first serve.", "Admission is first come, first served.",
        "first come first serve", "first come, first served", "sentence",
    ),
    # Grammatical agreement and participle rules (added in Stage 8)
    "prose-grammar-modal-of": (
        "You should of done it.", "You should have done it.",
        "should of", "should have", "sentence",
    ),
    "prose-grammar-had-went": (
        "He had went home.", "He had gone home.",
        "had went", "had gone", "sentence",
    ),
    "prose-grammar-have-wrote": (
        "They have wrote a letter.", "They have written a letter.",
        "have wrote", "have written", "sentence",
    ),
    "prose-grammar-had-saw": (
        "She had saw the movie.", "She had seen the movie.",
        "had saw", "had seen", "sentence",
    ),
    # Grammatical agreement and participle rules (added in Stage 8)
    "prose-grammar-modal-of": (
        "You should of done it.", "You should have done it.",
        "should of", "should have", "sentence",
    ),
    "prose-grammar-had-went": (
        "He had went home.", "He had gone home.",
        "had went", "had gone", "sentence",
    ),
    "prose-grammar-have-wrote": (
        "They have wrote a letter.", "They have written a letter.",
        "have wrote", "have written", "sentence",
    ),
    "prose-grammar-had-saw": (
        "She had saw the movie.", "She had seen the movie.",
        "had saw", "had seen", "sentence",
    ),
    # Document-wide capitalization and terminology consistency
    "prose-capitalization-github": (
        "We host the project on github.", "We host the project on GitHub.",
        "github", "GitHub", "document",
    ),
    "prose-capitalization-javascript": (
        "The client uses javascript.", "The client uses JavaScript.",
        "javascript", "JavaScript", "document",
    ),
    "prose-capitalization-typescript": (
        "The service uses typescript.", "The service uses TypeScript.",
        "typescript", "TypeScript", "document",
    ),
    "prose-capitalization-macos": (
        "The laptop runs macos.", "The laptop runs macOS.",
        "macos", "macOS", "document",
    ),
    "prose-capitalization-iphone": (
        "She uses an iphone.", "She uses an iPhone.",
        "iphone", "iPhone", "document",
    ),
    "prose-capitalization-youtube": (
        "The clip is on youtube.", "The clip is on YouTube.",
        "youtube", "YouTube", "document",
    ),
    "prose-terminology-e-mail": (
        "Send an e-mail today.", "Send an email today.",
        "e-mail", "email", "document",
    ),
    "prose-terminology-web-site": (
        "Visit the web site today.", "Visit the website today.",
        "web site", "website", "document",
    ),
    # Repetition and punctuation/spacing
    "prose-repetition-double-pronoun-i": (
        "I I will handle it.", "I will handle it.",
        "I I", "I", "sentence",
    ),
    "prose-spacing-double-space": (
        "This has  two spaces.", "This has one space.",
        "  ", " ", "live",
    ),
    "prose-spacing-after-opening-parenthesis": (
        "The value is ( one).", "The value is (one).",
        "( ", "(", "live",
    ),
    "prose-spacing-before-closing-parenthesis": (
        "The value is (one ).", "The value is (one).",
        " )", ")", "live",
    ),
    "prose-spacing-after-comma-semicolon": (
        "We bought apples,oranges.", "We bought apples, oranges.",
        ",", ", ", "live",
    ),
    "prose-spacing-after-question-exclamation": (
        "Stop!Run now.", "Stop! Run now.",
        "!", "! ", "live",
    ),
}


class TestNativeProseRuleLibrary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RegexRulesAnalysisEngine()
        cls.rules = {rule.id: rule for rule in cls.engine._library_rules}

    def test_every_curated_rule_has_a_positive_and_negative_example(self):
        self.assertEqual(len(self.rules), len(RULE_EXAMPLES))
        self.assertEqual(set(self.rules), set(RULE_EXAMPLES))

        for rule_id, (positive, negative, expected_original, expected_replacement, scope) in RULE_EXAMPLES.items():
            with self.subTest(rule_id=rule_id, example="positive"):
                findings = self.engine.analyze_scope(positive, scope)
                matches = [f for f in findings if f.metadata.get("rule_id") == rule_id]
                self.assertEqual(len(matches), 1)
                self.assertEqual(matches[0].original, expected_original)
                self.assertEqual(matches[0].replacement, expected_replacement)
                self.assertEqual(matches[0].metadata.get("rule_scope"), scope)
                self.assertEqual(positive[matches[0].start:matches[0].end], matches[0].original)
                self.assertEqual(matches[0].category, self.rules[rule_id].category)
                self.assertEqual(matches[0].severity, self.rules[rule_id].severity)

            with self.subTest(rule_id=rule_id, example="negative"):
                findings = self.engine.analyze_scope(negative, scope)
                self.assertFalse(
                    any(f.metadata.get("rule_id") == rule_id for f in findings),
                    f"Unexpected false positive for {rule_id}: {negative!r}",
                )

    def test_scope_partition_keeps_document_rules_out_of_live_and_sentence_checks(self):
        document_ids = {rule_id for rule_id, case in RULE_EXAMPLES.items() if case[4] == "document"}
        sentence_ids = {rule_id for rule_id, case in RULE_EXAMPLES.items() if case[4] == "sentence"}
        live_ids = {rule_id for rule_id, case in RULE_EXAMPLES.items() if case[4] == "live"}

        self.assertEqual(len(document_ids), 8)
        self.assertEqual(len(sentence_ids), len([c for c in RULE_EXAMPLES.values() if c[4] == "sentence"]))
        self.assertEqual(len(live_ids), 5)
        sample = "github. Their is a problem. There are items."
        for scope, excluded in (("live", document_ids | sentence_ids), ("sentence", document_ids | live_ids), ("document", sentence_ids | live_ids)):
            findings = self.engine.analyze_scope(sample, scope)
            self.assertFalse(excluded & {f.metadata.get("rule_id") for f in findings})

    def test_case_insensitive_brand_rules_preserve_canonical_casing(self):
        text = (
            "GitHub JavaScript TypeScript macOS iPhone YouTube "
            "github javascript Github Javascript Typescript Macos Iphone Youtube"
        )
        findings = self.engine.analyze_scope(text, "document")
        actual = {
            (finding.metadata.get("rule_id"), finding.original, finding.replacement)
            for finding in findings
        }
        self.assertEqual(
            actual,
            {
                ("prose-capitalization-github", "github", "GitHub"),
                ("prose-capitalization-github", "Github", "GitHub"),
                ("prose-capitalization-javascript", "javascript", "JavaScript"),
                ("prose-capitalization-javascript", "Javascript", "JavaScript"),
                ("prose-capitalization-typescript", "Typescript", "TypeScript"),
                ("prose-capitalization-macos", "Macos", "macOS"),
                ("prose-capitalization-iphone", "Iphone", "iPhone"),
                ("prose-capitalization-youtube", "Youtube", "YouTube"),
            },
        )
        for finding in findings:
            self.assertEqual(text[finding.start:finding.end], finding.original)

    def test_unicode_and_punctuation_offsets_remain_python_character_offsets(self):
        text = "😀 Café 東京. Their is a delay. github is mentioned."
        with tempfile.TemporaryDirectory() as directory:
            pipeline = AnalysisPipeline(cache_file=str(Path(directory) / "cache.json"), enable_heavy=False)
            pipeline.register_engine(RegexRulesAnalysisEngine(
                custom_rules_path=str(Path(directory) / "no-user-rules.json")
            ))
            findings = pipeline.analyze(text)

        by_rule = {f.metadata.get("rule_id"): f for f in findings}
        for rule_id in ("prose-confused-their-is", "prose-capitalization-github"):
            finding = by_rule[rule_id]
            self.assertEqual(text[finding.start:finding.end], finding.original)
            self.assertEqual(finding.start, text.index(finding.original))

        punctuation_text = "😀Hello,world!Again"
        punctuation = self.engine.analyze_scope(punctuation_text, "live")
        for finding in punctuation:
            self.assertEqual(punctuation_text[finding.start:finding.end], finding.original)
        self.assertEqual(
            [f.metadata["rule_id"] for f in punctuation],
            ["prose-spacing-after-comma-semicolon", "prose-spacing-after-question-exclamation"],
        )

    def test_multiple_occurrences_are_all_reported(self):
        text = "The end result was clear. The end result mattered."
        findings = [
            f for f in self.engine.analyze_scope(text, "sentence")
            if f.metadata.get("rule_id") == "prose-redundant-end-result"
        ]
        self.assertEqual(len(findings), 2)
        self.assertEqual([f.start for f in findings], [text.index("end result"), text.rindex("end result")])

    def test_overlapping_alternatives_are_preserved_and_correction_controller_refuses_them(self):
        custom_yaml = """\
rules:
  - id: user-alternative-end-result
    pattern: '\\bend result\\b'
    replacement: outcome
    category: wordiness
    severity: info
    message: Alternative wording.
    scope: sentence
"""
        with tempfile.TemporaryDirectory() as directory:
            rules_path = Path(directory) / "user-rules.yaml"
            rules_path.write_text(custom_yaml, encoding="utf-8")
            engine = RegexRulesAnalysisEngine(custom_rules_path=str(rules_path))
            text = "The end result was clear."
            findings = engine.analyze_scope(text, "sentence")

        alternatives = [f for f in findings if f.original == "end result"]
        self.assertEqual(len(alternatives), 2)
        self.assertEqual({f.replacement for f in alternatives}, {"result", "outcome"})
        self.assertEqual({(f.start, f.end) for f in alternatives}, {(4, 14)})
        result = CorrectionController().apply_acceptance(text, alternatives[0], all_findings=alternatives)
        self.assertFalse(result.success)
        self.assertIn("conflicting alternative suggestions", result.error_message)

    def test_analysis_pipeline_findings_apply_through_existing_correction_workflow(self):
        text = "The end result was clear."
        with tempfile.TemporaryDirectory() as directory:
            pipeline = AnalysisPipeline(cache_file=str(Path(directory) / "cache.json"), enable_heavy=False)
            pipeline.register_engine(RegexRulesAnalysisEngine(
                custom_rules_path=str(Path(directory) / "no-user-rules.json")
            ))
            findings = pipeline.analyze(text)

        finding = next(f for f in findings if f.metadata.get("rule_id") == "prose-redundant-end-result")
        result = CorrectionController().apply_acceptance(text, finding, all_findings=findings)
        self.assertTrue(result.success, result.error_message)
        self.assertEqual(result.new_text, "The result was clear.")
        self.assertEqual(finding.status, "accepted")

    def test_batched_sentence_analysis_matches_per_sentence_results(self):
        # Exercise every curated rule's positive example through the pipeline,
        # including regex-only fallbacks, document rules and live rules.
        text = "😀 " + " ".join(example[0] for example in RULE_EXAMPLES.values()) + " 東京"
        with tempfile.TemporaryDirectory() as directory:
            custom_path = str(Path(directory) / "missing-custom-rules.json")
            batched_engine = RegexRulesAnalysisEngine(custom_rules_path=custom_path)
            batch_calls = []
            original_batch_method = batched_engine.analyze_scope_spans

            def track_batch_call(buffer, spans):
                batch_calls.append(len(spans))
                return original_batch_method(buffer, spans)

            batched_engine.analyze_scope_spans = track_batch_call
            batched_pipeline = AnalysisPipeline(
                cache_file=str(Path(directory) / "batched-cache.json"), enable_heavy=False
            )
            batched_pipeline.register_engine(batched_engine)

            reference_engine = RegexRulesAnalysisEngine(custom_rules_path=custom_path)
            # Disable only the optional batch protocol to retain the original
            # per-sentence execution path as a behavioral reference.
            reference_engine.analyze_scope_spans = None
            reference_pipeline = AnalysisPipeline(
                cache_file=str(Path(directory) / "reference-cache.json"), enable_heavy=False
            )
            reference_pipeline.register_engine(reference_engine)

            batched = batched_pipeline.analyze(text)
            reference = reference_pipeline.analyze(text)

        self.assertEqual(len(batch_calls), 1)
        self.assertGreater(batch_calls[0], 4)

        def signature(findings):
            return [
                (
                    finding.source,
                    finding.category,
                    finding.original,
                    finding.replacement,
                    finding.start,
                    finding.end,
                    finding.metadata.get("rule_id"),
                )
                for finding in findings
            ]

        self.assertEqual(signature(batched), signature(reference))
        for finding in batched:
            self.assertEqual(text[finding.start:finding.end], finding.original)

    def test_native_prose_findings_suppress_overlapping_symspell_splits(self):
        class OverlappingSymSpellEngine(BaseAnalysisEngine):
            def __init__(self):
                super().__init__(name="symspell", tier="fast")

            def analyze(self, text):
                findings = []
                for token, replacement in (
                    ("fundamentals", "fun damentals"),
                    ("iphone", "iph one"),
                ):
                    start = text.lower().index(token)
                    findings.append(Finding(
                        source=self.name,
                        category="word_boundary",
                        message="Possible joined word.",
                        original=text[start:start + len(token)],
                        replacement=replacement,
                        start=start,
                        end=start + len(token),
                    ))
                return findings

        text = "We reviewed the basic fundamentals on an iphone."
        with tempfile.TemporaryDirectory() as directory:
            pipeline = AnalysisPipeline(
                cache_file=str(Path(directory) / "cache.json"), enable_heavy=False
            )
            pipeline._save_disk_cache = lambda: None
            pipeline.register_engine(OverlappingSymSpellEngine())
            pipeline.register_engine(RegexRulesAnalysisEngine(
                custom_rules_path=str(Path(directory) / "missing.json")
            ))
            findings = pipeline.analyze(text)

        self.assertEqual(
            {(finding.source, finding.original, finding.replacement) for finding in findings},
            {
                ("regex_rules", "basic fundamentals", "fundamentals"),
                ("regex_rules", "iphone", "iPhone"),
            },
        )
        for finding in findings:
            self.assertEqual(text[finding.start:finding.end], finding.original)

    def test_custom_rules_remain_additive_to_the_shipped_library(self):
        custom_yaml = """\
rules:
  - id: user-preferred-term
    pattern: '\\bwidgetry\\b'
    replacement: widgets
    category: terminology
    message: Use the configured term.
    scope: sentence
"""
        with tempfile.TemporaryDirectory() as directory:
            rules_path = Path(directory) / "custom.yaml"
            rules_path.write_text(custom_yaml, encoding="utf-8")
            engine = RegexRulesAnalysisEngine(custom_rules_path=str(rules_path))
            findings = engine.analyze_scope("We use widgetry.", "sentence")

        ids = {f.metadata.get("rule_id") for f in findings}
        self.assertIn("user-preferred-term", ids)
        self.assertIn("prose-redundant-end-result", {r.id for r in engine._library_rules})


if __name__ == "__main__":
    unittest.main()
