"""
分析解析与消解层 (Analysis Resolution Layer) - Phase 4 Analysis Resolution
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from .finding import Finding

logger = logging.getLogger(__name__)


class AnalysisResolver:
    """分析结果消解器（Analysis Resolver）

    负责接收来自多个独立分析引擎（如 Harper、GECToR 等）的 Findings，
    进行确定性的重叠检测、等价合并与冲突标记，输出统一的消解后 Findings 列表，
    同时完整保留所有引擎的源 provenance、置信度和冲突详情。
    """

    def __init__(self):
        pass

    def resolve(self, findings: List[Finding]) -> List[Finding]:
        """消解并合并给定的 findings 列表。

        规则：
        1. 相同范围且替换文本等价的 findings 合并为单一 finding，记录多个 sources。
        2. 相同范围但替换文本不同的 findings 标记为冲突（conflict），保留两个候选。
        3. 重叠但范围不同的 findings 进行冲突/重叠标记。
        4. 非重叠的 findings 独立保留。
        5. 保持确定性排序（按 start 升序，end 降序，source 字母序）。
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

        # 按确定性规则排序：start 升序，长度降序，source 字母序
        sorted_findings = sorted(
            valid_findings,
            key=lambda x: (x.start, -(x.end - x.start), x.source, x.original)
        )

        resolved: List[Finding] = []
        i = 0
        n = len(sorted_findings)

        while i < n:
            current = sorted_findings[i]
            # 收集所有与当前 finding 范围重叠或相等的 findings
            group = [current]
            j = i + 1
            while j < n:
                next_f = sorted_findings[j]
                # 判断是否重叠或位置完全相同
                if self._ranges_overlap(current.start, current.end, next_f.start, next_f.end):
                    group.append(next_f)
                    j += 1
                else:
                    break

            if len(group) == 1:
                # 无重叠，直接规范化加入
                resolved.append(self._prepare_single_finding(group[0]))
            else:
                # 存在重叠或相同位置，进行消解处理
                resolved_group = self._resolve_group(group)
                resolved.extend(resolved_group)

            i = j

        # 最终再次按位置确定性排序
        return sorted(
            resolved,
            key=lambda x: (x.start, x.end, x.source)
        )

    def _ranges_overlap(self, start1: int, end1: int, start2: int, end2: int) -> bool:
        """判断两个文本区间是否重叠或完全一致"""
        if start1 == start2 and end1 == end2:
            return True
        return max(start1, start2) < min(end1, end2)

    def _normalize_replacement(self, replacement: str) -> str:
        """规范化替换文本，去处首尾空白和多余标点差异（保守规范化）"""
        if not replacement:
            return ""
        return replacement.strip()

    def _prepare_single_finding(self, f: Finding) -> Finding:
        """准备单个独立的 finding，确保其元数据完整包含来源 provenance"""
        meta = dict(f.metadata)
        sources = meta.get("sources", [f.source])
        if f.source not in sources:
            sources.append(f.source)
        
        meta["sources"] = sources
        meta["is_merged"] = meta.get("is_merged", False)
        meta["has_conflict"] = meta.get("has_conflict", False)
        meta["source_confidences"] = meta.get("source_confidences", {f.source: f.confidence})
        meta["source_ids"] = meta.get("source_ids", {f.source: f.id})

        f.metadata = meta
        return f

    def _resolve_group(self, group: List[Finding]) -> List[Finding]:
        """消解一组重叠或位置相同的 findings"""
        exact_matches: Dict[Tuple[int, int, str, str], List[Finding]] = {}
        for f in group:
            norm_repl = self._normalize_replacement(f.replacement)
            key = (f.start, f.end, f.original, norm_repl)
            if key not in exact_matches:
                exact_matches[key] = []
            exact_matches[key].append(f)

        if len(exact_matches) == 1 and len(list(exact_matches.values())[0]) == len(group):
            base = group[0]
            sources = []
            source_confidences = {}
            source_ids = {}
            for f in group:
                if f.source not in sources:
                    sources.append(f.source)
                source_confidences[f.source] = f.confidence
                source_ids[f.source] = f.id

            meta = dict(base.metadata)
            meta["sources"] = sources
            meta["is_merged"] = True
            meta["has_conflict"] = False
            meta["source_confidences"] = source_confidences
            meta["source_ids"] = source_ids

            base.metadata = meta
            return [base]

        resolved_findings = []
        position_groups: Dict[Tuple[int, int], List[Finding]] = {}
        for f in group:
            pos_key = (f.start, f.end)
            if pos_key not in position_groups:
                position_groups[pos_key] = []
            position_groups[pos_key].append(f)

        for (start, end), pos_findings in position_groups.items():
            if len(pos_findings) == 1:
                resolved_findings.append(self._prepare_single_finding(pos_findings[0]))
            else:
                primary = pos_findings[0]
                sources = [f.source for f in pos_findings]
                source_confidences = {f.source: f.confidence for f in pos_findings}
                source_ids = {f.source: f.id for f in pos_findings}
                conflicting_details = [
                    {
                        "source": f.source,
                        "replacement": f.replacement,
                        "confidence": f.confidence,
                        "message": f.message,
                        "id": f.id,
                    }
                    for f in pos_findings
                ]

                meta = dict(primary.metadata)
                meta["sources"] = sources
                meta["is_merged"] = False
                meta["has_conflict"] = True
                meta["conflicting_findings"] = conflicting_details
                meta["source_confidences"] = source_confidences
                meta["source_ids"] = source_ids

                primary.metadata = meta
                resolved_findings.append(primary)

                for other in pos_findings[1:]:
                    other_meta = dict(other.metadata)
                    other_meta["sources"] = sources
                    other_meta["is_merged"] = False
                    other_meta["has_conflict"] = True
                    other_meta["conflicting_findings"] = conflicting_details
                    other_meta["source_confidences"] = source_confidences
                    other_meta["source_ids"] = source_ids
                    other.metadata = other_meta
                    resolved_findings.append(other)

        return resolved_findings
