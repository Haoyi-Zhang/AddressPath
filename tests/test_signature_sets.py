"""Portable finite regressions; no timings or historical implementation copy."""
from contextlib import ExitStack
import copy
from fractions import Fraction
from itertools import product
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import checker
import tpeg_checker as tc
import tpeg_producer as tp
import tpeg_oracle as oracle


def literal_maxima(family):
    # Membership/cardinality reference, not the implementation's set comparator.
    return sorted(s for s in family if not any(
        len(t) > len(s) and all(edge in t for edge in s) for t in family))


def literal_reach(graph, opened):
    reached = [graph['source']]
    for vertex in range(len(graph['vertices'])):
        if vertex in reached:
            for edge in graph['edges']:
                if edge['tail'] == vertex and edge['id'] in opened and edge['head'] not in reached:
                    reached.append(edge['head'])
    return sorted(reached)


def fixture(d=3):
    # A closed pair on a chain, followed by optional edges: includes dominated
    # signatures, equal-size incomparable maxima and a non-lexicographic witness.
    return {'id': 'literal-chain', 'family': 'owned-finite-regression',
            'accounting': {'domain': {'kind': 'integer_grid', 'bounds': [[0, 1]] * d},
                           'nodes': [{'input': i} for i in range(d)] +
                                    [{'constant': 1, 'terms': [[0, -1]]}],
                           'observations': [], 'assumptions': []},
            'graph': {'vertices': ['s', 'a', 'c', 'd', 'bad'], 'source': 0,
                      'bad_vertices': [4], 'edges': [
                          {'id': name, 'tail': i, 'head': i + 1, 'residual_node': node}
                          for i, (name, node) in enumerate([('a', 0), ('b', d), ('c', 1), ('d', 2)])]}}


def literal(model):
    accounting, graph = model['accounting'], model['graph']
    admitted, family, unsafe = [], [], 0
    for state in product(*(range(lo, hi + 1) for lo, hi in accounting['domain']['bounds'])):
        values = []
        for node in accounting['nodes']:
            values.append(Fraction(state[node['input']]) if 'input' in node else
                          Fraction(node['constant']) + sum(
                              Fraction(weight) * values[parent] for parent, weight in node['terms']))
        if any(not Fraction(interval['lower']) <= values[interval['node']] <= Fraction(interval['upper'])
               for interval in accounting['assumptions'] + accounting['observations']):
            continue
        admitted.append(list(state))
        sig = tuple(e['id'] for e in graph['edges'] if values[e['residual_node']] >= 1)
        if sig not in family:
            family.append(sig)
        unsafe += any(v in literal_reach(graph, sig) for v in graph['bad_vertices'])
    return admitted, family, unsafe


def outcome(model, cert):
    try:
        return {'verdict': tc.verify(model, cert)}
    except checker.Invalid as error:
        return {'error_type': type(error).__name__, 'error': str(error)}


def real_records():
    models = []
    for lower, upper in ((0, 1), (0, 0), (1, 1), (1, 0)):
        model = fixture()
        model['accounting']['observations'] = [{'node': 1, 'lower': lower, 'upper': upper}]
        models.append(model)
    unsafe = fixture()
    unsafe['graph']['edges'][1]['residual_node'] = 0
    models.append(unsafe)
    models.append(fixture(12))  # exactly 4,096 states, with unchanged witness order
    records = []
    for model in models:
        admitted, family, bad = literal(model)
        result = tp.make(model)
        expected = 'INCONSISTENT' if not admitted else 'INSUFFICIENT' if bad else 'PROVED'
        assert result['exact_status'] == expected
        assert result['feasible_states'] == len(admitted)
        assert result['unsafe_states'] == bad
        assert result['distinct_signatures'] == len(family)
        assert result['max_open_edges'] == max(map(len, family), default=0)
        assert result['uniform_zero_edges'] == sum(
            not any(e['id'] in sig for sig in family) for e in model['graph']['edges'])
        if result['certificate'] is not None:
            assert tc.verify(model, result['certificate']) == expected
            if result['certificate']['kind'] == 'signature_cover':
                entries = [{'open_edges': list(sig), 'reachable': literal_reach(model['graph'], sig)}
                           for sig in literal_maxima(family)]
                assert result['certificate'] == {'kind': 'signature_cover', 'witness': admitted[0],
                                                  'signatures': entries}
        assert oracle.evaluate(model)['status'] == expected
        records.append({'producer': result, 'oracle': oracle.evaluate(model),
                        'checked': None if result['certificate'] is None else outcome(model, result['certificate']),
                        'serialized': json.dumps(result['certificate'], indent=2) + '\n'})
    return records


def tiny_families():
    # Isolate maximality from affine parsing: all 255 nonempty families over
    # three edge labels are injected only at the admission/signature boundary.
    # The real affine fixtures above exercise the complete public paths.
    graph = {'vertices': ['s', 'a', 'c', 'bad'], 'source': 0, 'bad_vertices': [3],
             'edges': [{'id': name, 'tail': i, 'head': i + 1} for i, name in enumerate('abc')]}
    signatures = [tuple(name for i, name in enumerate('abc') if mask & (1 << i)) for mask in range(8)]
    records = []
    for mask in range(1, 256):
        family = [sig for i, sig in enumerate(signatures) if mask & (1 << i)]
        compiled = {'bounds': [(0, len(family) - 1)], 'A': [], 'b': [], 'edge_ids': set('abc'),
                    'vertices': graph['vertices'], 'source': 0, 'bad': [3], 'edges': graph['edges']}
        cert = {'kind': 'signature_cover', 'witness': [0], 'signatures': [
            {'open_edges': list(sig), 'reachable': literal_reach(graph, sig)} for sig in literal_maxima(family)]}
        with ExitStack() as stack:
            stack.enter_context(patch.object(tc, 'compile_model', return_value=compiled))
            stack.enter_context(patch.object(tc, '_signature', side_effect=lambda _c, state: family[state[0]]))
            checked = outcome({}, cert)
            bad = ('a', 'b', 'c') in family
            assert ('error' in checked) == bad
            union = {edge for sig in family for edge in sig}
            # Only the signature and unsafe producer branches are isolated here;
            # uniform-cut arithmetic remains tested by real models, not mocked.
            produced = tp.make({}) if bad or union == set('abc') else None
            if produced is not None:
                assert produced['feasible_states'] == len(family)
                assert produced['unsafe_states'] == int(bad)
                if not bad:
                    assert produced['certificate'] == cert
            records.append({'family': [list(s) for s in family], 'checker': checked, 'producer': produced})
    return records


def negative_records():
    model = fixture()
    cert = tp.make(model)['certificate']
    mutations = []
    missing = copy.deepcopy(cert); missing['signatures'].pop(); mutations.append(missing)
    duplicate = copy.deepcopy(cert); duplicate['signatures'].append(duplicate['signatures'][-1]); mutations.append(duplicate)
    unsorted = copy.deepcopy(cert); unsorted['signatures'].reverse(); mutations.append(unsorted)
    dominated = copy.deepcopy(cert)
    dominated['signatures'].insert(0, {'open_edges': ['a'], 'reachable': [0, 1]}); mutations.append(dominated)
    wrong = copy.deepcopy(cert); wrong['signatures'][0]['reachable'] = [0]; mutations.append(wrong)
    unsafe = copy.deepcopy(cert); unsafe['signatures'][0] = {'open_edges': list('abcd'), 'reachable': list(range(5))}; mutations.append(unsafe)
    witness = copy.deepcopy(cert); witness['witness'][0] = True; mutations.append(witness)
    over = copy.deepcopy(cert); over['signatures'] = [cert['signatures'][0]] * 4097; mutations.append(over)
    records = [outcome(model, value) for value in mutations]
    too_many = fixture(12); too_many['accounting']['domain']['bounds'][0] = [0, 2]
    records.append(outcome(too_many, cert))
    too_many = fixture(); too_many['graph']['vertices'] = ['s'] + [f'v{i}' for i in range(64)]
    records.append(outcome(too_many, cert))
    too_many = fixture(); too_many['graph']['edges'] *= 17
    records.append(outcome(too_many, cert))
    assert all('error' in record for record in records)
    return records


def retained_records():
    records = []
    for i in range(39, 45):
        name = f'tpeg-{i:03}.json'
        model = checker.load(ROOT / 'tpeg_cases' / name)
        cert = checker.load(ROOT / 'tpeg_results' / 'certificates' / name)
        # Measurement records (unlike proof inputs) contain archived floats.
        retained = json.loads((ROOT / 'tpeg_results' / name).read_text(encoding='utf-8'))
        result = tp.make(model)
        assert result['certificate'] == cert
        for key, value in result.items():
            if key != 'certificate':
                assert value == retained[key]
        assert tc.verify(model, cert) == result['exact_status']
        # Linux retained serializer bytes, not a Windows physical file-size claim.
        text = json.dumps(cert, indent=2) + '\n'
        assert len(text.encode('utf-8')) == retained['certificate_bytes']
        records.append({'producer': result, 'checker': outcome(model, cert), 'serialized': text})
    return records


def snapshot():
    return {'real': real_records(), 'tiny': tiny_families(), 'negative': negative_records(),
            'retained_signature_covers': retained_records()}


class SignatureSetTests(unittest.TestCase):
    def test_literal_affine_enumeration_and_boundary(self):
        self.assertEqual(len(real_records()), 6)

    def test_all_tiny_signature_families(self):
        self.assertEqual(len(tiny_families()), 255)

    def test_negative_and_cap_semantics(self):
        self.assertEqual(len(negative_records()), 11)

    def test_six_retained_signature_covers(self):
        self.assertEqual(len(retained_records()), 6)


if __name__ == '__main__':
    unittest.main(verbosity=2)
