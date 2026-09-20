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
                stderr_msg = result.stderr.decode("utf-8", errors="ignore")
                logger.warning(f"Harper analysis subprocess failed: {stderr_msg}")
                return []

            stdout_data = result.stdout.decode("utf-8", errors="ignore").strip()
            if not stdout_data:
                return []

            raw_findings = json.loads(stdout_data)
            findings: List[Finding] = []

            for item in raw_findings:
                original = item.get("original", "")
                start = item.get("start", 0)
                end = item.get("end", 0)

                # 校验文本范围切片是否与 original 匹配（针对边界、Unicode等）
                if 0 <= start <= end <= len(text):
                    sliced = text[start:end]
                    if sliced != original:
                        logger.debug(f"Harper span text mismatch: expected '{original}', got slice '{sliced}'")

                replacements = item.get("replacements", [])
                replacement = replacements[0] if replacements else ""
                auto_fixable = len(replacements) > 0

                category = item.get("category", "Grammar").lower().replace(" ", "_")
                message = item.get("message", "Grammar suggestion")

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
