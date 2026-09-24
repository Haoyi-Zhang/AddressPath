"""Direct finite TPEG oracle, independent of checker and producer modules."""
from __future__ import annotations

from fractions import Fraction
from itertools import product


def _values(model, state):
    values = []
    for node in model['accounting']['nodes']:
        if 'input' in node:
            value = Fraction(state[node['input']])
        else:
            value = Fraction(node['constant'])
            for parent, weight in node['terms']:
                value += Fraction(weight) * values[parent]
        values.append(value)
    return values


def _reach(graph, opened):
    reached = {graph['source']}
    changed = True
    while changed:
        changed = False
        for edge in graph['edges']:
            if edge['id'] in opened and edge['tail'] in reached and edge['head'] not in reached:
                reached.add(edge['head'])
                changed = True
    return reached


def evaluate(model):
    accounting = model['accounting']
    bounds = accounting['domain']['bounds']
    total = feasible = unsafe = 0
    signatures = set()
    for state in product(*(range(lo, hi + 1) for lo, hi in bounds)):
        total += 1
        values = _values(model, state)
        admitted = True
        for interval in accounting['assumptions'] + accounting['observations']:
            value = values[interval['node']]
            if value < Fraction(interval['lower']) or value > Fraction(interval['upper']):
                admitted = False
                break
        if not admitted:
            continue
        feasible += 1
        opened = tuple(edge['id'] for edge in model['graph']['edges'] if values[edge['residual_node']] >= 1)
        signatures.add(opened)
        reached = _reach(model['graph'], set(opened))
        if any(v in reached for v in model['graph']['bad_vertices']):
            unsafe += 1
    status = 'INCONSISTENT' if feasible == 0 else 'INSUFFICIENT' if unsafe else 'PROVED'
    return {
        'status': status,
        'states': total,
        'feasible_states': feasible,
        'unsafe_states': unsafe,
        'distinct_signatures': len(signatures),
    }
