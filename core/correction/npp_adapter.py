"""
G-Coach Notepad++ Bridge Adapter (Phase 8G.6)
Integrates NppBridgeClient into BackgroundCorrectionEngine for safe, in-process Notepad++ correction write-back.
"""

import logging
import platform
from typing import Optional
from core.analysis import Finding
from core.correction.target import CorrectionTarget
from core.correction.npp_client import NppBridgeClient

logger = logging.getLogger(__name__)

class NppCorrectionAdapter:
    """Notepad++ 桥接修正适配器（Phase 8G.6 Integration Adapter）
    
    使用命名管道客户端 (NppBridgeClient) 将纠正请求安全地转发到运行在 notepad++.exe 内部的
    原生 C++ 插件，完全避免跨进程 SendMessage 指针内存破坏与崩溃。
    """

    @staticmethod
    def is_notepad_target(target: CorrectionTarget) -> bool:
        """检查目标是否为 Notepad++ 应用程序"""
        if not target:
            return False
        app_name = (target.app_name or "").lower()
        return "notepad++" in app_name or "notepad++.exe" in app_name

    @staticmethod
    def apply_bridge_correction(target: CorrectionTarget, finding: Finding) -> bool:
        """通过 NppBridgeClient 执行安全的命名管道桥接替换"""
        if not NppCorrectionAdapter.is_notepad_target(target):
            return False

        if platform.system() != "Windows":
            logger.debug("NppCorrectionAdapter skipped: not Windows platform.")
            return False

        try:
            client = NppBridgeClient()
            
            # 1. 获取上下文以验证文档 identity / text length
            ctx = client.get_context(request_id="gcoach-ctx-req")
            if not ctx.get("success"):
                logger.warning(f"NppBridgeClient get_context failed: {ctx.get('error')}")
                return False

            start = finding.start
            end = finding.end
            expected_original = finding.original
            replacement = finding.replacement

            # 2. 读取目标范围进行前置校验
            read_res = client.read_range(start, end, request_id="gcoach-read-req")
            if not read_res.get("success"):
                logger.warning(f"NppBridgeClient read_range failed: {read_res.get('error')}")
                return False

            actual_text = read_res.get("text", "")
            if actual_text != expected_original:
                logger.warning(f"NppBridgeClient stale target rejection: expected '{expected_original}', found '{actual_text}' at [{start}:{end}].")
                return False

            # 3. 请求桥接插件执行精确范围替换与硬后置验证
            rep_res = client.replace_range(
                start=start,
                end=end,
                expected_original=expected_original,
                replacement=replacement,
                request_id="gcoach-rep-req"
            )

            if not rep_res.get("success"):
                logger.warning(f"NppBridgeClient replace_range failed: {rep_res.get('error')}")
                return False

            logger.info(f"Successfully applied Notepad++ correction via NppBridgeClient at [{start}:{end}].")
            return True
        except Exception as e:
            logger.error(f"Failed to execute NppCorrectionAdapter correction: {e}", exc_info=True)
            return False
