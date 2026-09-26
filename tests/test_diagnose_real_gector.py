"""
Unit test for tools/diagnose_real_gector.py
"""

import unittest
from pathlib import Path
from tools.diagnose_real_gector import run_diagnostic


class TestDiagnoseRealGector(unittest.TestCase):
    def test_diagnostic_script_runs_without_error(self):
        # Verify diagnostic runs successfully in simulation fallback mode without crashing
        try:
            run_diagnostic()
        except Exception as e:
            self.fail(f"diagnose_real_gector raised an exception in fallback mode: {e}")


if __name__ == "__main__":
    unittest.main()
