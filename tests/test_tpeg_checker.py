"""Regression and adversarial mutation checks for the TPEG verifier."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import checker
import tpeg_checker
import tpeg_oracle


def model(i):
    return checker.load(ROOT / 'tpeg_cases' / f'tpeg-{i:03}.json')


def cert(i):
    return checker.load(ROOT / 'tpeg_results' / 'certificates' / f'tpeg-{i:03}.json')


class TPEGCheckerTests(unittest.TestCase):
    def reject(self, m, c):
        with self.assertRaises((checker.Invalid, ValueError, OverflowError)):
            tpeg_checker.verify(m, c)

    def test_all_retained_certificates(self):
        for path in sorted((ROOT / 'tpeg_results' / 'certificates').glob('tpeg-*.json')):
            with self.subTest(case=path.stem):
                m = checker.load(ROOT / 'tpeg_cases' / path.name)
                c = checker.load(path)
                expected = json.loads((ROOT / 'tpeg_results' / path.name).read_text())['exact_status']
                self.assertEqual(tpeg_checker.verify(m, c), expected)

    def test_independent_oracle_matches_all_results(self):
        for path in sorted((ROOT / 'tpeg_results').glob('tpeg-*.json')):
            with self.subTest(case=path.stem):
                m = checker.load(ROOT / 'tpeg_cases' / path.name)
                retained = json.loads(path.read_text())
                reference = tpeg_oracle.evaluate(m)
                self.assertEqual(reference['status'], retained['exact_status'])
                self.assertEqual(reference['feasible_states'], retained['feasible_states'])
                self.assertEqual(reference['unsafe_states'], retained['unsafe_states'])
                self.assertEqual(reference['distinct_signatures'], retained['distinct_signatures'])

    def test_unknown_certificate_kind(self):
        c = cert(21); c['kind'] = 'trusted'
        self.reject(model(21), c)

    def test_uniform_cut_requires_source(self):
        c = cert(21); c['reachable'] = []
        self.reject(model(21), c)

    def test_uniform_cut_excludes_bad(self):
        c = cert(21); c['reachable'] = [0, 3]
        self.reject(model(21), c)

    def test_uniform_cut_missing_edge_proof(self):
        c = cert(21); c['edge_proofs'].pop()
        self.reject(model(21), c)

    def test_uniform_cut_extra_edge_proof(self):
        c = cert(21); c['edge_proofs'].append(copy.deepcopy(c['edge_proofs'][0]))
        self.reject(model(21), c)

    def test_uniform_cut_wrong_edge_identifier(self):
        c = cert(21); c['edge_proofs'][0]['edge'] = 'e02'
        self.reject(model(21), c)

    def test_uniform_cut_rejects_forged_local_proof(self):
        c = cert(21)
        c['edge_proofs'][0]['certificate']['multipliers'] = [0] * len(c['edge_proofs'][0]['certificate']['multipliers'])
        self.reject(model(21), c)

    def test_uniform_cut_rejects_infeasible_witness(self):
        c = cert(21); c['witness'] = [1, 0, 0, 0]
        self.reject(model(21), c)

    def test_widened_observation_invalidates_cut_proof(self):
        m = model(21); m['accounting']['observations'][0]['upper'] = 1
        self.reject(m, cert(21))

    def test_signature_cover_missing_maximal_signature(self):
        c = cert(39); c['signatures'].pop()
        self.reject(model(39), c)

    def test_signature_cover_rejects_duplicate_signature(self):
        c = cert(39); c['signatures'].append(copy.deepcopy(c['signatures'][-1]))
        self.reject(model(39), c)

    def test_signature_cover_rejects_noncanonical_reachability(self):
        c = cert(39); c['signatures'][0]['reachable'] = [0]
        self.reject(model(39), c)

    def test_signature_cover_rejects_bad_path(self):
        c = cert(39)
        c['signatures'][0]['open_edges'] = ['e00', 'e01']
        c['signatures'][0]['reachable'] = [0, 1, 2]
        self.reject(model(39), c)

    def test_signature_cover_rejects_unsorted_edges(self):
        c = cert(44)
        c['signatures'][0]['open_edges'] = list(reversed(c['signatures'][0]['open_edges']))
        self.reject(model(44), c)

    def test_signature_cover_cannot_prove_hidden_bypass(self):
        self.reject(model(45), cert(39))

    def test_inconsistency_certificate_wrong_model(self):
        self.reject(model(1), cert(59))

    def test_inconsistency_certificate_cannot_gain_witness(self):
        c = cert(59); c['witness'] = [0]
        self.reject(model(59), c)

    def test_edge_cycle_rejected(self):
        m = model(21); m['graph']['edges'][0]['tail'] = 1; m['graph']['edges'][0]['head'] = 0
        self.reject(m, cert(21))

    def test_duplicate_edge_identifier_rejected(self):
        m = model(21); m['graph']['edges'][1]['id'] = m['graph']['edges'][0]['id']
        self.reject(m, cert(21))

    def test_unsorted_edges_rejected(self):
        m = model(21); m['graph']['edges'][0], m['graph']['edges'][1] = m['graph']['edges'][1], m['graph']['edges'][0]
        self.reject(m, cert(21))

    def test_source_cannot_be_bad(self):
        m = model(21); m['graph']['bad_vertices'] = [0]
        self.reject(m, cert(21))

    def test_structurally_unreachable_bad_rejected(self):
        m = model(21)
        m['graph']['edges'] = [e for e in m['graph']['edges'] if e['head'] != 3]
        self.reject(m, cert(21))

    def test_fractional_residual_rejected(self):
        m = model(39)
        residual = m['graph']['edges'][1]['residual_node']
        m['accounting']['nodes'][residual]['terms'][0][1] = '1/2'
        self.reject(m, cert(39))

    def test_negative_residual_rejected(self):
        m = model(39)
        residual = m['graph']['edges'][1]['residual_node']
        m['accounting']['nodes'][residual]['constant'] = '-1'
        self.reject(m, cert(39))

    def test_bad_list_must_be_sorted_unique(self):
        m = model(67); m['graph']['bad_vertices'] = [4, 3]
        self.reject(m, cert(67))

    def test_extra_model_field_rejected(self):
        m = model(21); m['claim'] = 'safe'
        self.reject(m, cert(21))

    def test_maximum_state_signature_case(self):
        retained = json.loads((ROOT / 'tpeg_results' / 'tpeg-044.json').read_text())
        self.assertEqual(retained['enumerated_states'], 4096)
        self.assertEqual(retained['feasible_states'], 4096)
        self.assertEqual(retained['maximal_signatures'], 64)
        self.assertEqual(tpeg_checker.verify(model(44), cert(44)), 'PROVED')


if __name__ == '__main__':
    unittest.main(verbosity=2)
