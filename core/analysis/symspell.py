"""
SymSpell 本地单词切分纠错引擎 - Phase 8 SymSpell Word Boundary Analysis Engine
"""

import logging
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from .finding import Finding
from .engine import BaseAnalysisEngine

logger = logging.getLogger(__name__)


class SymSpellAnalysisEngine(BaseAnalysisEngine):
    """基于 SymSpell (symspellpy) 的本地轻量级单词切分纠错引擎。

    专注于检测并纠正粘连词（如 whatare -> what are, inthe -> in the, thankyou -> thank you），
    使用纯词切分模式 (`max_dictionary_edit_distance=0`)，并严格保护缩写形式与合法单字词。
    """

    # 必须严格保护不进行切分的常见缩写与否定形式
    EXCLUDED_CONTRACTIONS = {
        "dont", "cant", "wont", "isnt", "doesnt", "didnt",
        "couldnt", "wouldnt", "shouldnt", "don't", "can't",
        "won't", "isn't", "doesn't", "didn't", "couldn't",
        "wouldn't", "shouldn't"
    }

    # 必须严格保护的合法复合单字词（防止被误切分）
    PROTECTED_WORDS = {
        "cannot", "another", "something", "whatever", "however",
        "therefore", "already", "without", "today", "inside",
        "someone", "everyone"
    }

    def __init__(self, dictionary_path: Optional[str] = None):
        super().__init__(name="symspell", version="0.1.0", is_local=True)
        self.dictionary_path = dictionary_path
        self._sym_spell = None
        self._is_loaded = False

    @property
    def supported_types(self) -> List[str]:
        return ["spelling", "grammar", "word_boundary"]

    @property
    def supports_auto_fix(self) -> bool:
        return True

    def _load_engine(self) -> bool:
        """按需懒加载 SymSpell 引擎及离线词频词典。"""
        if self._is_loaded and self._sym_spell is not None:
            return True

        try:
            from symspellpy import SymSpell

            # 初始化 SymSpell，置edit_distance=0以实现纯词切分而非拼写纠错
            self._sym_spell = SymSpell(max_dictionary_edit_distance=0, prefix_length=7)

            # 查找词典路径
            dict_path = self.dictionary_path
            if not dict_path or not os.path.exists(dict_path):
                # 优先检查项目内置的离线词典 models/symspell/frequency_dictionary_en.txt
                bundled_dict = Path(__file__).parent.parent.parent / "models" / "symspell" / "frequency_dictionary_en.txt"
                if bundled_dict.exists():
                    dict_path = str(bundled_dict)
                else:
                    # 尝试从 site-packages 中定位 symspellpy 自带的词典
                    import site
                    for site_dir in site.getsitepackages():
                        candidate = os.path.join(site_dir, "symspellpy", "frequency_dictionary_en_82_765.txt")
                        if os.path.exists(candidate):
                            dict_path = candidate
                            break

            if not dict_path or not os.path.exists(dict_path):
                logger.warning("SymSpell frequency dictionary not found. SymSpell engine operating in fallback mode.")
                return False

            self._sym_spell.load_dictionary(dict_path, term_index=0, count_index=1)
            self._is_loaded = True
            logger.info(f"Successfully loaded SymSpell engine from dictionary: {dict_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load SymSpell engine: {e}", exc_info=True)
            return False

    def analyze(self, text: str) -> List[Finding]:
        """对输入文本进行单词切分分析，检测粘连词并返回标准化的 Finding 列表。"""
        if not text or not text.strip():
            return []

        if not self._load_engine() or not self._sym_spell:
            return []

        findings: List[Finding] = []

        # 使用正则提取英文单词 token 及其精确起始位置
        # 匹配所有由英文字母组成的单词（支持带撇号如 don't，但在下面会进行严格过滤）
        token_pattern = re.compile(r"\b[A-Za-z']+\b")

        for match in token_pattern.finditer(text):
            token = match.group(0)
            start = match.start()
            end = match.end()

            token_lower = token.lower()

            # 安全规则 1: 过滤缩写/否定形式
            if token_lower in self.EXCLUDED_CONTRACTIONS:
                continue

            # 安全规则 2: 过滤合法单字词
            if token_lower in self.PROTECTED_WORDS:
                continue

            # 安全规则 3: 过滤包含撇号的 token
            if "'" in token:
                continue

            # 长度过短的单词通常不需要切分（例如 "the", "cat"）
            if len(token) < 4:
                continue

            try:
                # 执行 SymSpell 纯词切分 (max_edit_distance=0)
                result = self._sym_spell.word_segmentation(token_lower)
                segmented = result.segmented_string

                # 检查是否成功切分出多个单词（即 segmented 中包含空格，且距离和有效）
                if segmented and " " in segmented and result.distance_sum >= 1:
                    # 确保切分出来的词不仅仅是把整个词原封不动返回
                    if segmented.replace(" ", "") == token_lower:
                        parts = segmented.split(" ")

                        # 保守候选过滤规则 (Conservative candidate filtering):
                        # 1. 限制切分出的组件数量最多为 2（防止长单词如 finished -> f in i she d 被过度拆解为多个碎片）
                        if len(parts) != 2:
                            continue

                        # 2. 检查单字碎片：只允许 "a" 或 "i" 作为单字符组件（如 "a lot" 中的 "a"），其余碎片长度必须 >= 2
                        valid_parts = True
                        for part in parts:
                            if len(part) < 2 and part not in {"a", "i"}:
                                valid_parts = False
                                break
                        if not valid_parts:
                            continue

                        # 3. 如果原 token 本身是词典中的合法单词（且不在已知的高频粘连词白名单中），则不予拆分
                        KNOWN_JOINED_WORDS = {
                            "whatare", "howare", "didyou", "inthe", "onthe",
                            "thankyou", "goodmorning", "alot", "youare", "whatdo"
                        }
                        if token_lower in self._sym_spell.words and token_lower not in KNOWN_JOINED_WORDS:
                            continue

                        # 保持原始大小写（例如 Thankyou -> Thank you, WHATARE -> What are）
                        replacement = self._preserve_capitalization(token, segmented)

                        if replacement.lower() != token.lower():
                            finding = Finding(
                                source="symspell",
                                category="word_boundary",
                                message=f"Missing word boundary detected: consider changing '{token}' to '{replacement}'.",
                                original=token,
                                replacement=replacement,
                                start=start,
                                end=end,
                                confidence=0.95,
                                severity="error",
                                auto_fixable=True,
                                metadata={
                                    "symspell_segmentation": True,
                                    "distance_sum": result.distance_sum,
                                    "log_prob_sum": result.log_prob_sum,
                                },
                            )
                            findings.append(finding)
            except Exception as e:
                logger.debug(f"Error during SymSpell segmentation for token '{token}': {e}")

        findings.sort(key=lambda f: f.start)
        return findings

    def _preserve_capitalization(self, original: str, segmented: str) -> str:
        """根据原 token 的大小写风格调整切分后字符串的大小写。"""
        if not original or not segmented:
            return segmented

        # 全大写
        if original.isupper():
            return segmented.upper()

        # 首字母大写 (Title case)
        if original[0].isupper():
            parts = segmented.split(" ")
            if parts:
                parts[0] = parts[0].capitalize()
                return " ".join(parts)

        return segmented
