"""Check entry-point gate dispatch without executing a reproduction campaign."""
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ReproductionGateTests(unittest.TestCase):
    def calls(self, args, code=0):
        with patch.object(sys, 'argv', [str(ROOT / 'reproduce.py'), *args]), \
             patch('subprocess.run', return_value=SimpleNamespace(returncode=code)) as child:
            if code:
                with self.assertRaises(SystemExit) as raised:
                    runpy.run_path(str(ROOT / 'reproduce.py'), run_name='__main__')
                self.assertEqual(raised.exception.code, code)
            else:
                runpy.run_path(str(ROOT / 'reproduce.py'), run_name='__main__')
            return [Path(call.args[0][1]).name for call in child.call_args_list]

    def test_full_routes_preserve_both_gates(self):
        for args in ([], ['--stage', 'all'], ['--stage=all'], ['--stage', 'validation']):
            with self.subTest(args=args):
                self.assertEqual(self.calls(args), ['reproduce_core.py', 'verify_research_records.py', 'final_code_audit.py'])

    def test_partial_routes_do_not_claim_final_validation(self):
        for stage in ('core', 'tpeg-middle', 'tpeg-tail'):
            with self.subTest(stage=stage):
                self.assertEqual(self.calls(['--stage', stage]), ['reproduce_core.py'])

    def test_core_failure_is_not_relabelled_success(self):
        self.assertEqual(self.calls(['--stage', 'all'], code=7), ['reproduce_core.py'])

    def test_gate_failure_propagates(self):
        import subprocess
        failure = subprocess.CalledProcessError(9, ['verify_research_records.py'])
        with patch.object(sys, 'argv', [str(ROOT / 'reproduce.py'), '--stage', 'all']), \
             patch('subprocess.run', side_effect=[SimpleNamespace(returncode=0), failure]):
            with self.assertRaises(subprocess.CalledProcessError):
                runpy.run_path(str(ROOT / 'reproduce.py'), run_name='__main__')


if __name__ == '__main__':
    unittest.main(verbosity=2)
