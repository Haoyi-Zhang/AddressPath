"""Run both exact certificate suites and retain resource/check counts."""
from __future__ import annotations

import argparse
import io
import json
import os
import resource
import sys
import time
import unittest
from math import prod
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'src'))
import checker
import test_checker
import test_tpeg_checker
import tpeg_checker


def main(output: Path):
    allowed = sorted(os.sched_getaffinity(0)); os.sched_setaffinity(0, {allowed[0]})
    resource.setrlimit(resource.RLIMIT_CPU, (110, 115))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    counts = {
        'arithmetic_certificate_calls': 0,
        'tpeg_certificate_calls': 0,
        'accepted': 0,
        'rejected': 0,
        'finite_cover_state_visit_upper_bound': 0,
        'signature_cover_state_visit_upper_bound': 0,
    }
    original_arithmetic = checker.verify
    original_tpeg = tpeg_checker.verify

    def counted_arithmetic(model, cert):
        counts['arithmetic_certificate_calls'] += 1
        if isinstance(cert, dict) and cert.get('kind') == 'finite_cover':
            counts['finite_cover_state_visit_upper_bound'] += len(cert.get('cover', []))
        try:
            value = original_arithmetic(model, cert); counts['accepted'] += 1; return value
        except (ValueError, OverflowError):
            counts['rejected'] += 1; raise

    def counted_tpeg(model, cert):
        counts['tpeg_certificate_calls'] += 1
        if isinstance(cert, dict) and cert.get('kind') == 'signature_cover':
            try:
                bounds = model['accounting']['domain']['bounds']
                counts['signature_cover_state_visit_upper_bound'] += prod(hi - lo + 1 for lo, hi in bounds)
            except Exception:
                pass
        try:
            value = original_tpeg(model, cert); counts['accepted'] += 1; return value
        except (ValueError, OverflowError):
            counts['rejected'] += 1; raise

    checker.verify = counted_arithmetic
    tpeg_checker.verify = counted_tpeg
    stream = io.StringIO(); cpu = time.process_time(); wall = time.monotonic()
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromModule(test_checker),
        unittest.defaultTestLoader.loadTestsFromModule(test_tpeg_checker),
    ])
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    summary = {
        'methods': result.testsRun,
        'passed': result.wasSuccessful(),
        'failures': len(result.failures),
        'errors': len(result.errors),
        'cpu_s': time.process_time() - cpu,
        'wall_s': time.monotonic() - wall,
        'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        **counts,
    }
    summary['certificate_calls'] = summary['arithmetic_certificate_calls'] + summary['tpeg_certificate_calls']
    output.mkdir(parents=True, exist_ok=True)
    (output / 'tests.txt').write_text(stream.getvalue())
    (output / 'tests.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='validation')
    main(ROOT / parser.parse_args().output)
