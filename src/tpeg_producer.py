"""Bounded exact producer for TPEG certificates; untrusted by tpeg_checker.py."""
from __future__ import annotations

from itertools import product
from typing import Any

import producer as arithmetic_producer
import tpeg_checker


def _serial_cert_for_zero(compiled: dict[str, Any], edge_id: str) -> dict[str, Any]:
    model = tpeg_checker._local_model(compiled, edge_id)
    try:
        result = arithmetic_producer.make(model, cap=50000)
        certificate = result['certificate']
        status = result['exact_status']
    except arithmetic_producer.Exhausted:
        A, b, c, q0 = arithmetic_producer.translate(model)
        status, _witness, certificate, _count = arithmetic_producer.finite_cover(model, A, b, c, q0)
    if status != 'PROVED' or certificate is None:
        raise AssertionError('universally closed cut edge lacks an arithmetic proof')
    return certificate


def _reach(compiled: dict[str, Any], open_edges: set[str]) -> list[int]:
    return tpeg_checker._structural_reachable(compiled['source'], compiled['edges'], open_edges)


def make(model: Any) -> dict[str, Any]:
    compiled = tpeg_checker.compile_model(model)
    signatures: set[tuple[str, ...]] = set()
    witness = None
    feasible = 0
    unsafe = 0
    max_open = 0
    for state in product(*(range(lo, hi + 1) for lo, hi in compiled['bounds'])):
        if not tpeg_checker._admitted(compiled, state):
            continue
        feasible += 1
        if witness is None:
            witness = list(state)
        sig = tpeg_checker._signature(compiled, state)
        signatures.add(sig)
        max_open = max(max_open, len(sig))
        reached = set(_reach(compiled, set(sig)))
        if any(v in reached for v in compiled['bad']):
            unsafe += 1

    sink_edges = {e['id'] for e in compiled['edges'] if e['head'] in set(compiled['bad'])}
    universal_zero = compiled['edge_ids'] - set().union(*(set(s) for s in signatures)) if signatures else set(compiled['edge_ids'])
    sink_zero_status = 'PROVED' if feasible and sink_edges <= universal_zero else 'INCONSISTENT' if not feasible else 'INSUFFICIENT'

    if feasible == 0:
        try:
            base = arithmetic_producer.make(compiled['base'])
            status, certificate = base['exact_status'], base['certificate']
        except arithmetic_producer.Exhausted:
            model = compiled['base']
            A, b, c, q0 = arithmetic_producer.translate(model)
            status, _witness, certificate, _count = arithmetic_producer.finite_cover(model, A, b, c, q0)
        if status != 'INCONSISTENT' or certificate is None:
            raise AssertionError('no arithmetic inconsistency certificate')
        return {
            'exact_status': 'INCONSISTENT',
            'sink_zero_status': 'INCONSISTENT',
            'uniform_cut_status': 'INCONSISTENT',
            'feasible_states': 0,
            'unsafe_states': 0,
            'distinct_signatures': 0,
            'maximal_signatures': 0,
            'max_open_edges': 0,
            'uniform_zero_edges': len(universal_zero),
            'certificate': {'kind': 'inconsistent', 'certificate': certificate},
        }

    if unsafe:
        return {
            'exact_status': 'INSUFFICIENT',
            'sink_zero_status': sink_zero_status,
            'uniform_cut_status': 'INSUFFICIENT',
            'feasible_states': feasible,
            'unsafe_states': unsafe,
            'distinct_signatures': len(signatures),
            'maximal_signatures': 0,
            'max_open_edges': max_open,
            'uniform_zero_edges': len(universal_zero),
            'certificate': None,
        }

    active = compiled['edge_ids'] - universal_zero
    reachable = _reach(compiled, active)
    if not any(v in set(reachable) for v in compiled['bad']):
        R = set(reachable)
        cut = sorted(e['id'] for e in compiled['edges'] if e['tail'] in R and e['head'] not in R)
        cert = {
            'kind': 'uniform_cut',
            'witness': witness,
            'reachable': reachable,
            'edge_proofs': [
                {'edge': edge_id, 'certificate': _serial_cert_for_zero(compiled, edge_id)}
                for edge_id in cut
            ],
        }
        return {
            'exact_status': 'PROVED',
            'sink_zero_status': sink_zero_status,
            'uniform_cut_status': 'PROVED',
            'feasible_states': feasible,
            'unsafe_states': 0,
            'distinct_signatures': len(signatures),
            'maximal_signatures': 1,
            'max_open_edges': max_open,
            'uniform_zero_edges': len(universal_zero),
            'certificate': cert,
        }

    # Local immutable views only: retain the enumerated tuples for output order.
    signature_sets = {sig: frozenset(sig) for sig in signatures}
    maximal = sorted(
        sig for sig in signatures
        if not any(signature_sets[sig] < other for other in signature_sets.values())
    )
    cert = {
        'kind': 'signature_cover',
        'witness': witness,
        'signatures': [
            {'open_edges': list(sig), 'reachable': _reach(compiled, set(sig))}
            for sig in maximal
        ],
    }
    return {
        'exact_status': 'PROVED',
        'sink_zero_status': sink_zero_status,
        'uniform_cut_status': 'INSUFFICIENT',
        'feasible_states': feasible,
        'unsafe_states': 0,
        'distinct_signatures': len(signatures),
        'maximal_signatures': len(maximal),
        'max_open_edges': max_open,
        'uniform_zero_edges': len(universal_zero),
        'certificate': cert,
    }
