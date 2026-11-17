"""
Unit tests for ReadabilityScorer (Lexicon-Style Local Readability & Clarity Metrics)
"""

import unittest
from core.analysis import ReadabilityScorer


class TestReadabilityScorer(unittest.TestCase):
    """测试可读性与清晰度评分计算器 (ReadabilityScorer)"""

    def test_empty_text(self):
        metrics = ReadabilityScorer.compute_metrics("")
        self.assertEqual(metrics["word_count"], 0)
        self.assertEqual(metrics["flesch_reading_ease"], 100.0)

    def test_simple_text(self):
        text = "The cat sat on the mat. The dog ran fast."
        metrics = ReadabilityScorer.compute_metrics(text)
        self.assertGreater(metrics["word_count"], 0)
        self.assertEqual(metrics["sentence_count"], 2)
        self.assertGreaterEqual(metrics["flesch_reading_ease"], 0.0)
        self.assertLessEqual(metrics["flesch_reading_ease"], 100.0)
        self.assertIsInstance(metrics["reading_level_desc"], str)
        self.assertIsInstance(metrics["clarity_score"], int)


if __name__ == "__main__":
    unittest.main()
