"""
Unit tests for Phase 1 Unified Analysis Foundation
"""

import unittest
from core.analysis import Finding, BaseAnalysisEngine, AnalysisPipeline


class DummyEngine(BaseAnalysisEngine):
    """测试专用的虚拟引擎"""
    def __init__(self, name="dummy_engine", findings_to_return=None, should_fail=False):
        super().__init__(name=name, version="1.0.0", is_local=True)
        self.findings_to_return = findings_to_return or []
        self.should_fail = should_fail

    def analyze(self, text: str):
        if self.should_fail:
            raise RuntimeError("Engine analysis failed intentionally")
        
        # 简单模拟：如果文本包含某些触发词，返回预设 finding
        results = []
        for f in self.findings_to_return:
            # 调整或直接返回
            results.append(f)
        return results


class TestFindingModel(unittest.TestCase):
    """测试 Finding 数据模型及其默认值、序列化等"""

    def test_finding_creation_and_defaults(self):
        f = Finding(
            source="harper",
            category="spelling",
            message="Possible spelling mistake",
            original="tehst",
            replacement="test",
            start=0,
            end=5,
        )
        self.assertEqual(f.source, "harper")
        self.assertEqual(f.category, "spelling")
        self.assertEqual(f.message, "Possible spelling mistake")
        self.assertEqual(f.original, "tehst")
        self.assertEqual(f.replacement, "test")
        self.assertEqual(f.start, 0)
        self.assertEqual(f.end, 5)
        self.assertEqual(f.confidence, 1.0)
        self.assertEqual(f.severity, "error")
        self.assertTrue(f.auto_fixable)
        self.assertEqual(f.status, "detected")
        self.assertIsNotNone(f.id)
        self.assertIsInstance(f.metadata, dict)

    def test_finding_custom_values(self):
        f = Finding(
            source="gector",
            category="grammar",
            message="Subject-verb agreement",
            original="go",
            replacement="goes",
            start=4,
            end=6,
            confidence=0.98,
            severity="warning",
            auto_fixable=True,
            status="accepted",
            metadata={"rule_id": "SVA_01"}
        )
        self.assertEqual(f.confidence, 0.98)
        self.assertEqual(f.severity, "warning")
        self.assertEqual(f.status, "accepted")
        self.assertEqual(f.metadata.get("rule_id"), "SVA_01")

    def test_serialization_roundtrip(self):
        f = Finding(
            source="no-ai-slop",
            category="style",
            message="Overused buzzword",
            original="synergize",
            replacement="work together",
            start=10,
            end=19,
            confidence=0.85,
            severity="style",
            metadata={"context": "corporate"}
        )
        d = f.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["source"], "no-ai-slop")
        self.assertEqual(d["start"], 10)
        self.assertEqual(d["end"], 19)

        f2 = Finding.from_dict(d)
        self.assertEqual(f, f2)
        self.assertEqual(f2.id, f.id)


class TestAnalysisEngineAbstraction(unittest.TestCase):
    """测试分析引擎抽象基类及元数据"""

    def test_engine_metadata(self):
        engine = DummyEngine(name="test_engine")
        self.assertEqual(engine.name, "test_engine")
        self.assertEqual(engine.version, "1.0.0")
        self.assertTrue(engine.is_local)
        self.assertTrue(engine.supports_auto_fix)
        self.assertIn("grammar", engine.supported_types)

        meta = engine.get_metadata()
        self.assertEqual(meta["name"], "test_engine")
        self.assertEqual(meta["version"], "1.0.0")
        self.assertTrue(meta["is_local"])


class TestAnalysisPipeline(unittest.TestCase):
    """测试分析协调器/管道 (AnalysisPipeline)"""

    def test_pipeline_registration(self):
        pipeline = AnalysisPipeline()
        self.assertEqual(pipeline.list_engines(), [])

        engine1 = DummyEngine(name="engine1")
        engine2 = DummyEngine(name="engine2")

        pipeline.register_engine(engine1)
        self.assertEqual(pipeline.list_engines(), ["engine1"])
        self.assertEqual(pipeline.get_engine("engine1"), engine1)

        pipeline.register_engine(engine2)
        self.assertEqual(set(pipeline.list_engines()), {"engine1", "engine2"})

        removed = pipeline.unregister_engine("engine1")
        self.assertEqual(removed, engine1)
        self.assertEqual(pipeline.list_engines(), ["engine2"])

    def test_pipeline_invalid_engine_registration(self):
        pipeline = AnalysisPipeline()
        with self.assertRaises(TypeError):
            pipeline.register_engine("not_an_engine")  # type: ignore

    def test_pipeline_empty_text(self):
        pipeline = AnalysisPipeline()
        engine = DummyEngine(name="e1", findings_to_return=[
            Finding("e1", "cat", "msg", "a", "b", 0, 1)
        ])
        pipeline.register_engine(engine)
        findings = pipeline.analyze("")
        self.assertEqual(findings, [])

    def test_pipeline_multiple_engines_and_findings(self):
        pipeline = AnalysisPipeline()

        f1 = Finding("engine1", "grammar", "err1", "go", "goes", 4, 6, 0.9)
        f2 = Finding("engine2", "style", "err2", "utilize", "use", 10, 17, 0.8)

        engine1 = DummyEngine(name="engine1", findings_to_return=[f1])
        engine2 = DummyEngine(name="engine2", findings_to_return=[f2])

        pipeline.register_engine(engine1)
        pipeline.register_engine(engine2)

        findings = pipeline.analyze("She go and utilize tool.")
        self.assertEqual(len(findings), 2)
        self.assertIn(f1, findings)
        self.assertIn(f2, findings)

    def test_pipeline_engine_failure_resilience(self):
        pipeline = AnalysisPipeline()

        f1 = Finding("engine1", "grammar", "err1", "a", "b", 0, 1)
        engine_ok = DummyEngine(name="engine1", findings_to_return=[f1])
        engine_fail = DummyEngine(name="engine_fail", should_fail=True)

        pipeline.register_engine(engine_ok)
        pipeline.register_engine(engine_fail)

        # 管道不应因 engine_fail 抛出异常崩溃，而是捕获并返回正常引擎的结果
        findings = pipeline.analyze("test text")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0], f1)


if __name__ == "__main__":
    unittest.main()
