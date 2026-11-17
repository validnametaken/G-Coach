"""
Unit tests for CustomRuleLoader and RegexRulesAnalysisEngine integration
"""

import unittest
import os
import tempfile
import json
from pathlib import Path
from core.analysis import RegexRulesAnalysisEngine, CustomRuleLoader


class TestCustomRules(unittest.TestCase):
    """测试自定义规则加载与引擎集成 (CustomRuleLoader)"""

    def test_custom_rule_loading_and_execution(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8") as tmp:
            custom_data = [
                {
                    "pattern": "\\bfoo\\b",
                    "replacement": "bar",
                    "style": "style",
                    "message": "Replace foo with bar."
                }
            ]
            json.dump(custom_data, tmp)
            tmp_name = tmp.name

        try:
            engine = RegexRulesAnalysisEngine(custom_rules_path=tmp_name)
            findings = engine.analyze("This is a foo test.")
            
            # Should find at least the custom rule finding for 'foo' -> 'bar'
            custom_findings = [f for f in findings if f.original.lower() == "foo"]
            self.assertGreaterEqual(len(custom_findings), 1)
            self.assertEqual(custom_findings[0].replacement, "bar")
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)

    def test_yaml_rule_loading_validation_profiles_and_stable_ids(self):
        yaml_text = """\
rules:
  - id: academic-teh
    pattern: '\\bteh\\b'
    replacement: the
    category: spelling
    severity: error
    message: Correct the spelling.
    profiles: [academic]
    scope: sentence
"""
        with tempfile.TemporaryDirectory() as directory:
            rules_path = Path(directory) / "rules.yaml"
            rules_path.write_text(yaml_text, encoding="utf-8")

            loader = CustomRuleLoader(rules_path)
            first_load = loader.load_rules()
            second_load = loader.load_rules()
            self.assertEqual(len(first_load), 1)
            self.assertEqual(first_load[0].id, "academic-teh")
            self.assertEqual(first_load[0].id, second_load[0].id)

            default_engine = RegexRulesAnalysisEngine(custom_rules_path=str(rules_path))
            academic_engine = RegexRulesAnalysisEngine(
                custom_rules_path=str(rules_path), profiles="academic"
            )
            self.assertFalse(any(f.metadata.get("rule_id") == "academic-teh"
                                 for f in default_engine.analyze("Please fix teh.")))
            findings = academic_engine.analyze("Please fix teh.")
            custom = next(f for f in findings if f.metadata.get("rule_id") == "academic-teh")
            self.assertEqual(custom.replacement, "the")
            self.assertEqual(custom.severity, "error")
            self.assertEqual(custom.category, "spelling")

    def test_invalid_yaml_rules_are_skipped_and_reported(self):
        yaml_text = """\
rules:
  - id: valid
    pattern: 'teh'
    replacement: the
    message: Fix typo.
  - id: bad-pattern
    pattern: '['
    replacement: x
    message: Invalid regex.
  - id: bad-severity
    pattern: 'foo'
    replacement: bar
    severity: urgent
    message: Invalid severity.
  - id: missing-message
    pattern: 'baz'
    message: ''
  - id: bad-replacement
    pattern: 'foo'
    replacement: '\\g<missing>'
    message: Invalid replacement reference.
"""
        with tempfile.TemporaryDirectory() as directory:
            rules_path = Path(directory) / "invalid.yaml"
            rules_path.write_text(yaml_text, encoding="utf-8")
            loader = CustomRuleLoader(rules_path)
            rules = loader.load_rules()

        self.assertEqual([rule.id for rule in rules], ["valid"])
        self.assertEqual(len(loader.errors), 4)

    def test_generated_rule_ids_are_stable(self):
        yaml_text = """\
rules:
  - pattern: 'teh'
    replacement: the
    category: spelling
    message: Correct the typo.
"""
        with tempfile.TemporaryDirectory() as directory:
            rules_path = Path(directory) / "stable.yaml"
            rules_path.write_text(yaml_text, encoding="utf-8")
            first_id = CustomRuleLoader(rules_path).load_rules()[0].id
            second_id = CustomRuleLoader(rules_path).load_rules()[0].id

        self.assertEqual(first_id, second_id)
        self.assertTrue(first_id.startswith("rule-"))

    def test_yaml_safe_loader_rejects_python_object_constructors(self):
        with tempfile.TemporaryDirectory() as directory:
            rules_path = Path(directory) / "unsafe.yaml"
            rules_path.write_text(
                "!!python/object/apply:builtins.print ['must not execute']", encoding="utf-8"
            )
            loader = CustomRuleLoader(rules_path)
            self.assertEqual(loader.load_rules(), [])
            self.assertTrue(loader.errors)

    def test_scope_specific_execution(self):
        yaml_text = """\
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
            rules_path = Path(directory) / "scopes.yml"
            rules_path.write_text(yaml_text, encoding="utf-8")
            engine = RegexRulesAnalysisEngine(custom_rules_path=str(rules_path))
            self.assertEqual(
                [f.metadata["rule_id"] for f in engine.analyze_scope("live word document", "live")],
                ["live-rule"],
            )
            self.assertEqual(
                [f.metadata["rule_id"] for f in engine.analyze_scope("live word document", "sentence")],
                ["sentence-rule"],
            )
            self.assertEqual(
                [f.metadata["rule_id"] for f in engine.analyze_scope("live word document", "document")],
                ["document-rule"],
            )
            all_findings = engine.analyze("live word document")
            self.assertEqual(len(all_findings), 3)


if __name__ == "__main__":
    unittest.main()
