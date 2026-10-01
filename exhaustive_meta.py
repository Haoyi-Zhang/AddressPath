#!/usr/bin/env python3
"""Exhaustively check the two combinatorial TPEG characterizations on tiny DAGs.

This script is intentionally independent of the certificate checker and
producer.  It enumerates all topologically ordered four-vertex graphs with at
most four edges, keeps graphs having a source-to-bad path, enumerates every
antichain of open-edge signatures, and compares direct reachability with:

1. maximal-signature sufficiency; and
2. the uniform-zero-cut characterization by independently enumerating every
   source-side vertex set and comparing it with union-graph reachability.

The check is finite evidence, not a machine-checked general proof.
"""
from __future__ import annotations

from itertools import combinations
import argparse
import json
from pathlib import Path
import resource
import time

VERTICES = 4
SOURCE = 0
BAD = 3
POSSIBLE_EDGES = tuple((u, v) for u in range(VERTICES) for v in range(u + 1, VERTICES))


def reaches_bad(edges: tuple[tuple[int, int], ...], opened: frozenset[int]) -> bool:
    reached = {SOURCE}
    changed = True
    while changed:
        changed = False
        for i, (u, v) in enumerate(edges):
            if i in opened and u in reached and v not in reached:
                reached.add(v)
                changed = True
    return BAD in reached



def source_side_sets():
    """All R with SOURCE in R and BAD not in R."""
    middle=[v for v in range(VERTICES) if v not in (SOURCE,BAD)]
    result=[]
    for mask in range(1<<len(middle)):
        r={SOURCE}
        for i,v in enumerate(middle):
            if mask & (1<<i): r.add(v)
        result.append(frozenset(r))
    return tuple(result)


def has_uniform_zero_cut(edges: tuple[tuple[int,int],...], active: frozenset[int]) -> tuple[bool,int]:
    checked=0; exists=False
    for r in source_side_sets():
        checked+=1
        crossing=[i for i,(u,v) in enumerate(edges) if u in r and v not in r]
        if all(i not in active for i in crossing):
            exists=True
    return exists,checked

def all_antichains(m: int):
    """Enumerate all nonempty antichains of subsets of ``range(m)``."""
    subsets = tuple(frozenset(i for i in range(m) if mask & (1 << i)) for mask in range(1 << m))
    for family_mask in range(1, 1 << len(subsets)):
        family = tuple(subsets[i] for i in range(len(subsets)) if family_mask & (1 << i))
        if all(not (a < b or b < a) for i, a in enumerate(family) for b in family[i + 1:]):
            yield family


def main(output: Path) -> None:
    t0 = time.perf_counter()
    c0 = time.process_time()
    graphs = antichains = signature_members = 0
    safe_families = unsafe_families = 0
    uniform_cut_families = cover_only_families = 0
    source_side_sets_checked = 0
    for m in range(1, 5):
        for chosen in combinations(POSSIBLE_EDGES, m):
            all_open = frozenset(range(m))
            if not reaches_bad(chosen, all_open):
                continue
            graphs += 1
            for maximal in all_antichains(m):
                antichains += 1
                signature_members += len(maximal)
                # An antichain is the exact set of maximal admitted signatures.
                maximal_safe = all(not reaches_bad(chosen, sig) for sig in maximal)
                # Downward closure is the corresponding admitted-signature family.
                admitted = {
                    frozenset(i for i in range(m) if mask & (1 << i))
                    for mask in range(1 << m)
                    if any(frozenset(i for i in range(m) if mask & (1 << i)) <= top for top in maximal)
                }
                direct_safe = all(not reaches_bad(chosen, sig) for sig in admitted)
                if maximal_safe != direct_safe:
                    raise AssertionError('maximal-signature characterization failed')

                active = frozenset().union(*admitted)
                union_safe = not reaches_bad(chosen, active)
                cut_exists,checked=has_uniform_zero_cut(chosen,active)
                source_side_sets_checked += checked
                if cut_exists != union_safe:
                    raise AssertionError('uniform-zero-cut characterization failed')
                if direct_safe:
                    safe_families += 1
                    if union_safe:
                        uniform_cut_families += 1
                    else:
                        cover_only_families += 1
                else:
                    unsafe_families += 1

    result = {
        'vertices': VERTICES,
        'possible_topological_edges': len(POSSIBLE_EDGES),
        'max_graph_edges': 4,
        'structurally_relevant_graphs': graphs,
        'maximal_signature_antichains': antichains,
        'signature_members_checked': signature_members,
        'safe_families': safe_families,
        'unsafe_families': unsafe_families,
        'uniform_cut_safe_families': uniform_cut_families,
        'signature_cover_only_safe_families': cover_only_families,
        'source_side_sets_per_family': len(source_side_sets()),
        'source_side_sets_checked': source_side_sets_checked,
        'checks': {
            'maximal_signature_characterization': 'PASS',
            'uniform_zero_cut_characterization': 'PASS',
        },
        'cpu_s': time.process_time() - c0,
        'wall_s': time.perf_counter() - t0,
        'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, default=Path('validation/meta-check.json'))
    args = ap.parse_args()
    main(args.output)
