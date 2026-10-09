"""
Real GECToR Model Benchmark Utility - Phase 4 Analysis Resolution
"""

import time
import unittest
from core.analysis import GectorAnalysisEngine


class TestGectorBenchmark(unittest.TestCase):
    """GECToR 真实模型性能基准测试工具（当模型未安装时安全跳过）"""

    def test_real_model_benchmark(self):
        engine = GectorAnalysisEngine()
        # 检查模型是否真正安装
        loaded = engine._load_model()
        if not loaded:
            print("\n[Benchmark] GECToR real model files not found in models/gector/. Skipping real model benchmark.")
            self.skipTest("GECToR model not installed; skipping real model benchmark.")

        print("\n[Benchmark] Starting GECToR real model benchmark...")
        
        # 1. Initialization / load time measurement (already loaded in _load_model, or measure cold start)
        t0 = time.time()
        engine2 = GectorAnalysisEngine()
        engine2._load_model()
        load_time = time.time() - t0
        print(f"[Benchmark] Model load time: {load_time*1000:.2f} ms")

        short_text = "She go to school."
        paragraph = (
            "I has a apple yesterday. "
            "The students was very happy about the results. "
            "He didn't went to school."
        )

        # 2. First inference time
        t0 = time.time()
        res1 = engine2.analyze(short_text)
        first_inf_time = time.time() - t0
        print(f"[Benchmark] First inference (short text): {first_inf_time*1000:.2f} ms")

        # 3. Subsequent inference time
        t0 = time.time()
        res2 = engine2.analyze(short_text)
        sub_inf_time = time.time() - t0
        print(f"[Benchmark] Subsequent inference (short text): {sub_inf_time*1000:.2f} ms")

        # 4. Paragraph inference time
        t0 = time.time()
        res_para = engine2.analyze(paragraph)
        para_inf_time = time.time() - t0
        print(f"[Benchmark] Paragraph inference ({len(paragraph)} chars): {para_inf_time*1000:.2f} ms")

        self.assertIsNotNone(res1)
        self.assertIsNotNone(res_para)


if __name__ == "__main__":
    unittest.main()
