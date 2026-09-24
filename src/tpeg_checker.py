"""Independent checker for Translation-Path Evidence Graph (TPEG) certificates.

The checker accepts finite integer accounting models and a directed acyclic path
schema.  Each edge is enabled by a nonnegative integer affine residual.  It
checks three certificate forms:

* ``uniform_cut``: every edge leaving an explicit source-side cut is proved
  identically zero by a separately checked arithmetic certificate;
* ``signature_cover``: the maximal admitted open-edge signatures are listed and
  each has no path to a declared bad vertex;
* ``inconsistent``: the accounting constraints have no admitted state.

No certificate producer or optimizer is imported here.  Finite enumeration is
bounded by the base schema's 4,096-state admission limit.
"""
from __future__ import annotations

from fractions import Fraction as F
from itertools import product
from pathlib import Path
from typing import Any

import checker as arithmetic

MAX_VERTICES = 64
MAX_EDGES = 64
MAX_SIGNATURES = 4096

Invalid = arithmetic.Invalid


def _keys(value: Any, expected: set[str], what: str) -> None:
    if type(value) is not dict or set(value) != expected:
        raise Invalid(f'{what}: missing or unexpected fields')


def _sorted_unique_ints(value: Any, lo: int, hi: int, what: str) -> list[int]:
    if type(value) is not list:
        raise Invalid(f'{what}: expected list')
    out = [arithmetic.integer(v, lo, hi) for v in value]
    if out != sorted(set(out)):
        raise Invalid(f'{what}: must be sorted and unique')
    return out


def _sorted_unique_strings(value: Any, allowed: set[str], what: str) -> list[str]:
    if type(value) is not list or any(type(v) is not str or v not in allowed for v in value):
        raise Invalid(f'{what}: invalid edge identifier list')
    if value != sorted(set(value)):
        raise Invalid(f'{what}: must be sorted and unique')
    return value


def _base_model(model: dict[str, Any], assertion_node: int = 0, upper: Any = 0) -> dict[str, Any]:
    accounting = model['accounting']
    return {
        'id': model['id'],
        'family': model['family'],
        'domain': accounting['domain'],
        'nodes': accounting['nodes'],
        'observations': accounting['observations'],
        'assumptions': accounting['assumptions'],
        'assertion': {'node': assertion_node, 'upper': upper},
    }


def _compile_forms(nodes: list[dict[str, Any]], d: int) -> list[tuple[list[F], F]]:
    """Compile affine forms after the base checker has validated node syntax."""
    forms: list[tuple[list[F], F]] = []
    for i, node in enumerate(nodes):
        if i < d:
            forms.append(([F(int(j == i)) for j in range(d)], F(0)))
            continue
        vec, off = [F(0)] * d, arithmetic.rational(node['constant'])
        for parent, raw_coeff in node['terms']:
            coeff = arithmetic.rational(raw_coeff)
            pvec, poff = forms[parent]
            vec = [a + coeff * b for a, b in zip(vec, pvec)]
            off += coeff * poff
        forms.append((vec, off))
    return forms


def _box_minimum(form: tuple[list[F], F], bounds: list[tuple[int, int]]) -> F:
    coeffs, off = form
    return off + sum((c * (lo if c >= 0 else hi) for c, (lo, hi) in zip(coeffs, bounds)), F(0))


def _structural_reachable(source: int, edges: list[dict[str, Any]], enabled: set[str]) -> list[int]:
    reached = {source}
    changed = True
    while changed:
        changed = False
        for edge in edges:
            if edge['id'] in enabled and edge['tail'] in reached and edge['head'] not in reached:
                reached.add(edge['head'])
                changed = True
    return sorted(reached)


def compile_model(model: Any) -> dict[str, Any]:
    _keys(model, {'id', 'family', 'accounting', 'graph'}, 'model')
    if type(model['id']) is not str or not model['id'] or len(model['id']) > 64:
        raise Invalid('invalid model id')
    if type(model['family']) is not str or not model['family'] or len(model['family']) > 64:
        raise Invalid('invalid family')

    accounting = model['accounting']
    _keys(accounting, {'domain', 'nodes', 'observations', 'assumptions'}, 'accounting')
    base = _base_model(model)
    bounds, A, b, _, _ = arithmetic.compile_model(base)
    d = len(bounds)
    forms = _compile_forms(accounting['nodes'], d)

    graph = model['graph']
    _keys(graph, {'vertices', 'source', 'bad_vertices', 'edges'}, 'graph')
    vertices = graph['vertices']
    if type(vertices) is not list or not 2 <= len(vertices) <= MAX_VERTICES:
        raise Invalid('vertex budget')
    if any(type(v) is not str or not v or len(v) > 48 for v in vertices):
        raise Invalid('invalid vertex label')
    if len(set(vertices)) != len(vertices):
        raise Invalid('duplicate vertex label')
    source = arithmetic.integer(graph['source'], 0, len(vertices) - 1)
    bad = _sorted_unique_ints(graph['bad_vertices'], 0, len(vertices) - 1, 'bad vertices')
    if not bad or source in bad:
        raise Invalid('bad vertices must be nonempty and exclude the source')

    raw_edges = graph['edges']
    if type(raw_edges) is not list or not 1 <= len(raw_edges) <= MAX_EDGES:
        raise Invalid('edge budget')
    edges: list[dict[str, Any]] = []
    ids: set[str] = set()
    for raw in raw_edges:
        _keys(raw, {'id', 'tail', 'head', 'residual_node'}, 'edge')
        edge_id = raw['id']
        if type(edge_id) is not str or not edge_id or len(edge_id) > 48 or edge_id in ids:
            raise Invalid('invalid or duplicate edge id')
        ids.add(edge_id)
        tail = arithmetic.integer(raw['tail'], 0, len(vertices) - 1)
        head = arithmetic.integer(raw['head'], 0, len(vertices) - 1)
        if tail >= head:
            raise Invalid('edges must follow the declared topological vertex order')
        residual = arithmetic.integer(raw['residual_node'], 0, len(forms) - 1)
        coeffs, off = forms[residual]
        if any(v.denominator != 1 for v in [*coeffs, off]):
            raise Invalid('edge residual must be integer-valued on the integer grid')
        if _box_minimum(forms[residual], bounds) < 0:
            raise Invalid('edge residual must be nonnegative over the declared input box')
        edges.append({'id': edge_id, 'tail': tail, 'head': head, 'residual_node': residual})
    if [e['id'] for e in edges] != sorted(e['id'] for e in edges):
        raise Invalid('edges must be sorted by id')

    all_ids = {e['id'] for e in edges}
    structurally_reached = set(_structural_reachable(source, edges, all_ids))
    if not any(v in structurally_reached for v in bad):
        raise Invalid('the declared bad set is structurally unreachable')

    return {
        'model': model,
        'base': base,
        'bounds': bounds,
        'A': A,
        'b': b,
        'forms': forms,
        'vertices': vertices,
        'source': source,
        'bad': bad,
        'edges': edges,
        'edge_ids': all_ids,
    }


def _admitted(compiled: dict[str, Any], state: tuple[int, ...] | list[int]) -> bool:
    return all(arithmetic.dot(row, state) <= rhs for row, rhs in zip(compiled['A'], compiled['b']))


def _witness(compiled: dict[str, Any], value: Any) -> list[int]:
    bounds = compiled['bounds']
    if type(value) is not list or len(value) != len(bounds):
        raise Invalid('consistency witness shape')
    state = [arithmetic.integer(v, lo, hi) for v, (lo, hi) in zip(value, bounds)]
    if not _admitted(compiled, state):
        raise Invalid('consistency witness is not admitted')
    return state


def _value(form: tuple[list[F], F], state: tuple[int, ...] | list[int]) -> F:
    coeffs, off = form
    return arithmetic.dot(coeffs, state) + off


def _signature(compiled: dict[str, Any], state: tuple[int, ...] | list[int]) -> tuple[str, ...]:
    opened = [
        edge['id']
        for edge in compiled['edges']
        if _value(compiled['forms'][edge['residual_node']], state) >= 1
    ]
    return tuple(opened)


def _local_model(compiled: dict[str, Any], edge_id: str) -> dict[str, Any]:
    edge = next((e for e in compiled['edges'] if e['id'] == edge_id), None)
    if edge is None:
        raise Invalid('unknown cut edge')
    return _base_model(compiled['model'], assertion_node=edge['residual_node'], upper=0)


def _verify_uniform_cut(compiled: dict[str, Any], cert: dict[str, Any]) -> str:
    _keys(cert, {'kind', 'witness', 'reachable', 'edge_proofs'}, 'uniform-cut certificate')
    _witness(compiled, cert['witness'])
    reachable = _sorted_unique_ints(cert['reachable'], 0, len(compiled['vertices']) - 1, 'reachable set')
    R = set(reachable)
    if compiled['source'] not in R or any(v in R for v in compiled['bad']):
        raise Invalid('cut must contain the source and exclude every bad vertex')

    expected = sorted(
        e['id'] for e in compiled['edges'] if e['tail'] in R and e['head'] not in R
    )
    raw_proofs = cert['edge_proofs']
    if type(raw_proofs) is not list:
        raise Invalid('edge proofs must be a list')
    proof_ids: list[str] = []
    for item in raw_proofs:
        _keys(item, {'edge', 'certificate'}, 'edge proof')
        edge_id = item['edge']
        if type(edge_id) is not str or edge_id not in compiled['edge_ids']:
            raise Invalid('unknown edge proof id')
        proof_ids.append(edge_id)
        result = arithmetic.verify(_local_model(compiled, edge_id), item['certificate'])
        if result != 'PROVED':
            raise Invalid('cut-edge arithmetic certificate does not prove zero')
    if proof_ids != expected:
        raise Invalid('edge proofs must exactly match the sorted outgoing cut')
    if not expected:
        raise Invalid('empty outgoing cut cannot separate a structurally reachable bad vertex')
    return 'PROVED'


def _verify_signature_cover(compiled: dict[str, Any], cert: dict[str, Any]) -> str:
    _keys(cert, {'kind', 'witness', 'signatures'}, 'signature-cover certificate')
    _witness(compiled, cert['witness'])
    raw_entries = cert['signatures']
    if type(raw_entries) is not list or not 1 <= len(raw_entries) <= MAX_SIGNATURES:
        raise Invalid('signature budget')

    supplied: list[tuple[str, ...]] = []
    supplied_reach: dict[tuple[str, ...], list[int]] = {}
    for entry in raw_entries:
        _keys(entry, {'open_edges', 'reachable'}, 'signature entry')
        open_edges = tuple(_sorted_unique_strings(entry['open_edges'], compiled['edge_ids'], 'open edges'))
        reachable = _sorted_unique_ints(entry['reachable'], 0, len(compiled['vertices']) - 1, 'signature reachability')
        exact_reachable = _structural_reachable(compiled['source'], compiled['edges'], set(open_edges))
        if reachable != exact_reachable:
            raise Invalid('signature reachability is not canonical')
        if any(v in set(reachable) for v in compiled['bad']):
            raise Invalid('listed signature reaches a bad vertex')
        supplied.append(open_edges)
        supplied_reach[open_edges] = reachable
    if supplied != sorted(set(supplied)):
        raise Invalid('signature entries must be sorted and unique')

    admitted_signatures: set[tuple[str, ...]] = set()
    for state in product(*(range(lo, hi + 1) for lo, hi in compiled['bounds'])):
        if _admitted(compiled, state):
            admitted_signatures.add(_signature(compiled, state))
    if not admitted_signatures:
        raise Invalid('signature cover cannot prove an inconsistent model')
    maximal = sorted(
        sig for sig in admitted_signatures
        if not any(set(sig) < set(other) for other in admitted_signatures)
    )
    if supplied != maximal:
        raise Invalid('certificate must list exactly the maximal admitted signatures')
    return 'PROVED'


def verify(model: Any, cert: Any) -> str:
    compiled = compile_model(model)
    if type(cert) is not dict or type(cert.get('kind')) is not str:
        raise Invalid('certificate envelope')
    kind = cert['kind']
    if kind == 'uniform_cut':
        return _verify_uniform_cut(compiled, cert)
    if kind == 'signature_cover':
        return _verify_signature_cover(compiled, cert)
    if kind == 'inconsistent':
        _keys(cert, {'kind', 'certificate'}, 'inconsistency certificate')
        if arithmetic.verify(compiled['base'], cert['certificate']) != 'INCONSISTENT':
            raise Invalid('embedded arithmetic certificate is not an inconsistency proof')
        return 'INCONSISTENT'
    raise Invalid('unsupported TPEG proof kind')


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('model')
    ap.add_argument('certificate')
    args = ap.parse_args()
    try:
        print(verify(arithmetic.load(Path(args.model)), arithmetic.load(Path(args.certificate))))
    except (Invalid, ValueError, OverflowError) as exc:
        raise SystemExit('INVALID_CERTIFICATE: ' + str(exc))
