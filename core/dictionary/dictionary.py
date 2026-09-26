"""
Personal Dictionary (个人词典) - Phase 8F
Manages user-added valid vocabulary (names, places, organizations, product names, etc.)
to prevent false findings from local analysis engines.
"""

import json
import logging
from pathlib import Path
from typing import List, Set, Optional, Any

logger = logging.getLogger(__name__)


class PersonalDictionary:
    """个人词典 (Personal Dictionary)

    用于存储和管理用户自定义的合法词汇（如人名 Ichinomiya、地名 Nagoya、
    组织/产品名 OpenAI 等），在分析管道中作为共享词汇层过滤不当误报，
    同时保持对相邻文本及其他独立语法错误的完整检测。
    """

    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = Path.home() / ".ai_prompt_optimizer" / "dictionary.json"
        
        self._words: Set[str] = set()
        self._load()

    def _load(self):
        """从本地持久化文件加载词典数据"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    words_list = data.get("words", [])
                    if isinstance(words_list, list):
                        for w in words_list:
                            if isinstance(w, str) and w.strip():
                                self._words.add(w.strip())
            except Exception as e:
                logger.error(f"Failed to load personal dictionary from {self.storage_path}: {e}")

    def save(self):
        """将词典数据持久化到本地文件"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {"words": sorted(list(self._words))}
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save personal dictionary to {self.storage_path}: {e}")

    def add_word(self, word: str) -> bool:
        """添加一个单词到个人词典中。如果为空或空白则安全忽略并返回 False。"""
        if not word or not isinstance(word, str):
            return False
        cleaned = word.strip()
        if not cleaned:
            return False
        
        if cleaned not in self._words:
            self._words.add(cleaned)
            self.save()
            return True
        return False

    def remove_word(self, word: str) -> bool:
        """从个人词典中移除一个单词。"""
        if not word or not isinstance(word, str):
            return False
        cleaned = word.strip()
        if cleaned in self._words:
            self._words.remove(cleaned)
            self.save()
            return True
        return False

    def contains(self, word: str) -> bool:
        """检查单词是否存在于个人词典中（支持大小写感知及常用大小写变体匹配）。"""
        if not word or not isinstance(word, str):
            return False
        cleaned = word.strip()
        if not cleaned:
            return False

        # 1. 精确匹配
        if cleaned in self._words:
            return True

        # 2. 大小写不敏感及变体匹配（如 Ichinomiya, ichinomiya, ICHINOMIYA, OpenAI）
        cleaned_lower = cleaned.lower()
        for w in self._words:
            if w.lower() == cleaned_lower:
                return True
            if w.capitalize() == cleaned or w.upper() == cleaned or w.lower() == cleaned:
                return True

        return False

    def words(self) -> List[str]:
        """返回词典中所有单词的排序列表。"""
        return sorted(list(self._words))


def is_dictionary_candidate(finding: Any) -> bool:
    """判断一个 Finding 是否适合提供 'Add to dictionary' 操作（保守策略）。

    规则：
    - 有有效替换文本的普通纠错（如 was->were, go->goes, whatare->what are, a->an）不是词典候选。
    - 标点符号不是词典候选。
    - 仅当 Finding 的类别明确指示为拼写错误、未知词、词汇或专有名词（如 category 包含 spelling, unknown, vocabulary, name, spell）且无有效替换时，才是词典候选。
    - 不再将 source == 'harper' 作为独立候选原因。
    """
    if not finding or not getattr(finding, "original", None):
        return False
    
    replacement = getattr(finding, "replacement", "")
    if replacement and replacement.strip():
        return False

    category = str(getattr(finding, "category", "")).lower()
    original = str(getattr(finding, "original", ""))

    if "punct" in category or original in [".", ",", "!", "?", ";", ":"]:
        return False

    if category in ["spelling", "unknown", "vocabulary", "name", "spell"]:
        return True

    return False

