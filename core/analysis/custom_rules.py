"""Load and validate local YAML and legacy JSON prose rules."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Pattern

import yaml

logger = logging.getLogger(__name__)

RULE_SCOPES = frozenset({"live", "sentence", "document"})
RULE_SEVERITIES = frozenset({"error", "warning", "style", "info"})
RULE_FLAGS = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
    "VERBOSE": re.VERBOSE,
    "ASCII": re.ASCII,
    "UNICODE": re.UNICODE,
}


@dataclass(frozen=True, slots=True)
class CompiledRule:
    """A validated rule with its regular expression compiled exactly once."""

    id: str
    pattern_text: str
    pattern: Pattern[str]
    replacement: str
    category: str
    severity: str
    message: str
    profiles: tuple[str, ...]
    scope: str
    confidence: float
    auto_fixable: bool


class RuleValidationError(ValueError):
    """Raised when an individual rule does not satisfy the rule schema."""


def _stable_rule_id(rule_data: dict[str, Any]) -> str:
    """Create a repeatable ID when a rule author did not provide one."""
    canonical = json.dumps(rule_data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"rule-{digest}"


def compile_rule(item: Any, index: int = 0) -> CompiledRule:
    """Validate one rule mapping and return its cached compiled form."""
    if not isinstance(item, dict):
        raise RuleValidationError("rule must be a mapping")

    pattern_text = item.get("pattern")
    if not isinstance(pattern_text, str) or not pattern_text:
        raise RuleValidationError("'pattern' must be a non-empty string")

    replacement = item.get("replacement", "")
    if not isinstance(replacement, str):
        raise RuleValidationError("'replacement' must be a string")

    category = item.get("category", item.get("style", "style"))
    if not isinstance(category, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", category):
        raise RuleValidationError("'category' must be a lowercase category name")

    default_severity = "warning" if category == "style" else "error"
    severity = item.get("severity", default_severity)
    if not isinstance(severity, str) or severity not in RULE_SEVERITIES:
        raise RuleValidationError(
            f"'severity' must be one of: {', '.join(sorted(RULE_SEVERITIES))}"
        )

    message = item.get("message", "Custom rule suggestion.")
    if not isinstance(message, str) or not message.strip():
        raise RuleValidationError("'message' must be a non-empty string")

    scope = item.get("scope", "sentence")
    if not isinstance(scope, str) or scope not in RULE_SCOPES:
        raise RuleValidationError(f"'scope' must be one of: {', '.join(sorted(RULE_SCOPES))}")

    raw_profiles = item.get("profiles", ["*"])
    if isinstance(raw_profiles, str):
        raw_profiles = [raw_profiles]
    if (
        not isinstance(raw_profiles, list)
        or not raw_profiles
        or any(not isinstance(profile, str) or not profile.strip() for profile in raw_profiles)
    ):
        raise RuleValidationError("'profiles' must be a non-empty string or list of strings")
    profiles = tuple(dict.fromkeys(profile.strip() for profile in raw_profiles))

    ignore_case = item.get("ignore_case", True)
    if not isinstance(ignore_case, bool):
        raise RuleValidationError("'ignore_case' must be a boolean")
    flags = re.IGNORECASE if ignore_case else 0
    raw_flags = item.get("flags", [])
    if isinstance(raw_flags, str):
        raw_flags = [raw_flags]
    if not isinstance(raw_flags, list):
        raise RuleValidationError("'flags' must be a string or list of flag names")
    for flag_name in raw_flags:
        if not isinstance(flag_name, str) or flag_name.upper() not in RULE_FLAGS:
            raise RuleValidationError(
                f"unsupported regex flag {flag_name!r}; use {', '.join(sorted(RULE_FLAGS))}"
            )
        flags |= RULE_FLAGS[flag_name.upper()]

    try:
        compiled_pattern = re.compile(pattern_text, flags)
    except (re.error, ValueError) as exc:
        raise RuleValidationError(f"invalid regular expression: {exc}") from exc
    try:
        # Pattern.sub compiles the replacement template even when the input has
        # no match, so invalid group references are caught during rule loading.
        compiled_pattern.sub(replacement, "")
    except (re.error, IndexError) as exc:
        raise RuleValidationError(f"invalid replacement template: {exc}") from exc

    confidence = item.get("confidence", 0.95)
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise RuleValidationError("'confidence' must be a number between 0 and 1")

    auto_fixable = item.get("auto_fixable", True)
    if not isinstance(auto_fixable, bool):
        raise RuleValidationError("'auto_fixable' must be a boolean")

    explicit_id = item.get("id")
    if explicit_id is not None and (not isinstance(explicit_id, str) or not explicit_id.strip()):
        raise RuleValidationError("'id' must be a non-empty string when provided")

    id_data = {
        "pattern": pattern_text,
        "replacement": replacement,
        "category": category,
        "severity": severity,
        "message": message,
        "profiles": profiles,
        "scope": scope,
        "ignore_case": ignore_case,
        "flags": [str(flag).upper() for flag in raw_flags],
        "confidence": float(confidence),
        "auto_fixable": auto_fixable,
    }
    rule_id = explicit_id.strip() if explicit_id else _stable_rule_id(id_data)

    return CompiledRule(
        id=rule_id,
        pattern_text=pattern_text,
        pattern=compiled_pattern,
        replacement=replacement,
        category=category,
        severity=severity,
        message=message,
        profiles=profiles,
        scope=scope,
        confidence=float(confidence),
        auto_fixable=auto_fixable,
    )


class CustomRuleLoader:
    """Load user rules from YAML or legacy JSON without executing YAML objects.

    YAML files may contain a list of rule mappings or a mapping with a ``rules``
    list. JSON files retain support for the original list-of-mappings format.
    Invalid rules are reported in :attr:`errors` and skipped individually.
    """

    def __init__(self, rules_file_path: str | os.PathLike[str] | None = None):
        use_default_path = rules_file_path is None
        self.rules_file_path = Path(
            rules_file_path
            if rules_file_path is not None
            else os.path.join(os.path.expanduser("~"), ".gcoach_custom_rules.json")
        )
        self.errors: list[str] = []
        if use_default_path:
            self._ensure_default_file()

    def _ensure_default_file(self) -> None:
        """Retain the established default JSON location for existing installs."""
        try:
            if not self.rules_file_path.exists():
                default_rules = [
                    {
                        "pattern": r"\b(gcoach)\b",
                        "replacement": "G-Coach",
                        "category": "style",
                        "message": "Product name should be capitalized as 'G-Coach'.",
                    }
                ]
                self.rules_file_path.parent.mkdir(parents=True, exist_ok=True)
                self.rules_file_path.write_text(
                    json.dumps(default_rules, indent=2, ensure_ascii=False), encoding="utf-8"
                )
        except OSError as exc:
            logger.debug("Failed to initialize default custom rules file: %s", exc)

    def _read_data(self) -> Any:
        suffix = self.rules_file_path.suffix.lower()
        content = self.rules_file_path.read_text(encoding="utf-8")
        if suffix == ".json":
            return json.loads(content)
        # safe_load is intentional: custom rule files must never construct Python objects.
        return yaml.safe_load(content)

    def load_rules(self) -> list[CompiledRule]:
        """Read, validate, and compile the rule file once for engine initialization."""
        self.errors = []
        if not self.rules_file_path.exists():
            return []

        try:
            rules_data = self._read_data()
        except (OSError, UnicodeError, json.JSONDecodeError, yaml.YAMLError) as exc:
            self.errors.append(f"Unable to read rules file: {exc}")
            logger.warning("Unable to load custom rules from %s: %s", self.rules_file_path, exc)
            return []

        if isinstance(rules_data, dict):
            rules_data = rules_data.get("rules")
        if not isinstance(rules_data, list):
            self.errors.append("Rule file root must be a list or a mapping containing a 'rules' list")
            return []

        compiled_rules: list[CompiledRule] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(rules_data):
            try:
                rule = compile_rule(item, index)
                if rule.id in seen_ids:
                    raise RuleValidationError(f"duplicate rule ID {rule.id!r}")
                seen_ids.add(rule.id)
                compiled_rules.append(rule)
            except RuleValidationError as exc:
                error = f"Rule {index + 1}: {exc}"
                self.errors.append(error)
                logger.warning("Skipping invalid rule in %s: %s", self.rules_file_path, error)
        return compiled_rules
