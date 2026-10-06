"""Owned graph regressions for output-sensitive path/reachability traversal."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'reviewer_hardening'))
sys.path.insert(0, str(ROOT / 'src'))
import path_budget as pb
import independent_path_budget as ipb
import tpeg_checker


def dead_diamonds(depth):
    nodes = ['s', 'b', 'd0']
    edges = [{'name': 'live', 'src': 's', 'dst': 'b', 'open': {'coeffs': {'x': 1}}},
             {'name': 'dead', 'src': 's', 'dst': 'd0', 'open': {'coeffs': {'x': 1}}}]
    for i in range(depth):
        a, b, end = f'a{i}', f'c{i}', f'd{i+1}'
        nodes.extend([a, b, end])
        for label, src, dst in [('a', f'd{i}', a), ('b', f'd{i}', b),
                                ('c', a, end), ('d', b, end)]:
            edges.append({'name': f'{i}_{label}', 'src': src, 'dst': dst,
                          'open': {'coeffs': {'x': 1}}})
    return {'name': 'dead-diamonds', 'variables': ['x'], 'bounds': {'x': [0, 1]},
            'nodes': nodes, 'source': 's', 'bad': 'b',
            'constraints': [{'name': 'closed', 'coeffs': {'x': 1}, 'rhs': 0}], 'edges': edges}


class PathEnumerationTests(unittest.TestCase):
    def test_one_bad_path_with_64_dead_diamonds(self):
        raw = dead_diamonds(64)
        cert = {'type': 'path_budget', 'model': raw['name'], 'witness': {'x': 0},
                'obligations': [{'path': ['live'], 'multipliers': {'closed': 1}}]}
        self.assertEqual(pb.canonical_paths(pb.parse_model(raw), 1), (('live',),))
        self.assertEqual(ipb._dag_paths(raw, 1)[0], (('live',),))
        self.assertEqual(pb.check_certificate(pb.parse_model(raw), cert, 1)['status'], 'PROVED')
        self.assertEqual(ipb.check(raw, cert, 1)['status'], 'PROVED')

    def test_structurally_unreachable_bad_skips_dead_diamonds(self):
        raw = dead_diamonds(64)
        raw['edges'] = [e for e in raw['edges'] if e['name'] != 'live']
        self.assertEqual(pb.canonical_paths(pb.parse_model(raw), 1), ())
        self.assertEqual(ipb._dag_paths(raw, 1)[0], ())

    def test_live_branch_still_counts_toward_path_cap(self):
        raw = dead_diamonds(3)
        raw['edges'].append({'name': 'finish', 'src': 'd3', 'dst': 'b',
                             'open': {'coeffs': {'x': 1}}})
        with self.assertRaises(pb.PathLimitExceeded):
            pb.canonical_paths(pb.parse_model(raw), 8)
        with self.assertRaises(ipb.IndependentError):
            ipb._dag_paths(raw, 8)
        self.assertEqual(len(pb.canonical_paths(pb.parse_model(raw), 9)), 9)
        self.assertEqual(len(ipb._dag_paths(raw, 9)[0]), 9)

    def test_reachability_scans_reverse_order_chain_once(self):
        class CountedEdges(list):
            scans = 0
            def __iter__(self):
                self.scans += 1
                return super().__iter__()
        edges = CountedEdges({'id': f'e{i}', 'tail': i, 'head': i+1} for i in reversed(range(63)))
        enabled = {f'e{i}' for i in range(63)}
        self.assertEqual(tpeg_checker._structural_reachable(0, edges, enabled), list(range(64)))
        self.assertEqual(edges.scans, 1)
        self.assertEqual(tpeg_checker._structural_reachable(0, edges, enabled - {'e31'}), list(range(32)))


if __name__ == '__main__':
    unittest.main(verbosity=2)
