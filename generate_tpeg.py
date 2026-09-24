"""Generate deterministic benign TPEG models for path-isolation certificates."""
from __future__ import annotations

from fractions import Fraction as F
from pathlib import Path
import argparse
import json


def serial(value):
    value = F(value)
    return str(value.numerator) if value.denominator == 1 else str(value)


def input_nodes(d):
    return [{'input': i} for i in range(d)]


def add(nodes, terms, constant=0):
    nodes.append({'constant': serial(constant), 'terms': [[i, serial(w)] for i, w in terms]})
    return len(nodes) - 1


def interval(node, lower, upper):
    return {'node': node, 'lower': serial(lower), 'upper': serial(upper)}


def edge(i, tail, head, residual):
    return {'id': f'e{i:02}', 'tail': tail, 'head': head, 'residual_node': residual}


def model(family, bounds, nodes, observations, vertices, source, bad, edges, assumptions=None):
    return {
        'id': '',
        'family': family,
        'accounting': {
            'domain': {'kind': 'integer_grid', 'bounds': bounds},
            'nodes': nodes,
            'observations': observations,
            'assumptions': assumptions or [],
        },
        'graph': {
            'vertices': vertices,
            'source': source,
            'bad_vertices': bad,
            'edges': edges,
        },
    }


def all_cases():
    out = []

    # Address-accounting window: total=safe+foreign, and the foreign-use edge
    # is open exactly when the integer residual is positive.
    for n in range(1, 5):
        for width in [F(0), F(1, 4), F(3, 4), F(1), F(5, 4)]:
            nodes = input_nodes(2)  # safe, foreign
            total = add(nodes, [(0, 1), (1, 1)])
            observations = [interval(total, n, n), interval(0, n - width, n + width)]
            out.append(model(
                'accounting-window', [[0, n + 1], [0, n + 1]], nodes, observations,
                ['request', 'foreign-use'], 0, [1], [edge(0, 0, 1, 1)]
            ))

    # A source-side cut proves both branches closed while sink-adjacent events
    # remain unconstrained.  This separates uniform cuts from a sink-zero rule.
    for high in [1, 2, 3]:
        for width in [F(0), F(3, 4)]:
            nodes = input_nodes(4)
            observations = [interval(0, 0, width), interval(2, 0, width)]
            edges = [edge(0, 0, 1, 0), edge(1, 0, 2, 2), edge(2, 1, 3, 1), edge(3, 2, 3, 3)]
            out.append(model(
                'source-cut', [[0, high]] * 4, nodes, observations,
                ['request', 'hit-arm', 'walk-arm', 'foreign-use'], 0, [3], edges
            ))

    # Two three-edge paths share no cut edge.  The middle layer is closed, so a
    # valid cut exists strictly before the sink-adjacent layer.
    for high in [1, 2, 3]:
        for width in [F(0), F(3, 4)]:
            nodes = input_nodes(6)
            observations = [interval(1, 0, width), interval(4, 0, width)]
            edges = [
                edge(0, 0, 1, 0), edge(1, 0, 2, 3),
                edge(2, 1, 3, 1), edge(3, 2, 4, 4),
                edge(4, 3, 5, 2), edge(5, 4, 5, 5),
            ]
            out.append(model(
                'interior-cut', [[0, high]] * 6, nodes, observations,
                ['request', 'hit', 'walk', 'hit-merge', 'walk-merge', 'foreign-use'],
                0, [5], edges
            ))

    # A branched lookup/replay graph is blocked at the merge-to-owner boundary.
    for bounds in [([[0, 1]] * 7), ([[0, 2]] * 7), ([[0, 3]] * 5 + [[0, 1]] * 2)]:
        for width in [F(0), F(3, 4)]:
            nodes = input_nodes(7)
            observations = [interval(5, 0, width)]
            edges = [
                edge(0, 0, 1, 0), edge(1, 1, 2, 1), edge(2, 1, 3, 2),
                edge(3, 2, 4, 3), edge(4, 3, 4, 4),
                edge(5, 4, 5, 5), edge(6, 5, 6, 6),
            ]
            out.append(model(
                'merge-boundary-cut', bounds, nodes, observations,
                ['request', 'lookup', 'hit', 'walk-or-replay', 'merge', 'owner-check', 'foreign-use'],
                0, [6], edges
            ))

    # No edge is universally zero.  Each state opens exactly one edge of every
    # two-edge path, so all states are safe but a single uniform cut is absent.
    # Six irrelevant accounting bits create a 4,096-state, 64-signature case.
    for paths in range(1, 7):
        extra = 12 - paths
        d = paths + extra
        nodes = input_nodes(d)
        complements = [add(nodes, [(i, -1)], 1) for i in range(paths)]
        vertices = ['request'] + [f'arm-{i+1}' for i in range(paths)] + ['foreign-use']
        bad = len(vertices) - 1
        edges = []
        for i in range(paths):
            edges.append(edge(2 * i, 0, 1 + i, i))
            edges.append(edge(2 * i + 1, 1 + i, bad, complements[i]))
        out.append(model(
            'alternating-cut-cover', [[0, 1]] * d, nodes, [], vertices, 0, [bad], edges
        ))

    # A hidden direct bypass remains open even when the visible path is closed.
    # These are benign model-level negative controls, not hardware traces.
    for high in [1, 2]:
        for visible_width in [F(0), F(3, 4)]:
            for bypass_upper in [1, 2]:
                nodes = input_nodes(3)
                observations = [interval(0, 0, visible_width), interval(2, 0, bypass_upper)]
                edges = [edge(0, 0, 1, 0), edge(1, 0, 2, 2), edge(2, 1, 2, 1)]
                out.append(model(
                    'hidden-bypass', [[0, high], [0, high], [0, high]], nodes, observations,
                    ['request', 'visible-check', 'foreign-use'], 0, [2], edges
                ))

    # Wide intervals admit a complete open path and must force abstention.
    for high in [1, 2, 3]:
        for lower in [0, 1]:
            nodes = input_nodes(2)
            observations = [interval(0, lower, high), interval(1, lower, high)]
            out.append(model(
                'wide-path', [[0, high], [0, high]], nodes, observations,
                ['request', 'translation-stage', 'foreign-use'], 0, [2],
                [edge(0, 0, 1, 0), edge(1, 1, 2, 1)]
            ))

    # Inconsistent evidence is diagnosed separately from a safety proof.
    for high in [1, 2, 3, 4]:
        for extra in [0, 1]:
            d = 1 + extra
            nodes = input_nodes(d)
            observations = [interval(0, 0, 0), interval(0, 1, 1)]
            out.append(model(
                'inconsistent-evidence', [[0, high]] + ([[0, 1]] if extra else []), nodes, observations,
                ['request', 'foreign-use'], 0, [1], [edge(0, 0, 1, 0)]
            ))

    # Two declared bad uses are jointly separated by source-side zeros.
    for high in [1, 2, 3]:
        for width in [F(0), F(3, 4)]:
            nodes = input_nodes(4)
            observations = [interval(0, 0, width), interval(2, 0, width)]
            edges = [edge(0, 0, 1, 0), edge(1, 0, 2, 2), edge(2, 1, 3, 1), edge(3, 2, 4, 3)]
            out.append(model(
                'multi-bad-cut', [[0, high]] * 4, nodes, observations,
                ['request', 'stage-a', 'stage-b', 'foreign-use-a', 'foreign-use-b'],
                0, [3, 4], edges
            ))

    for i, item in enumerate(out, 1):
        item['id'] = f'tpeg-{i:03}'
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', default='tpeg_cases')
    args = ap.parse_args()
    dest = Path(args.output)
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob('tpeg-*.json'):
        old.unlink()
    cases = all_cases()
    for item in cases:
        (dest / f"{item['id']}.json").write_text(json.dumps(item, indent=2) + '\n', encoding='utf-8')
    print(f'{len(cases)} TPEG models written to {dest}')
