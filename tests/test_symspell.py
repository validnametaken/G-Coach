"""
Unit tests for SymSpell Word Segmentation Analysis Engine (SymSpellAnalysisEngine)
"""

import time
import unittest
from core.analysis import SymSpellAnalysisEngine, AnalysisPipeline


class TestSymSpellAnalysisEngine(unittest.TestCase):
    """测试 SymSpellAnalysisEngine 的各项切分功能、安全性保护、句式边界对齐与性能表现"""

    @classmethod
    def setUpClass(cls):
        cls.engine = SymSpellAnalysisEngine()

    def test_engine_metadata(self):
        self.assertEqual(self.engine.name, "symspell")
        self.assertEqual(self.engine.version, "0.1.0")
        self.assertTrue(self.engine.is_local)
        self.assertTrue(self.engine.supports_auto_fix)
        self.assertIn("word_boundary", self.engine.supported_types)

        meta = self.engine.get_metadata()
        self.assertEqual(meta["name"], "symspell")
        self.assertTrue(meta["is_local"])

    def test_empty_and_whitespace_text(self):
        self.assertEqual(self.engine.analyze(""), [])
        self.assertEqual(self.engine.analyze("   \n\t "), [])

    def test_positive_joined_word_cases(self):
        """测试各项正面粘连词切分用例"""
        test_mappings = [
            ("whatare", "what are"),
            ("howare", "how are"),
            ("didyou", "did you"),
            ("inthe", "in the"),
            ("onthe", "on the"),
            ("thankyou", "thank you"),
            ("goodmorning", "good morning"),
            ("alot", "a lot"),
            ("youare", "you are"),
            ("whatdo", "what do"),
        ]

        for orig, expected in test_mappings:
            with self.subTest(orig=orig):
                findings = self.engine.analyze(orig)
                self.assertGreaterEqual(len(findings), 1, f"Expected finding for '{orig}'")
                f = findings[0]
                self.assertEqual(f.original, orig)
                self.assertEqual(f.replacement, expected)
                self.assertEqual(f.source, "symspell")
                self.assertEqual(f.category, "word_boundary")
                self.assertTrue(f.metadata.get("symspell_segmentation"))

    def test_negative_and_protection_cases(self):
        """测试否定形式、缩写以及合法单字词的保护（绝不产生切分）"""
        protected_words = [
            "dont", "cant", "wont", "isnt", "doesnt", "didnt",
            "couldnt", "wouldnt", "shouldnt", "cannot", "another",
            "something", "whatever", "however", "therefore", "already",
            "without", "today", "inside", "someone", "everyone",
            "waiting", "outside", "finished", "about", "your"
        ]

        for word in protected_words:
            with self.subTest(word=word):
                findings = self.engine.analyze(word)
                self.assertEqual(
                    len(findings), 0,
                    f"Protected/legitimate word '{word}' should not generate any SymSpell finding, but got: {findings}"
                )

    def test_sentence_and_span_alignment(self):
        """测试复杂句子中的边界对齐、跨词提取、标点符号排除及大小写保持"""
        sentences = [
            ("I think whatare you doing today?", "whatare", "what are"),
            ("Please put it inthe box.", "inthe", "in the"),
            ("Thankyou for your help.", "Thankyou", "Thank you"),
            ("Goodmorning everyone.", "Goodmorning", "Good morning"),
        ]

        for sent, expected_orig, expected_repl in sentences:
            with self.subTest(sent=sent):
                findings = self.engine.analyze(sent)
                self.assertGreaterEqual(len(findings), 1, f"Expected finding in sentence: '{sent}'")
                
                # 寻找对应目标 finding
                matching = [f for f in findings if f.original.lower() == expected_orig.lower()]
                self.assertGreaterEqual(len(matching), 1, f"Expected finding for '{expected_orig}' in '{sent}'")
                
                f = matching[0]
                self.assertEqual(f.original, expected_orig)
                self.assertEqual(f.replacement, expected_repl)
                
                # 验证切分 span 仅覆盖单词本身，不包含 surrounding spaces 或句号/问号
                extracted_slice = sent[f.start:f.end]
                self.assertEqual(extracted_slice, expected_orig)
                self.assertNotIn(".", extracted_slice)
                self.assertNotIn("?", extracted_slice)
                self.assertNotIn(" ", extracted_slice)

    def test_pipeline_coexistence(self):
        """测试 SymSpell 与现有分析管道（Pipeline）的共存，不改变解析器策略"""
        pipeline = AnalysisPipeline()
        pipeline.register_engine(self.engine)

        text = "Please put it inthe box."
        findings = pipeline.analyze(text)
        self.assertGreaterEqual(len(findings), 1)
        sources = {f.source for f in findings}
        self.assertIn("symspell", sources)

    def test_performance_measurement(self):
        """测试 SymSpell 引擎在正常句子与粘连词句子上的运行耗时，验证其在 Windows 上的极速瞬时表现"""
        normal_sent = "The students were very happy and completed their work today."
        joined_sent = "I think whatare you doing today, and please put it inthe box for goodmorning everyone."

        # 预热
        self.engine.analyze(normal_sent)

        start_normal = time.time()
        findings_normal = self.engine.analyze(normal_sent)
        duration_normal = (time.time() - start_normal) * 1000

        start_joined = time.time()
        findings_joined = self.engine.analyze(joined_sent)
        duration_joined = (time.time() - start_joined) * 1000

        print(f"\n[Performance Benchmark] SymSpell normal sentence ({len(normal_sent)} chars): {duration_normal:.2f} ms (findings: {len(findings_normal)})")
        print(f"[Performance Benchmark] SymSpell joined sentence ({len(joined_sent)} chars): {duration_joined:.2f} ms (findings: {len(findings_joined)})")

        self.assertLess(duration_normal, 100.0, "SymSpell analysis on normal text should be extremely fast (< 100ms)")
        self.assertLess(duration_joined, 100.0, "SymSpell analysis on joined text should be extremely fast (< 100ms)")


if __name__ == "__main__":
    unittest.main()
