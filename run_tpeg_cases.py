"""Run one bounded TPEG case group and retain aggregate, non-offensive evidence."""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import os
import resource
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
import checker
import tpeg_checker
import tpeg_oracle
import tpeg_producer


def run(ids, output, root):
    allowed = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {allowed[0]})
    resource.setrlimit(resource.RLIMIT_CPU, (110, 115))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    output.mkdir(parents=True, exist_ok=True)
    (output / 'certificates').mkdir(exist_ok=True)
    start = time.monotonic()
    cpu_start = time.process_time()
    results = []
    for name in ids:
        if time.monotonic() - start > 100:
            raise RuntimeError('chunk wall budget exceeded')
        model = checker.load(root / 'tpeg_cases' / f'{name}.json')
        begin = time.monotonic()
        t = time.process_time()
        result = tpeg_producer.make(model)
        producer_cpu = time.process_time() - t
        t = time.process_time()
        reference = tpeg_oracle.evaluate(model)
        oracle_cpu = time.process_time() - t
        if any([
            reference['status'] != result['exact_status'],
            reference['feasible_states'] != result['feasible_states'],
            reference['unsafe_states'] != result['unsafe_states'],
            reference['distinct_signatures'] != result['distinct_signatures'],
        ]):
            raise AssertionError('direct finite TPEG oracle disagreement')
        cert = result.pop('certificate')
        t = time.process_time()
        if cert is not None:
            checked = tpeg_checker.verify(model, cert)
            if checked != result['exact_status']:
                raise AssertionError('TPEG checker disagreement')
            cert_path = output / 'certificates' / f'{name}.json'
            cert_path.write_text(json.dumps(cert, indent=2) + '\n', encoding='utf-8')
            certificate_bytes = cert_path.stat().st_size
        else:
            checked = 'NO_CERTIFICATE'
            certificate_bytes = 0
        checker_cpu = time.process_time() - t
        compiled = tpeg_checker.compile_model(model)
        result.update({
            'id': name,
            'family': model['family'],
            'oracle_status': reference['status'],
            'enumerated_states': reference['states'],
            'checker_result': checked,
            'certificate_kind': None if cert is None else cert['kind'],
            'certificate_bytes': certificate_bytes,
            'producer_cpu_s': producer_cpu,
            'oracle_cpu_s': oracle_cpu,
            'checker_cpu_s': checker_cpu,
            'wall_s': time.monotonic() - begin,
            'inputs': len(compiled['bounds']),
            'nodes': len(model['accounting']['nodes']),
            'observables': len(model['accounting']['observations']),
            'inequalities': len(compiled['A']),
            'vertices': len(compiled['vertices']),
            'edges': len(compiled['edges']),
        })
        (output / f'{name}.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        results.append(result)
    usage = {
        'cases': ids,
        'workers': 1,
        'cpu_s': time.process_time() - cpu_start,
        'wall_s': time.monotonic() - start,
        'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'states_per_independent_enumerator': sum(r['enumerated_states'] for r in results),
        'admitted_states': sum(r['feasible_states'] for r in results),
        'certificates_checked': sum(r['certificate_kind'] is not None for r in results),
    }
    (output / f"resources-{ids[0]}-{ids[-1]}.json").write_text(json.dumps(usage, indent=2) + '\n')
    print(json.dumps(usage))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ids', nargs='+')
    ap.add_argument('--start', type=int, default=1)
    ap.add_argument('--end', type=int, default=16)
    ap.add_argument('--output', default='tpeg_results')
    args = ap.parse_args()
    ids = args.ids or [f'tpeg-{i:03}' for i in range(args.start, args.end + 1)]
    run(ids, ROOT / args.output, ROOT)
