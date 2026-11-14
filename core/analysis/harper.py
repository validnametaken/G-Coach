"""
Harper 本地语法分析引擎集成 - Phase 2 Harper Local Analysis Engine
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from .finding import Finding
from .engine import BaseAnalysisEngine

logger = logging.getLogger(__name__)


class HarperAnalysisEngine(BaseAnalysisEngine):
    """基于 Harper (harper.js / WASM) 的本地确定性语法分析引擎。

    通过 Node.js 子进程调用本地打包的 harper.js 引擎，对文本进行离线、确定性语法检查，
    并将诊断结果转换为标准化的 Finding 模型。
    """

    def __init__(self, runner_path: Optional[str] = None):
        super().__init__(name="harper", version="0.1.0", is_local=True)
        if runner_path:
            self.runner_path = Path(runner_path)
        else:
            self.runner_path = Path(__file__).parent / "harper_runner.js"

    @property
    def supported_types(self) -> List[str]:
        return ["grammar", "spelling", "punctuation", "style"]

    @property
    def supports_auto_fix(self) -> bool:
        return True

    @staticmethod
    def _utf16_boundary_map(text: str) -> Dict[int, int]:
        """Map JavaScript UTF-16 offsets to Python string character offsets.

        Harper's spans are returned by ``harper.js`` and are consumed by
        JavaScript ``String.slice``, so their offsets count UTF-16 code units.
        G-Coach findings use Python character offsets. Only valid code-point
        boundaries are included; an offset inside a surrogate pair is invalid.
        """
        boundaries = {0: 0}
        utf16_offset = 0
        for python_offset, character in enumerate(text, start=1):
            utf16_offset += 2 if ord(character) > 0xFFFF else 1
            boundaries[utf16_offset] = python_offset
        return boundaries

    def analyze(self, text: str) -> List[Finding]:
        """对输入文本进行本地 Harper 语法分析，返回标准化 Findings 列表。

        如果文本为空、空白、Node.js 不可用或运行时发生错误，将安全捕获并返回空列表。
        """
        if not text or not text.strip():
            return []

        if not self.runner_path.exists():
            logger.error(f"Harper runner script not found at {self.runner_path}")
            return []

        try:
            result = subprocess.run(
                ["node", str(self.runner_path)],
                input=text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
            )

            if result.returncode != 0:
                logger.warning("Harper analysis subprocess failed (exit code %s).", result.returncode)
                return []

            stdout_data = result.stdout.decode("utf-8", errors="ignore").strip()
            if not stdout_data:
                return []

            raw_findings = json.loads(stdout_data)
            findings: List[Finding] = []
            utf16_boundaries = self._utf16_boundary_map(text)

            for item in raw_findings:
                original = item.get("original", "")
                raw_start = item.get("start")
                raw_end = item.get("end")

                # Normalize JavaScript UTF-16 offsets at the engine boundary
                # so every Finding in G-Coach consistently uses Python offsets.
                if (
                    isinstance(raw_start, bool)
                    or not isinstance(raw_start, int)
                    or isinstance(raw_end, bool)
                    or not isinstance(raw_end, int)
                ):
                    logger.debug("Harper returned a finding with invalid text offsets.")
                    continue

                start = utf16_boundaries.get(raw_start)
                end = utf16_boundaries.get(raw_end)
                if start is None or end is None or end < start or text[start:end] != original:
                    logger.debug("Harper returned a finding whose offsets do not match the source text.")
                    continue

                replacements = item.get("replacements", [])
                replacement = replacements[0] if replacements else ""
                auto_fixable = len(replacements) > 0

                category = item.get("category", "Grammar").lower().replace(" ", "_")
                message = item.get("message", "Grammar suggestion")

                # Harper's spelling rule can mistake uppercase abbreviations
                # such as "MB" for misspelled words in explanatory text.
                # Keep these terms intact while still allowing contextual
                # WordChoice findings (for example, "10 MB" -> "megabytes").
                if (
                    category == "spelling"
                    and len(original) >= 2
                    and original.isalpha()
                    and original.isupper()
                ):
                    logger.debug("Ignoring a Harper spelling suggestion for an uppercase term.")
                    continue

                # Harper 是确定性规则检查器，置信度设为 1.0
                confidence = 1.0
                severity = "error" if "error" in category or "agreement" in category else "warning"

                finding = Finding(
                    source="harper",
                    category=category,
                    message=message,
                    original=original,
                    replacement=replacement,
                    start=start,
                    end=end,
                    confidence=confidence,
                    severity=severity,
                    auto_fixable=auto_fixable,
                    metadata={
                        "raw_json": item.get("json"),
                        "replacements": replacements,
                    },
                )
                findings.append(finding)

            return findings

        except subprocess.TimeoutExpired:
            logger.warning("Harper analysis timed out.")
            return []
        except Exception as e:
            logger.error(f"Error running Harper analysis engine: {e}", exc_info=True)
            return []
