"""Reconcile TPEG aggregate tables from retained case-level exact results."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import argparse
import csv
import json


def summarize(source: Path, dest: Path):
    rows = [json.loads(p.read_text()) for p in sorted(source.glob('tpeg-*.json'))]
    if len(rows) != 72 or len({r['id'] for r in rows}) != 72:
        raise ValueError('expected the fixed 72-case TPEG corpus')
    for row in rows:
        if row['exact_status'] != row['oracle_status']:
            raise ValueError('oracle mismatch')
        if row['certificate_kind'] is None:
            if row['exact_status'] != 'INSUFFICIENT':
                raise ValueError('missing certificate')
        elif row['checker_result'] != row['exact_status']:
            raise ValueError('checker mismatch')

    dest.mkdir(parents=True, exist_ok=True)
    family_fields = [
        'family', 'cases', 'proved', 'insufficient', 'inconsistent',
        'sink_zero_proved', 'uniform_cut_proved', 'signature_cover_certificates',
        'enumerated_states', 'admitted_states', 'unsafe_states'
    ]
    families = []
    for family in sorted({r['family'] for r in rows}):
        subset = [r for r in rows if r['family'] == family]
        families.append({
            'family': family,
            'cases': len(subset),
            'proved': sum(r['exact_status'] == 'PROVED' for r in subset),
            'insufficient': sum(r['exact_status'] == 'INSUFFICIENT' for r in subset),
            'inconsistent': sum(r['exact_status'] == 'INCONSISTENT' for r in subset),
            'sink_zero_proved': sum(r['sink_zero_status'] == 'PROVED' for r in subset),
            'uniform_cut_proved': sum(r['uniform_cut_status'] == 'PROVED' for r in subset),
            'signature_cover_certificates': sum(r['certificate_kind'] == 'signature_cover' for r in subset),
            'enumerated_states': sum(r['enumerated_states'] for r in subset),
            'admitted_states': sum(r['feasible_states'] for r in subset),
            'unsafe_states': sum(r['unsafe_states'] for r in subset),
        })
    with (dest / 'tpeg-families.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=family_fields)
        writer.writeheader(); writer.writerows(families)
    tex_lines = []
    for r in families:
        label = r['family'].replace('-', r'\mbox{-}')
        tex_lines.append(
            f"{label} & {r['cases']} & {r['proved']} & {r['insufficient']} & "
            f"{r['inconsistent']} & {r['sink_zero_proved']} & {r['uniform_cut_proved']} & "
            f"{r['signature_cover_certificates']} \\\\"
        )
    (dest / 'tpeg-families.tex').write_text('\n'.join(tex_lines) + '\n')

    methods = [
        {'method': 'sink-adjacent zero', 'proved': sum(r['sink_zero_status'] == 'PROVED' for r in rows)},
        {'method': 'uniform zero cut', 'proved': sum(r['uniform_cut_status'] == 'PROVED' for r in rows)},
        {'method': 'cut plus maximal-signature cover', 'proved': sum(r['exact_status'] == 'PROVED' for r in rows)},
    ]
    with (dest / 'tpeg-methods.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['method', 'proved'])
        writer.writeheader(); writer.writerows(methods)

    scaling = []
    for index, paths in zip(range(39, 45), range(1, 7)):
        r = next(v for v in rows if v['id'] == f'tpeg-{index:03}')
        scaling.append({
            'paths': paths,
            'enumerated_states': r['enumerated_states'],
            'distinct_signatures': r['distinct_signatures'],
            'maximal_signatures': r['maximal_signatures'],
            'certificate_bytes': r['certificate_bytes'],
            'producer_cpu_s': r['producer_cpu_s'],
            'checker_cpu_s': r['checker_cpu_s'],
        })
    with (dest / 'tpeg-scaling.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(scaling[0]))
        writer.writeheader(); writer.writerows(scaling)

    resources = [json.loads(p.read_text()) for p in sorted(source.glob('resources-*.json'))]
    summary = {
        'cases': len(rows),
        'exact': dict(Counter(r['exact_status'] for r in rows)),
        'certificates': dict(Counter(r['certificate_kind'] or 'none' for r in rows)),
        'sink_zero_proved': methods[0]['proved'],
        'uniform_cut_proved': methods[1]['proved'],
        'complete_finite_proved': methods[2]['proved'],
        'states_per_independent_enumerator': sum(r['enumerated_states'] for r in rows),
        'admitted_states': sum(r['feasible_states'] for r in rows),
        'unsafe_states': sum(r['unsafe_states'] for r in rows),
        'distinct_signature_sum': sum(r['distinct_signatures'] for r in rows),
        'cpu_s': sum(r['cpu_s'] for r in resources),
        'wall_s': sum(r['wall_s'] for r in resources),
        'peak_rss_kib': max(r['peak_rss_kib'] for r in resources),
        'certificate_bytes': {
            'sum': sum(r['certificate_bytes'] for r in rows),
            'min_nonzero': min(r['certificate_bytes'] for r in rows if r['certificate_bytes']),
            'max': max(r['certificate_bytes'] for r in rows),
        },
        'maxima': {key: max(r[key] for r in rows) for key in [
            'inputs', 'nodes', 'observables', 'inequalities', 'vertices', 'edges',
            'enumerated_states', 'feasible_states', 'distinct_signatures',
            'maximal_signatures', 'wall_s'
        ]},
    }
    (dest / 'tpeg-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='tpeg_results')
    parser.add_argument('--output', default='tables')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    print(json.dumps(summarize(root / args.source, root / args.output), indent=2))
