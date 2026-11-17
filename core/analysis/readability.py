"""
G-Coach Readability & Clarity Scoring Engine (Lexicon-Style Local Metrics)
Calculates Flesch Reading Ease, Flesch-Kincaid Grade Level, and text complexity statistics locally.
"""

import re
import math
from typing import Dict, Any


class ReadabilityScorer:
    """本地可读性与清晰度评分计算引擎（Flesch Reading Ease & Grade Level）"""

    @staticmethod
    def _count_syllables(word: str) -> int:
        """估计英文单词的音节数（Syllable estimation heuristic）"""
        word = word.lower()
        if len(word) <= 3:
            return 1
        word = re.sub(r'(?:[^laeiouy]|ed|es|e)$', '', word)
        word = re.sub(r'^y', '', word)
        matches = re.findall(r'[aeiouy]{1,2}', word)
        return max(1, len(matches))

    @classmethod
    def compute_metrics(cls, text: str) -> Dict[str, Any]:
        """计算给定文本的可读性指标与清晰度评分"""
        if not text or not text.strip():
            return {
                "word_count": 0,
                "sentence_count": 0,
                "syllable_count": 0,
                "flesch_reading_ease": 100.0,
                "grade_level": 0.0,
                "reading_level_desc": "N/A",
                "clarity_score": 100,
            }

        # 1. 句子切分
        sentences = re.split(r'[.!?\n]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        sentence_count = max(1, len(sentences))

        # 2. 单词提取
        words = re.findall(r'\b[a-zA-Z]+\b', text)
        word_count = max(1, len(words))

        # 3. 音节统计
        syllable_count = sum(cls._count_syllables(w) for w in words)

        # 4. Flesch Reading Ease 公式
        # 206.835 - 1.015 * (total_words / total_sentences) - 84.6 * (total_syllables / total_words)
        words_per_sentence = word_count / sentence_count
        syllables_per_word = syllable_count / word_count

        fre = 206.835 - (1.015 * words_per_sentence) - (84.6 * syllables_per_word)
        fre = max(0.0, min(100.0, fre))

        # 5. Flesch-Kincaid Grade Level 公式
        # 0.39 * (total_words / total_sentences) + 11.8 * (total_syllables / total_words) - 15.59
        grade = (0.39 * words_per_sentence) + (11.8 * syllables_per_word) - 15.59
        grade = max(0.0, grade)

        # 6. 可读性描述分级
        if fre >= 90:
            level_desc = "Very Easy (5th grade)"
        elif fre >= 80:
            level_desc = "Very Easy (6th grade)"
        elif fre >= 70:
            level_desc = "Fairly Easy (7th grade)"
        elif fre >= 60:
            level_desc = "Standard (8th-9th grade)"
        elif fre >= 50:
            level_desc = "Fairly Difficult (High school)"
        elif fre >= 30:
            level_desc = "Difficult (College)"
        else:
            level_desc = "Very Difficult (Graduate)"

        # 7. 清晰度综合评分 (0-100)
        # 理想写作 FRE 维持在 60-70 之间；过低（过难）或过高（过于幼稚）均适当扣分
        clarity_score = int(round(fre))

        return {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "syllable_count": syllable_count,
            "flesch_reading_ease": round(fre, 1),
            "grade_level": round(grade, 1),
            "reading_level_desc": level_desc,
            "clarity_score": clarity_score,
        }
