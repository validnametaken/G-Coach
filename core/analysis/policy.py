"""
纠错策略与候选精炼层 (Correction Policy & Candidate Curation Layer) - Phase 8 CorrectionPolicy
"""

import logging
from typing import List, Dict, Any, Tuple
from .finding import Finding

logger = logging.getLogger(__name__)


class CorrectionPolicy:
    """纠错策略与候选精炼器（CorrectionPolicy）

    位于 AnalysisResolver 之后，负责对消解后的 Findings 列表进行精炼（Curation）。
    针对实际观察到的多引擎冲突（如 SymSpell 的 WORD_BOUNDARY 候选与 Harper 的表面大写/错误拼写候选在同一 span 上冲突），
    应用专长引擎特异性规则（Engine Specialization）进行确定性裁决。
    """

    def __init__(self):
        pass

    def apply(self, findings: List[Finding]) -> List[Finding]:
        """精炼并过滤给定的 findings 列表。

        规则：
        1. 保持非重叠（独立）的 findings 不变。
        2. 保持已由 resolver 合并的等价 findings（is_merged=True 或来源多个且替换等价）不变。
        3. 对于在相同 span 或重叠 span 产生冲突（has_conflict=True 或产生交叉重叠）的 findings：
           - 依据纠错类型（Correction Type）与引擎专长（Engine Specialization）进行确定性裁决。
           - 例如：在同一 span 上，SymSpell 的 WORD_BOUNDARY 优先于 Harper 的 CAPITALIZATION 或次优拼写替换。
        4. 返回精炼后的 curated findings 列表，保持位置确定性排序。
        """
        if not findings:
            return []

        # 确保输入全为 Finding 实例
        valid_findings: List[Finding] = []
        for f in findings:
            if isinstance(f, Finding):
                valid_findings.append(f)
            elif isinstance(f, dict):
                valid_findings.append(Finding.from_dict(f))

        if not valid_findings:
            return []

        # 按位置排序
        sorted_findings = sorted(
            valid_findings,
            key=lambda x: (x.start, -(x.end - x.start), x.source, x.original)
        )

        curated: List[Finding] = []
        i = 0
        n = len(sorted_findings)

        while i < n:
            current = sorted_findings[i]
            group = [current]
            j = i + 1
            while j < n:
                next_f = sorted_findings[j]
                if self._ranges_overlap(current.start, current.end, next_f.start, next_f.end):
                    group.append(next_f)
                    j += 1
                else:
                    break

            if len(group) == 1:
                curated.append(group[0])
            else:
                # 存在重叠或冲突组，应用策略裁决
                resolved_group = self._curate_group(group)
                curated.extend(resolved_group)

            i = j

        # 最终确定性排序
        return sorted(
            curated,
            key=lambda x: (x.start, x.end, x.source)
        )

    def _ranges_overlap(self, start1: int, end1: int, start2: int, end2: int) -> bool:
        """判断两个文本区间是否重叠或完全一致"""
        if start1 == start2 and end1 == end2:
            return True
        return max(start1, start2) < min(end1, end2)

    def _classify_correction_type(self, f: Finding) -> str:
        """识别 Finding 的纠错类型"""
        source = f.source.lower()
        category = f.category.lower()
        original = f.original
        replacement = f.replacement

        if source == "symspell" or category == "word_boundary" or (" " in replacement and len(replacement) > len(original)):
            return "WORD_BOUNDARY"

        if original.lower() == replacement.lower() and original != replacement:
            return "CAPITALIZATION"

        if category in ["subject_verb_agreement", "verb_form", "morphology", "grammar"] or source == "gector":
            return "MORPHOLOGY"

        if "punct" in category or original in [".", ",", "!", "?", ";", ":"]:
            return "PUNCTUATION"

        if len(replacement) > len(original):
            return "WORD_INSERTION"

        if len(replacement) < len(original):
            return "WORD_DELETION"

        return "SPELLING"

    def _curate_group(self, group: List[Finding]) -> List[Finding]:
        """精炼一组重叠或冲突的 findings"""
        # 如果 group 中包含已合并的 finding (is_merged=True)，或者所有 finding 的 replacement 等价，直接返回代表项
        if any(f.metadata.get("is_merged", False) for f in group):
            merged_item = next((f for f in group if f.metadata.get("is_merged", False)), group[0])
            meta = dict(merged_item.metadata)
            meta["has_conflict"] = False
            meta.pop("conflicting_findings", None)
            merged_item.metadata = meta
            return [merged_item]

        # 检查是否所有 finding 的 span 相同
        first_span = (group[0].start, group[0].end)
        all_same_span = all((f.start, f.end) == first_span for f in group)

        if all_same_span:
            # 优先检查是否存在 WORD_BOUNDARY 候选（例如 SymSpell）与 Harper 的候选冲突
            word_boundary_findings = [
                f for f in group 
                if self._classify_correction_type(f) == "WORD_BOUNDARY" or f.source == "symspell"
            ]

            if word_boundary_findings:
                chosen = word_boundary_findings[0]
                meta = dict(chosen.metadata)
                meta["has_conflict"] = False
                meta.pop("conflicting_findings", None)
                meta["curated_by_policy"] = "symspell_word_boundary_preferred"
                chosen.metadata = meta
                return [chosen]

            # 检查是否存在 GECToR 语法形态优于一般检查
            gector_findings = [f for f in group if f.source == "gector"]
            if gector_findings and len(group) > 1:
                chosen = gector_findings[0]
                meta = dict(chosen.metadata)
                meta["has_conflict"] = False
                meta.pop("conflicting_findings", None)
                meta["curated_by_policy"] = "gector_morphology_preferred"
                chosen.metadata = meta
                return [chosen]

        return group
