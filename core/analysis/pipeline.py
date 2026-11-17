"""
分析协调器/管道 (Pipeline) - Phase 1 Unified Analysis Foundation & Phase 8F Personal Dictionary
"""

import logging
import os
import json
from typing import List, Dict, Any, Optional
from .finding import Finding
from .engine import BaseAnalysisEngine
from core.dictionary import PersonalDictionary

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """分析管道（Coordinator）

    管理多个独立的分析引擎，接收文本并发起分析，
    汇总并返回统一的标准 Findings 列表。
    """

    def __init__(self, dictionary: Optional[PersonalDictionary] = None, cache_file: Optional[str] = None, enable_fast: bool = True, enable_heavy: bool = True):
        self._engines: Dict[str, BaseAnalysisEngine] = {}
        self.dictionary = dictionary or PersonalDictionary()
        self.enable_fast = enable_fast
        self.enable_heavy = enable_heavy
        self._cache: Dict[str, List[Finding]] = {}
        self._cache_max_size = 256
        self.cache_file = cache_file or os.path.join(os.path.expanduser("~"), ".gcoach_analysis_cache.json")
        self._load_disk_cache()

    def _load_disk_cache(self) -> None:
        """从磁盘加载持久化分析缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for k, findings_list in data.items():
                            deserialized = []
                            for item in findings_list:
                                if isinstance(item, dict):
                                    deserialized.append(Finding.from_dict(item))
                            self._cache[k] = deserialized
                logger.debug("Loaded %d items from persistent analysis cache.", len(self._cache))
        except Exception as exc:
            logger.debug("Failed to load persistent analysis cache: %s", exc)

    def _save_disk_cache(self) -> None:
        """将内存缓存持久化保存到磁盘"""
        try:
            data = {}
            for k, findings in self._cache.items():
                data[str(k)] = [f.to_dict() for f in findings]
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as exc:
            logger.debug("Failed to save persistent analysis cache: %s", exc)

    def register_engine(self, engine: BaseAnalysisEngine) -> None:
        """注册一个分析引擎"""
        if not isinstance(engine, BaseAnalysisEngine):
            raise TypeError("Engine must inherit from BaseAnalysisEngine")
        self._engines[engine.name] = engine
        logger.info(f"Registered analysis engine: {engine.name} (v{engine.version})")

    def unregister_engine(self, name: str) -> Optional[BaseAnalysisEngine]:
        """注销一个分析引擎"""
        engine = self._engines.pop(name, None)
        if engine:
            logger.info(f"Unregistered analysis engine: {name}")
        return engine

    def get_engine(self, name: str) -> Optional[BaseAnalysisEngine]:
        """获取指定名称的引擎"""
        return self._engines.get(name)

    def list_engines(self) -> List[str]:
        """列出所有已注册的引擎名称"""
        return list(self._engines.keys())

    def analyze(self, text: str) -> List[Finding]:
        """Run fast and heavy engines while preserving offsets into the original text.

        Scope-aware fast engines run live rules against the current text buffer,
        sentence rules against individual sentence spans, and document rules once
        against the complete buffer. Sentence spans retain their original start
        offsets, including whitespace skipped between sentence chunks.
        """
        if not text:
            return []

        text_key = str(hash(text))
        if text_key in self._cache:
            logger.debug("Analysis pipeline full text cache hit for hash %s", text_key)
            return list(self._cache[text_key])

        import re

        # Keep delimiter whitespace out of sentence analysis without losing its
        # length when mapping local findings back to the source document.
        sentence_pattern = re.compile(r'(?<=[.!?\n])\s+')
        sentence_spans = []
        sentence_start = 0
        for separator in sentence_pattern.finditer(text):
            sentence_end = separator.start()
            if sentence_end > sentence_start:
                sentence_spans.append((sentence_start, sentence_end, text[sentence_start:sentence_end]))
            sentence_start = separator.end()
        if sentence_start < len(text):
            sentence_spans.append((sentence_start, len(text), text[sentence_start:]))
        if not sentence_spans and text.strip():
            sentence_spans.append((0, len(text), text))

        fast_engines = [
            (name, engine) for name, engine in self._engines.items()
            if getattr(engine, "tier", "heavy") == "fast"
        ]
        heavy_engines = [
            (name, engine) for name, engine in self._engines.items()
            if getattr(engine, "tier", "heavy") != "fast"
        ]
        all_findings: List[Finding] = []

        def coerce_findings(raw_findings, engine_name: str, buffer_length: int) -> List[Finding]:
            valid: List[Finding] = []
            for raw_finding in raw_findings or []:
                try:
                    finding = (
                        raw_finding if isinstance(raw_finding, Finding)
                        else Finding.from_dict(raw_finding)
                    )
                except (TypeError, ValueError, KeyError) as exc:
                    logger.warning("Ignoring invalid finding from engine '%s': %s", engine_name, exc)
                    continue
                if not (0 <= finding.start <= finding.end <= buffer_length):
                    logger.warning(
                        "Ignoring out-of-range finding from engine '%s': %s-%s for %s characters",
                        engine_name, finding.start, finding.end, buffer_length,
                    )
                    continue
                valid.append(finding)
            return valid

        def keep_finding(finding: Finding, buffer: str) -> bool:
            span_text = buffer[finding.start:finding.end]
            if self.dictionary.contains(finding.original) or (
                span_text and span_text != finding.original and self.dictionary.contains(span_text)
            ):
                logger.debug("Suppressing a personal-dictionary finding from source %s.", finding.source)
                return False
            return True

        # Live and document rules need the complete current buffer to evaluate
        # their configured context. Their offsets are already document offsets.
        if self.enable_fast:
            for name, engine in fast_engines:
                analyze_scope = getattr(engine, "analyze_scope", None)
                if not callable(analyze_scope):
                    continue
                for scope in ("live", "document"):
                    try:
                        scoped = coerce_findings(analyze_scope(text, scope), name, len(text))
                        all_findings.extend(finding for finding in scoped if keep_finding(finding, text))
                    except Exception as exc:
                        logger.error(
                            "Error running %s-scope fast analysis engine '%s': %s",
                            scope, name, exc, exc_info=True,
                        )

        # Preserve the sentence-level cache for small edits, but batch the
        # literal prose rules when most of a document is uncached. This avoids
        # invoking dozens of regex patterns once for every sentence in a full
        # document while still reusing unchanged sentence results afterwards.
        uncached_spans: list[tuple[int, int, int]] = []
        sentence_lengths: dict[int, int] = {}
        uncached_chars = 0
        for sentence_index, (sentence_start, sentence_end, sentence) in enumerate(sentence_spans):
            if not sentence.strip():
                continue
            sentence_key = str(hash(sentence))
            if sentence_key not in self._cache:
                uncached_spans.append((sentence_index, sentence_start, sentence_end))
                sentence_lengths[sentence_index] = len(sentence)
                uncached_chars += sentence_end - sentence_start

        batched_fast_findings: Dict[int, List[Finding]] = {}
        batched_engine_names: set[str] = set()
        should_batch_sentences = (
            len(uncached_spans) >= 4
            and uncached_chars >= max(1, int(len(text) * 0.20))
        )
        if self.enable_fast and should_batch_sentences:
            for name, engine in fast_engines:
                analyze_spans = getattr(engine, "analyze_scope_spans", None)
                if not callable(analyze_spans):
                    continue
                try:
                    raw_by_sentence = analyze_spans(text, uncached_spans)
                    expected_indices = {index for index, _, _ in uncached_spans}
                    if not isinstance(raw_by_sentence, dict) or set(raw_by_sentence) != expected_indices:
                        raise ValueError(
                            "Batched sentence analysis must return one result list per requested span"
                        )
                    engine_findings: Dict[int, List[Finding]] = {}
                    for sentence_index, raw in (raw_by_sentence or {}).items():
                        valid = coerce_findings(
                            raw, name, len(text)
                        )
                        if valid:
                            engine_findings[sentence_index] = valid
                    for sentence_index, valid in engine_findings.items():
                        batched_fast_findings.setdefault(sentence_index, []).extend(valid)
                    batched_engine_names.add(name)
                except Exception as exc:
                    logger.error(
                        "Error running batched sentence analysis engine '%s': %s",
                        name, exc, exc_info=True,
                    )

        for sentence_index, (sentence_start, _sentence_end, sentence) in enumerate(sentence_spans):
            if not sentence.strip():
                continue

            sent_key = str(hash(sentence))
            sent_findings = self._cache.get(sent_key)

            if sent_findings is None:
                sent_raw_findings: List[Finding] = list(
                    batched_fast_findings.get(sentence_index, [])
                )
                covered_spans = set()

                if self.enable_fast:
                    for name, engine in fast_engines:
                        if name in batched_engine_names:
                            continue
                        try:
                            analyze_scope = getattr(engine, "analyze_scope", None)
                            raw = (
                                analyze_scope(sentence, "sentence")
                                if callable(analyze_scope)
                                else engine.analyze(sentence)
                            )
                            for finding in coerce_findings(raw, name, len(sentence)):
                                sent_raw_findings.append(finding)
                                # Only spelling and boundary corrections can provide
                                # useful coverage for short-circuiting heavy grammar.
                                if finding.category in {"spelling", "word_boundary"}:
                                    covered_spans.update(range(finding.start, finding.end))
                        except Exception as exc:
                            logger.error(
                                "Error running fast analysis engine '%s' on sentence chunk: %s",
                                name, exc, exc_info=True,
                            )

                # Native prose rules are phrase-aware. When SymSpell splits a
                # token inside one of those accepted phrase/capitalization
                # spans (for example "basic fundamentals" -> "fundamentals"),
                # its overlapping word-boundary alternative is a duplicate or
                # a false split. Keep the higher-context prose finding and
                # recompute spelling coverage from the remaining fast results.
                native_prose_spans = [
                    (finding.start, finding.end)
                    for finding in sent_raw_findings
                    if finding.source == "regex_rules"
                    and str(finding.metadata.get("rule_id", "")).startswith("prose-")
                ]
                if native_prose_spans:
                    sent_raw_findings = [
                        finding for finding in sent_raw_findings
                        if not (
                            finding.source == "symspell"
                            and finding.category == "word_boundary"
                            and any(
                                max(finding.start, start) < min(finding.end, end)
                                for start, end in native_prose_spans
                            )
                        )
                    ]
                    covered_spans = set()
                    for finding in sent_raw_findings:
                        if finding.category in {"spelling", "word_boundary"}:
                            covered_spans.update(range(finding.start, finding.end))

                # The common path (no fast spelling/boundary findings) does
                # not need two full sentence scans just to calculate a zero
                # coverage ratio.
                if covered_spans:
                    non_ws_len = sum(1 for char in sentence if not char.isspace())
                    covered_non_ws = sum(
                        1 for index in covered_spans
                        if index < len(sentence) and not sentence[index].isspace()
                    )
                    coverage_ratio = covered_non_ws / non_ws_len if non_ws_len else 0.0
                else:
                    coverage_ratio = 0.0
                has_short_circuit_finding = bool(covered_spans)
                should_skip_heavy = (
                    not self.enable_heavy
                    or coverage_ratio > 0.75
                    or (len(sentence.strip()) < 15 and has_short_circuit_finding)
                )

                if not should_skip_heavy:
                    for name, engine in heavy_engines:
                        try:
                            raw = engine.analyze(sentence)
                            for finding in coerce_findings(raw, name, len(sentence)):
                                overlap = any(
                                    index in covered_spans
                                    for index in range(finding.start, finding.end)
                                )
                                if overlap and finding.category in {"spelling", "word_boundary"}:
                                    continue
                                sent_raw_findings.append(finding)
                        except Exception as exc:
                            logger.error(
                                "Error running heavy analysis engine '%s' on sentence chunk: %s",
                                name, exc, exc_info=True,
                            )

                sent_findings = [
                    finding for finding in sent_raw_findings if keep_finding(finding, sentence)
                ]
                self._cache[sent_key] = sent_findings

            for finding in sent_findings:
                all_findings.append(Finding(
                    id=finding.id,
                    source=finding.source,
                    category=finding.category,
                    message=finding.message,
                    original=finding.original,
                    replacement=finding.replacement,
                    start=finding.start + sentence_start,
                    end=finding.end + sentence_start,
                    confidence=finding.confidence,
                    severity=finding.severity,
                    auto_fixable=finding.auto_fixable,
                    status=finding.status,
                    metadata=dict(finding.metadata),
                ))

        # Document-scope native prose rules are produced outside the sentence
        # loop, so apply the same overlap rule once more across the final
        # document-level result set (including live/document findings).
        document_native_spans = [
            (finding.start, finding.end)
            for finding in all_findings
            if finding.source == "regex_rules"
            and str(finding.metadata.get("rule_id", "")).startswith("prose-")
        ]
        if document_native_spans:
            all_findings = [
                finding for finding in all_findings
                if not (
                    finding.source == "symspell"
                    and finding.category == "word_boundary"
                    and any(
                        max(finding.start, start) < min(finding.end, end)
                        for start, end in document_native_spans
                    )
                )
            ]

        all_findings.sort(key=lambda finding: (finding.start, finding.end, finding.source))

        if len(self._cache) >= self._cache_max_size:
            try:
                self._cache.pop(next(iter(self._cache)))
            except (StopIteration, KeyError):
                self._cache.clear()
        self._cache[text_key] = all_findings
        self._save_disk_cache()
        return all_findings
