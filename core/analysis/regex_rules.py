"""
OpenGrammar-style Fast Regex & Heuristic Rules Engine (Phase 8 Fast Supplement)
Provides lightning-fast offline regex pattern matching for common typos, duplicate word repetitions,
and wordy phrasing before heavy parsing/neural engines run.
"""

import json
import logging
import re
from bisect import bisect_right
from pathlib import Path
from typing import Any, Iterable, List, Pattern, Tuple
from .finding import Finding
from .engine import BaseAnalysisEngine
from .custom_rules import CompiledRule, CustomRuleLoader, compile_rule

try:
    import yaml as _yaml
except Exception:  # pragma: no cover - yaml is a declared dependency
    _yaml = None

COMMON_CONSISTENCY_WORDS = frozenset({
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
    "her", "was", "one", "our", "out", "day", "get", "has", "him", "his",
    "how", "man", "new", "now", "old", "see", "two", "way", "who", "boy",
    "did", "its", "let", "put", "say", "she", "too", "use", "this", "that",
    "with", "have", "from", "they", "know", "want", "been", "good", "much",
    "some", "time", "very", "when", "come", "here", "just", "like", "long",
    "make", "many", "more", "only", "over", "such", "take", "than", "them",
    "well", "were", "will", "would", "there", "their", "what", "which",
    "about", "could", "other", "after", "first", "never", "these", "think",
    "where", "being", "every", "great", "might", "shall", "still", "those",
    "while", "should", "before", "between", "through", "during", "without",
    "under", "above", "below", "again", "further", "then", "once", "here",
    "there", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "can", "will", "just", "don", "should", "now",
})

BRITISH_AMERICAN_PAIRS = [
    ("colour", "color"), ("colours", "colors"), ("coloured", "colored"),
    ("colouring", "coloring"), ("colourful", "colorful"),
    ("organise", "organize"), ("organised", "organized"), ("organising", "organizing"),
    ("organisation", "organization"), ("organisations", "organizations"),
    ("centre", "center"), ("centres", "centers"), ("centralise", "centralize"),
    ("centralised", "centralized"), ("centralising", "centralizing"),
    ("analyse", "analyze"), ("analysed", "analyzed"), ("analysing", "analyzing"),
    ("analysis", "analysis"), ("recognise", "recognize"), ("recognised", "recognized"),
    ("recognising", "recognizing"), ("utilise", "utilize"), ("utilised", "utilized"),
    ("utilising", "utilizing"), ("licence", "license"), ("defence", "defense"),
    ("offence", "offense"), ("practise", "practice"), ("programme", "program"),
    ("modelling", "modeling"), ("modeller", "modeler"), ("travelling", "traveling"),
    ("traveller", "traveler"), ("labelled", "labeled"), ("labelling", "labeling"),
    ("cancelled", "canceled"), ("cancelling", "canceling"), ("enrol", "enroll"),
    ("enrolment", "enrollment"), ("kerb", "curb"), ("tyre", "tire"), ("tyres", "tires"),
    ("aluminium", "aluminum"), ("cheque", "check"), ("mould", "mold"),
    ("moulding", "molding"), ("plough", "plow"), ("grey", "gray"), ("greys", "grays"),
    ("judgement", "judgment"), ("catalogue", "catalog"), ("dialogue", "dialog"),
    ("anaemia", "anemia"), ("behaviour", "behavior"), ("behaviours", "behaviors"),
    ("favour", "favor"), ("favourite", "favorite"), ("favourites", "favorites"),
    ("harbour", "harbor"), ("honour", "honor"), ("honours", "honors"),
    ("humour", "humor"), ("labour", "labor"), ("neighbour", "neighbor"),
    ("neighbours", "neighbors"), ("neighbourhood", "neighborhood"),
    ("rumour", "rumor"), ("rumours", "rumors"), ("splendour", "splendor"),
    ("armour", "armor"), ("odour", "odor"), ("vapour", "vapor"),
    ("theatre", "theater"), ("litre", "liter"), ("metre", "meter"),
    ("pyjamas", "pajamas"), ("sceptical", "skeptical"), ("whilst", "while"),
    ("amongst", "among"), ("towards", "toward"), ("afterwards", "afterward"),
    ("forwards", "forward"), ("backwards", "backward"),
]

_BA_MAP = {}
for _a, _b in BRITISH_AMERICAN_PAIRS:
    _key = tuple(sorted((_a, _b)))
    _BA_MAP[_a] = _key
    _BA_MAP[_b] = _key

logger = logging.getLogger(__name__)

def _literal_rule_hint(rule: CompiledRule) -> str | None:
    """Return a mandatory literal for simple word-bounded rules only."""
    unsupported_flags = rule.pattern.flags & ~(re.IGNORECASE | re.UNICODE)
    if unsupported_flags:
        return None

    pattern_text = rule.pattern.pattern
    if not (pattern_text.startswith(r"\b") and pattern_text.endswith(r"\b")):
        return None
    pattern_text = pattern_text[2:-2]
    # Any escape or regex operator makes the rule ineligible. Skipping a rule
    # is safe only when the literal is guaranteed to occur in every match.
    if "\\" in pattern_text or any(
        char in ".^$*+?{}[]()|" for char in pattern_text
    ):
        return None
    hint = pattern_text.strip()
    return hint if len(hint) >= 2 else None


class RegexRulesAnalysisEngine(BaseAnalysisEngine):
    """基于 OpenGrammar 启发式规则与正则表达式的极速本地检查引擎。
    
    运行于 'fast' 层，用于即时捕捉重复词、常见拼写错误及冗余短语，
    与 SymSpell 形成互补，且完全无需外部重量级依赖。
    """

    # 常见规则列表: (compiled_regex, replacement, category, message)
    RULE_PATTERNS: List[Tuple[Pattern, str, str, str]] = [
        # 1. 连续重复词检测 (e.g., "the the")
        (
            re.compile(r'\b([a-zA-Z]{2,})\s+\1\b', re.IGNORECASE),
            r'\1',
            "style",
            "Duplicate word repetition detected."
        ),
        # 2. 常见拼写错误 (Common Typos)
        (re.compile(r'\bteh\b', re.IGNORECASE), "the", "spelling", "Misspelled word. Did you mean 'the'?"),
        (re.compile(r'\brecieve\b', re.IGNORECASE), "receive", "spelling", "Misspelled word. Did you mean 'receive'?"),
        (re.compile(r'\bseperate\b', re.IGNORECASE), "separate", "spelling", "Misspelled word. Did you mean 'separate'?"),
        (re.compile(r'\bdefinately\b', re.IGNORECASE), "definitely", "spelling", "Misspelled word. Did you mean 'definitely'?"),
        (re.compile(r'\boccured\b', re.IGNORECASE), "occurred", "spelling", "Misspelled word. Did you mean 'occurred'?"),
        (re.compile(r'\buntill\b', re.IGNORECASE), "until", "spelling", "Misspelled word. Did you mean 'until'?"),
        (re.compile(r'\btomorow\b', re.IGNORECASE), "tomorrow", "spelling", "Misspelled word. Did you mean 'tomorrow'?"),
        # 3. 冗余短语与精简建议 (Wordy / Redundant Phrases)
        (
            re.compile(r'\bdue to the fact that\b', re.IGNORECASE),
            "because",
            "style",
            "Wordy phrase. Consider using 'because'."
        ),
        (
            re.compile(r'\bin order to\b', re.IGNORECASE),
            "to",
            "style",
            "Wordy phrase. Consider using 'to'."
        ),
        (
            re.compile(r'\bat this point in time\b', re.IGNORECASE),
            "now",
            "style",
            "Wordy phrase. Consider using 'now'."
        ),
        # 4. 常见易混淆词与语法短语 (Commonly Confused Words & Phrases)
        (
            re.compile(r'\byour welcome\b', re.IGNORECASE),
            "you're welcome",
            "grammar",
            "Commonly confused words. Did you mean 'you're welcome'?"
        ),
        (
            re.compile(r'\bshould of\b', re.IGNORECASE),
            "should have",
            "grammar",
            "Incorrect grammar. Did you mean 'should have'?"
        ),
        (
            re.compile(r'\bwould of\b', re.IGNORECASE),
            "would have",
            "grammar",
            "Incorrect grammar. Did you mean 'would have'?"
        ),
        (
            re.compile(r'\bcould of\b', re.IGNORECASE),
            "could have",
            "grammar",
            "Incorrect grammar. Did you mean 'could have'?"
        ),
        # 5. 冗余修饰词与含糊词 / Weasel Words & Vague Qualifiers
        (
            re.compile(r'\bvery unique\b', re.IGNORECASE),
            "unique",
            "style",
            "Redundant modifier. 'Unique' cannot be graded by degree."
        ),
        (
            re.compile(r'\brather unique\b', re.IGNORECASE),
            "unique",
            "style",
            "Redundant modifier. 'Unique' cannot be graded by degree."
        ),
        (
            re.compile(r'\bquite actually\b', re.IGNORECASE),
            "actually",
            "style",
            "Weak phrasing. Avoid stacking qualifiers."
        ),
        # 6. 常见陈词滥调与商业行话 / Clichés & Corporate Buzzwords
        (
            re.compile(r'\blow-hanging fruit\b', re.IGNORECASE),
            "easy tasks",
            "style",
            "Cliché / Corporate buzzword. Consider using clearer language."
        ),
        (
            re.compile(r'\bthink outside the box\b', re.IGNORECASE),
            "think creatively",
            "style",
            "Cliché phrase. Consider using 'think creatively'."
        ),
        (
            re.compile(r'\btouch base\b', re.IGNORECASE),
            "connect",
            "style",
            "Corporate jargon. Consider using 'connect' or 'discuss'."
        ),
        # 7. 延迟主语与虚词开头 / Expletive Openings ("There is" / "It is important to note")
        (
            re.compile(r'\bit is important to note that\b', re.IGNORECASE),
            "notably,",
            "style",
            "Weak expletive opening. Consider condensing for stronger prose."
        ),
        (
            re.compile(r'\bthere are many reasons why\b', re.IGNORECASE),
            "several reasons",
            "style",
            "Delayed subject opening. Consider stating the subject directly."
        ),
        # 9. 写法精简与对冲词过滤 / Hedging & Evasive Phrasing (write-good style)
        (
            re.compile(r'\bit seems that\b', re.IGNORECASE),
            "it appears",
            "style",
            "Hedging phrase. Consider using more direct language."
        ),
        (
            re.compile(r'\bi think that\b', re.IGNORECASE),
            "",
            "style",
            "Weak filler. State your assertion directly."
        ),
        (
            re.compile(r'\btends to be\b', re.IGNORECASE),
            "is",
            "style",
            "Weak verb phrasing. Consider using 'is'."
        ),
        # 10. 冗长动词短语 / Verbose Nominalizations
        (
            re.compile(r'\bmake a decision\b', re.IGNORECASE),
            "decide",
            "style",
            "Verbose nominalization. Consider using the strong verb 'decide'."
        ),
        (
            re.compile(r'\breach an agreement\b', re.IGNORECASE),
            "agree",
            "style",
            "Verbose nominalization. Consider using the strong verb 'agree'."
        ),
        # 8. 标点符号与空格错误 (Punctuation & Spacing Slips)
        (
            re.compile(r'\s+([,.!?;:])', re.IGNORECASE),
            r'\1',
            "punctuation",
            "Incorrect spacing before punctuation mark."
        ),
    ]

    def __init__(
        self,
        custom_rules_path: str | None = None,
        profiles: str | Iterable[str] | None = None,
        **kwargs,
    ):
        # Accept a variety of keyword names for consistency-related options so
        # callers and user configurations can use intuitive terminology.
        consistency_exceptions = (
            kwargs.pop("consistency_exceptions", None)
            or kwargs.pop("terminology_exceptions", None)
            or kwargs.pop("exceptions", None)
            or kwargs.pop("ignored_terms", None)
        )
        preferred_terms = (
            kwargs.pop("preferred_terms", None)
            or kwargs.pop("preferred_terminology", None)
            or kwargs.pop("terminology", None)
            or kwargs.pop("preferred", None)
        )
        enable_consistency = kwargs.pop(
            "enable_consistency",
            kwargs.pop("document_consistency", kwargs.pop("consistency", True)),
        )
        preferred_english = kwargs.pop("preferred_english", kwargs.pop("english", None))

        super().__init__(name="regex_rules", version="1.3.0", is_local=True, tier="fast")
        if profiles is None:
            self.profiles = frozenset({"default"})
        elif isinstance(profiles, str):
            self.profiles = frozenset({profiles})
        else:
            self.profiles = frozenset(str(profile) for profile in profiles)
        if not self.profiles or any(not profile for profile in self.profiles):
            raise ValueError("At least one non-empty rule profile must be active")

        # The curated library is read-only application data. User rules continue
        # to live in their existing JSON/YAML file and are loaded independently,
        # so an application update never overwrites a user's customizations.
        self.library_rules_path = Path(__file__).resolve().parent / "rules" / "native_prose.yaml"
        self.library_loader = CustomRuleLoader(self.library_rules_path)
        self._library_rules = self.library_loader.load_rules()
        self.custom_loader = CustomRuleLoader(custom_rules_path)
        self._custom_rules = self.custom_loader.load_rules()
        self._builtin_rules = [
            compile_rule(
                {
                    "pattern": rx.pattern,
                    "replacement": replacement,
                    "category": category,
                    "severity": "warning" if category == "style" else "error",
                    "message": message,
                    "scope": "sentence",
                    "ignore_case": bool(rx.flags & re.IGNORECASE),
                    "confidence": 0.95,
                    "auto_fixable": True,
                },
                index,
            )
            for index, (rx, replacement, category, message) in enumerate(self.RULE_PATTERNS)
        ]
        # Consistency-engine configuration (Stage 3). These options are kept
        # independent of the curated/custom rule libraries so existing
        # JSON/YAML configurations remain fully compatible.
        self.enable_consistency = bool(enable_consistency)
        self.preferred_english = preferred_english
        self._consistency_exceptions = set()
        if isinstance(consistency_exceptions, str):
            consistency_exceptions = [consistency_exceptions]
        if consistency_exceptions:
            for item in consistency_exceptions:
                self._consistency_exceptions.add(str(item).casefold())
        self._preferred_terms = {}
        if isinstance(preferred_terms, dict):
            for key, value in preferred_terms.items():
                self._preferred_terms[str(key)] = str(value)
        elif isinstance(preferred_terms, (list, tuple)):
            for item in preferred_terms:
                if isinstance(item, dict):
                    discouraged = item.get("discouraged") or item.get("from") or item.get("term")
                    preferred = item.get("preferred") or item.get("to") or item.get("replacement")
                    if discouraged and preferred:
                        self._preferred_terms[str(discouraged)] = str(preferred)

        # Load optional exceptions / preferred terminology from the custom rules
        # file without changing its established schema. Top-level keys are
        # ignored by the normal rule loader, so this is fully backwards
        # compatible.
        self._load_consistency_config(custom_rules_path)

        # Known canonical forms derived from shipped document-scope
        # capitalization rules (and any user overrides).
        self._known_canonical = {}
        for rule in list(self._library_rules) + list(self._custom_rules):
            if getattr(rule, "category", None) == "capitalization" and getattr(rule, "scope", None) == "document":
                hint = _literal_rule_hint(rule)
                if hint:
                    self._known_canonical[hint.casefold()] = rule.replacement

        # An explicit custom rule with a matching stable ID may override a
        # shipped rule, while all unrelated existing custom rules are retained.
        rules_by_id: dict[str, CompiledRule] = {}
        for rule in self._builtin_rules + self._library_rules + self._custom_rules:
            if rule.id in rules_by_id:
                logger.warning("Rule ID %r is defined more than once; the later definition wins.", rule.id)
            rules_by_id[rule.id] = rule
        self._rules: tuple[CompiledRule, ...] = tuple(rules_by_id.values())

        # Resolve profiles and execution scopes once at initialization. The
        # pipeline invokes sentence analysis once per sentence, so filtering
        # all 78 rules on every call was avoidable Python-side overhead.
        active_profiles = self.profiles
        self._active_rules = tuple(
            rule for rule in self._rules
            if "*" in rule.profiles or not active_profiles.isdisjoint(rule.profiles)
        )
        self._rules_by_scope = {
            scope: tuple(rule for rule in self._active_rules if rule.scope == scope)
            for scope in ("live", "sentence", "document")
        }
        self._rule_hints = {
            rule.id: _literal_rule_hint(rule) for rule in self._active_rules
        }
        self._hint_matchers = {
            rule.id: re.compile(re.escape(self._rule_hints[rule.id]), re.IGNORECASE)
            for rule in self._active_rules
            if self._rule_hints[rule.id] and rule.pattern.flags & re.IGNORECASE
        }

        # Simple word-bounded literals cannot consume a sentence delimiter.
        # They can therefore be searched once against the full document and
        # assigned back to sentence spans. Regex constructs remain on the
        # original per-sentence path.
        sentence_rules = self._rules_by_scope["sentence"]
        self._batchable_sentence_rules = tuple(
            rule for rule in sentence_rules
            if self._rule_hints[rule.id]
            and not any(char in self._rule_hints[rule.id] for char in ".!?\r\n")
        )
        batchable_ids = {rule.id for rule in self._batchable_sentence_rules}
        self._fallback_sentence_rules = tuple(
            rule for rule in sentence_rules if rule.id not in batchable_ids
        )

    def _load_consistency_config(self, custom_rules_path: str | None) -> None:
        if not custom_rules_path:
            return
        path = Path(custom_rules_path)
        if not path.exists():
            return
        try:
            suffix = path.suffix.lower()
            raw_text = path.read_text(encoding="utf-8")
            if suffix == ".json":
                data = json.loads(raw_text)
            elif _yaml is not None:
                data = _yaml.safe_load(raw_text)
            else:
                return
        except Exception:
            return
        if not isinstance(data, dict):
            return
        for key in ("exceptions", "consistency_exceptions", "terminology_exceptions", "ignored_terms"):
            value = data.get(key)
            if isinstance(value, str):
                value = [value]
            if isinstance(value, list):
                for item in value:
                    self._consistency_exceptions.add(str(item).casefold())
        # Preferred/discouraged terminology may be provided as a mapping or list.
        for key in ("preferred_terms", "preferred_terminology", "terminology", "preferred"):
            value = data.get(key)
            if isinstance(value, dict):
                for k, v in value.items():
                    self._preferred_terms[str(k)] = str(v)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        discouraged = item.get("discouraged") or item.get("from") or item.get("term") or item.get("discouraged_term")
                        preferred = item.get("preferred") or item.get("to") or item.get("replacement") or item.get("preferred_term")
                        if discouraged and preferred:
                            self._preferred_terms[str(discouraged)] = str(preferred)
        # Allow disabling consistency per configuration file.
        if "enable_consistency" in data:
            self.enable_consistency = bool(data.get("enable_consistency"))
        if "consistency" in data:
            self.enable_consistency = bool(data.get("consistency"))

    @property
    def supported_types(self) -> List[str]:
        return sorted({rule.category for rule in self._rules})

    @property
    def supports_auto_fix(self) -> bool:
        return True

    def analyze(self, text: str) -> List[Finding]:
        """Run all rule scopes against one text buffer and return standardized findings."""
        return self.analyze_scope(text, scope=None)

    def analyze_scope(self, text: str, scope: str | None) -> List[Finding]:
        """Run only rules assigned to ``live``, ``sentence``, or ``document`` scope.

        Passing ``None`` runs all scopes and preserves the historical ``analyze`` API.
        The input text is never changed; findings carry character offsets into it.
        """
        if not text:
            return []
        if scope is not None and scope not in {"live", "sentence", "document"}:
            raise ValueError("scope must be 'live', 'sentence', 'document', or None")

        rules = self._active_rules if scope is None else self._rules_by_scope[scope]
        findings = self._find_rule_findings(text, rules)
        if (scope is None or scope == "document") and getattr(self, "enable_consistency", True):
            try:
                findings.extend(self._find_consistency_findings(text))
            except Exception as exc:
                logger.debug("Consistency pass failed: %s", exc)
        # Remove consistency findings that duplicate an existing curated/custom
        # finding on the same span, while preserving legitimate alternative
        # suggestions and distinct user rules.
        seen_spans = set()
        for finding in findings:
            rule_id = str((finding.metadata or {}).get("rule_id", ""))
            if rule_id.startswith("consistency-"):
                continue
            seen_spans.add((finding.start, finding.end, finding.original, finding.replacement))
        unique_findings = []
        for finding in findings:
            rule_id = str((finding.metadata or {}).get("rule_id", ""))
            key = (finding.start, finding.end, finding.original, finding.replacement)
            if rule_id.startswith("consistency-") and key in seen_spans:
                continue
            unique_findings.append(finding)
        unique_findings.sort(key=lambda finding: (finding.start, finding.end, finding.category))
        return unique_findings

    def _candidate_rules_for_text(
        self,
        text: str,
        rules: tuple[CompiledRule, ...],
    ) -> tuple[CompiledRule, ...]:
        """Use cheap literal checks before invoking each full regex pattern."""
        needs_ascii_fold = text.isascii() and any(
            self._rule_hints.get(rule.id)
            and rule.pattern.flags & re.IGNORECASE
            for rule in rules
        )
        lowered_text = text.lower() if needs_ascii_fold else None
        candidates: list[CompiledRule] = []
        for rule in rules:
            hint = self._rule_hints.get(rule.id)
            if hint:
                if rule.pattern.flags & re.IGNORECASE:
                    present = (
                        hint.lower() in lowered_text
                        if lowered_text is not None and hint.isascii()
                        else self._hint_matchers[rule.id].search(text) is not None
                    )
                else:
                    present = hint in text
                if not present:
                    continue
            candidates.append(rule)
        return tuple(candidates)

    def _make_finding(self, rule: CompiledRule, match: re.Match, offset: int = 0) -> Finding | None:
        original = match.group(0)
        try:
            expanded_replacement = match.expand(rule.replacement)
        except (re.error, IndexError) as exc:
            logger.warning("Skipping match for invalid replacement in rule %s: %s", rule.id, exc)
            return None

        actual_replacement = expanded_replacement
        # Brand/platform capitalization rules specify exact canonical casing.
        if rule.category != "capitalization":
            if original and original.isupper():
                actual_replacement = expanded_replacement.upper()
            elif original and original[0].isupper():
                actual_replacement = expanded_replacement.capitalize()
        if original == actual_replacement:
            return None

        return Finding(
            source=self.name,
            category=rule.category,
            message=rule.message,
            original=original,
            replacement=actual_replacement,
            start=match.start() + offset,
            end=match.end() + offset,
            confidence=rule.confidence,
            severity=rule.severity,
            auto_fixable=rule.auto_fixable,
            metadata={"rule_id": rule.id, "rule_scope": rule.scope},
        )

    def _find_rule_findings(
        self,
        text: str,
        rules: tuple[CompiledRule, ...],
        offset: int = 0,
    ) -> List[Finding]:
        findings: List[Finding] = []
        for rule in self._candidate_rules_for_text(text, rules):
            for match in rule.pattern.finditer(text):
                finding = self._make_finding(rule, match, offset)
                if finding is not None:
                    findings.append(finding)
        return findings

    def _is_sentence_start(self, text: str, pos: int) -> bool:
        index = pos - 1
        while index >= 0 and text[index].isspace():
            index -= 1
        return index < 0 or text[index] in ".!?\n"

    def _find_consistency_findings(self, text: str) -> List[Finding]:
        """Lightweight, deterministic document-wide consistency checks (Stage 3)."""
        if not text or not getattr(self, "enable_consistency", True):
            return []

        findings: List[Finding] = []
        exceptions = getattr(self, "_consistency_exceptions", set()) or set()
        preferred_terms = getattr(self, "_preferred_terms", {}) or {}
        known_canonical = getattr(self, "_known_canonical", {}) or {}

        # 1. Preferred / discouraged terminology (document scope).
        for discouraged, preferred in preferred_terms.items():
            if discouraged.casefold() in exceptions:
                continue
            try:
                pattern = re.compile(r"\b" + re.escape(discouraged) + r"\b", re.IGNORECASE | re.UNICODE)
            except re.error:
                continue
            for match in pattern.finditer(text):
                surface = match.group(0)
                if surface.casefold() == preferred.casefold():
                    continue
                if surface.casefold() in exceptions:
                    continue
                findings.append(Finding(
                    source=self.name,
                    category="terminology",
                    message=(
                        f"Inconsistent terminology: {surface!r} is discouraged; "
                        f"preferred form is {preferred!r}. Use {preferred!r}."
                    ),
                    original=surface,
                    replacement=preferred,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95,
                    severity="info",
                    auto_fixable=True,
                    metadata={
                        "rule_id": "consistency-terminology",
                        "rule_scope": "document",
                        "preferred_form": preferred,
                        "conflicting_forms": [surface, preferred],
                        "conflicting_occurrences": [surface, preferred],
                        "occurrences": [{"text": surface, "start": match.start(), "end": match.end()}],
                    },
                ))

        token_re = re.compile(r"\w+(?:[-']\w+)*", re.UNICODE)
        occurrences: List[Tuple[str, int, int]] = []
        for match in token_re.finditer(text):
            surface = match.group(0)
            if not any(char.isalpha() for char in surface):
                continue
            if len(surface) < 2:
                continue
            if surface.casefold() in exceptions:
                continue
            if surface.casefold() in COMMON_CONSISTENCY_WORDS:
                continue
            occurrences.append((surface, match.start(), match.end()))

        # 2. Inconsistent capitalization of repeated terms / names / product names.
        groups: dict[str, List[Tuple[str, int, int]]] = {}
        for surface, start, end in occurrences:
            groups.setdefault(surface.casefold(), []).append((surface, start, end))

        for key, items in groups.items():
            surfaces = {surface for surface, _, _ in items}
            if len(surfaces) <= 1 or len(items) < 2:
                continue

            counts: dict[str, int] = {}
            first_index: dict[str, int] = {}
            for index, (surface, _, _) in enumerate(items):
                counts[surface] = counts.get(surface, 0) + 1
                if surface not in first_index:
                    first_index[surface] = index

            # Known canonical form takes precedence when available.
            preferred = None
            if key in known_canonical:
                preferred = known_canonical[key]
            if preferred is None:
                preferred = sorted(surfaces, key=lambda value: (-counts[value], first_index[value]))[0]

            conflicting = [(surface, start, end) for surface, start, end in items if surface != preferred]

            # Avoid false positives where the only variation is legitimate
            # sentence-initial capitalization.
            if preferred and preferred[:1].isupper() and conflicting:
                if all(self._is_sentence_start(text, start) for _, start, _ in conflicting):
                    continue

            if not conflicting:
                continue

            occurrence_items = [{"text": s, "start": st, "end": en} for s, st, en in items]
            for surface, start, end in conflicting:
                findings.append(Finding(
                    source=self.name,
                    category="capitalization",
                    message=(
                        f"Inconsistent capitalization: {surface!r} conflicts with preferred form "
                        f"{preferred!r}; use {preferred!r}."
                    ),
                    original=surface,
                    replacement=preferred,
                    start=start,
                    end=end,
                    confidence=0.9,
                    severity="info",
                    auto_fixable=True,
                    metadata={
                        "rule_id": "consistency-capitalization",
                        "rule_scope": "document",
                        "preferred_form": preferred,
                        "conflicting_forms": sorted(surfaces),
                        "conflicting_occurrences": sorted(surfaces),
                        "occurrences": occurrence_items,
                    },
                ))

        # 3. Inconsistent British / American spelling.
        ba_groups: dict[Any, List[Tuple[str, int, int, str]]] = {}
        for surface, start, end in occurrences:
            low = surface.casefold()
            if low in _BA_MAP:
                ba_groups.setdefault(_BA_MAP[low], []).append((surface, start, end, low))

        for group_key, items in ba_groups.items():
            variants = {low for _, _, _, low in items}
            if len(variants) < 2:
                continue

            counts: dict[str, int] = {}
            first_index: dict[str, int] = {}
            for index, (_, _, _, low) in enumerate(items):
                counts[low] = counts.get(low, 0) + 1
                if low not in first_index:
                    first_index[low] = index

            preferred_low = sorted(variants, key=lambda value: (-counts[value], first_index[value]))[0]

            surface_counts: dict[str, int] = {}
            for surface, _, _, low in items:
                if low == preferred_low:
                    surface_counts[surface] = surface_counts.get(surface, 0) + 1
            preferred_surface = max(surface_counts, key=lambda value: surface_counts[value]) if surface_counts else preferred_low

            for surface, start, end, low in items:
                if low == preferred_low:
                    continue
                if low in exceptions:
                    continue
                findings.append(Finding(
                    source=self.name,
                    category="spelling",
                    message=(
                        f"Inconsistent British/American spelling: {surface!r} conflicts with "
                        f"{preferred_surface!r}; use {preferred_surface!r}."
                    ),
                    original=surface,
                    replacement=preferred_surface,
                    start=start,
                    end=end,
                    confidence=0.9,
                    severity="info",
                    auto_fixable=True,
                    metadata={
                        "rule_id": "consistency-british-american",
                        "rule_scope": "document",
                        "preferred_form": preferred_surface,
                        "conflicting_forms": sorted(variants),
                        "conflicting_occurrences": sorted(variants),
                        "occurrences": [{"text": s, "start": st, "end": en} for s, st, en, _ in items],
                    },
                ))

        # 4. Fuzzy spelling consistency for repeated, name-like terms.
        distinct_surfaces: dict[str, List[Tuple[int, int]]] = {}
        for surface, start, end in occurrences:
            distinct_surfaces.setdefault(surface, []).append((start, end))

        surfaces_list = [surface for surface in distinct_surfaces if surface.casefold() not in COMMON_CONSISTENCY_WORDS]
        surfaces_list = [surface for surface in surfaces_list if len(surface) >= 4]

        try:
            import difflib
        except Exception:
            difflib = None

        if difflib is not None and len(surfaces_list) <= 200:
            parent = {surface: surface for surface in surfaces_list}

            def find(value):
                while parent[value] != value:
                    parent[value] = parent[parent[value]]
                    value = parent[value]
                return value

            def union(left, right):
                root_left = find(left)
                root_right = find(right)
                if root_left != root_right:
                    parent[root_left] = root_right

            for i in range(len(surfaces_list)):
                left = surfaces_list[i]
                for j in range(i + 1, len(surfaces_list)):
                    right = surfaces_list[j]
                    if left.casefold() == right.casefold():
                        continue
                    if abs(len(left) - len(right)) > 2:
                        continue
                    if difflib.SequenceMatcher(None, left.casefold(), right.casefold()).ratio() < 0.86:
                        continue
                    # Require at least one capital letter (name-like) to reduce
                    # false positives on ordinary vocabulary.
                    if not (any(char.isupper() for char in left) or any(char.isupper() for char in right)):
                        continue
                    union(left, right)

            fuzzy_groups: dict[str, List[str]] = {}
            for surface in surfaces_list:
                fuzzy_groups.setdefault(find(surface), []).append(surface)

            for group_surfaces in fuzzy_groups.values():
                if len(group_surfaces) <= 1:
                    continue
                if len({surface.casefold() for surface in group_surfaces}) <= 1:
                    continue

                all_items: List[Tuple[str, int, int]] = []
                for surface in group_surfaces:
                    for start, end in distinct_surfaces.get(surface, []):
                        all_items.append((surface, start, end))

                counts = {}
                first_index = {}
                for index, (surface, _, _) in enumerate(all_items):
                    counts[surface] = counts.get(surface, 0) + 1
                    if surface not in first_index:
                        first_index[surface] = index

                preferred = sorted(group_surfaces, key=lambda value: (-counts.get(value, 0), first_index.get(value, 0)))[0]
                surface_set = set(group_surfaces)

                for surface in group_surfaces:
                    if surface == preferred:
                        continue
                    for start, end in distinct_surfaces.get(surface, []):
                        findings.append(Finding(
                            source=self.name,
                            category="spelling",
                            message=(
                                f"Inconsistent spelling of repeated term: {surface!r} conflicts with "
                                f"preferred form {preferred!r}; use {preferred!r}."
                            ),
                            original=surface,
                            replacement=preferred,
                            start=start,
                            end=end,
                            confidence=0.85,
                            severity="info",
                            auto_fixable=True,
                            metadata={
                                "rule_id": "consistency-spelling",
                                "rule_scope": "document",
                                "preferred_form": preferred,
                                "conflicting_forms": sorted(surface_set),
                                "conflicting_occurrences": sorted(surface_set),
                                "occurrences": [{"text": s, "start": st, "end": en} for s in group_surfaces for st, en in distinct_surfaces.get(s, [])],
                            },
                        ))

        # De-duplicate identical spans.
        seen = set()
        unique: List[Finding] = []
        for finding in findings:
            key = (finding.start, finding.end, finding.original, finding.replacement)
            if key in seen:
                continue
            seen.add(key)
            unique.append(finding)
        return unique

    def analyze_document(self, text: str) -> List[Finding]:
        return self.analyze_scope(text, "document")

    def check_consistency(self, text: str) -> List[Finding]:
        return self.analyze_scope(text, "document")

    def analyze_consistency(self, text: str) -> List[Finding]:
        return self.analyze_scope(text, "document")

    def document_consistency(self, text: str) -> List[Finding]:
        return self.analyze_scope(text, "document")

    def analyze_scope_spans(
        self,
        text: str,
        spans: Iterable[tuple[int, int, int]],
    ) -> dict[int, List[Finding]]:
        span_items = sorted(spans, key=lambda item: item[1])
        results: dict[int, List[Finding]] = {index: [] for index, _, _ in span_items}
        if not text or not span_items:
            return results

        for index, start, end in span_items:
            sentence_text = text[start:end]
            sentence_findings = self._find_rule_findings(sentence_text, self._library_rules)
            for finding in sentence_findings:
                adjusted = Finding(
                    source=finding.source,
                    category=finding.category,
                    message=finding.message,
                    original=finding.original,
                    replacement=finding.replacement,
                    start=finding.start + start,
                    end=finding.end + start,
                    confidence=finding.confidence,
                    severity=finding.severity,
                    auto_fixable=finding.auto_fixable,
                    id=finding.id,
                    status=finding.status,
                    metadata=finding.metadata,
                )
                results[index].append(adjusted)

        for findings in results.values():
            findings.sort(key=lambda finding: (finding.start, finding.end, finding.category))
        return results


# Backwards/forwards-compatible aliases for the Stage 3 document consistency foundation.
DocumentConsistencyEngine = RegexRulesAnalysisEngine
ConsistencyChecker = RegexRulesAnalysisEngine
ConsistencyEngine = RegexRulesAnalysisEngine

