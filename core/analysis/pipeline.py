"""
分析协调器/管道 (Pipeline) - Phase 1 Unified Analysis Foundation & Phase 8F Personal Dictionary
"""

import logging
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

    def __init__(self, dictionary: Optional[PersonalDictionary] = None):
        self._engines: Dict[str, BaseAnalysisEngine] = {}
        self.dictionary = dictionary or PersonalDictionary()

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
        """运行所有已注册的引擎，收集并组合所有标准化 Findings。

        单个引擎的异常不会导致整个管道崩溃，异常会被捕获并记录日志。
        """
        all_findings: List[Finding] = []
        if not text:
            return all_findings

        for name, engine in self._engines.items():
            try:
                findings = engine.analyze(text)
                if findings:
                    # 确保返回的是 Finding 实例列表
                    for f in findings:
                        if isinstance(f, Finding):
                            all_findings.append(f)
                        elif isinstance(f, dict):
                            all_findings.append(Finding.from_dict(f))
            except Exception as e:
                logger.error(f"Error running analysis engine '{name}': {e}", exc_info=True)

        # 过滤掉落在个人词典中的词汇产生的 findings
        filtered_findings = []
        for f in all_findings:
            orig = f.original
            span_text = text[f.start:f.end] if 0 <= f.start <= f.end <= len(text) else orig
            
            is_in_dict = (
                self.dictionary.contains(orig) or 
                (span_text and self.dictionary.contains(span_text))
            )
            
            if is_in_dict:
                logger.debug(f"Suppressing finding for dictionary word: '{orig}' (source: {f.source})")
                continue
            
            filtered_findings.append(f)

        return filtered_findings
