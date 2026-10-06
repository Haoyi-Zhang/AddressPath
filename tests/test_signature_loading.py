"""Distinguish finite certificate-language completeness from byte admission."""
from pathlib import Path
from itertools import combinations
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import checker
import tpeg_checker
import tpeg_oracle


def large_cover_model():
    nodes = [{'input': i} for i in range(12)]
    nodes += [{'constant': 1, 'terms': [[i, -1]]} for i in range(12)]
    nodes.append({'constant': 1, 'terms': []})
    def name(i):
        return f'e{i:02}' + 'a'*45
    edges = []
    for i in range(12):
        edges += [{'id': name(2*i), 'tail': 0, 'head': i+1, 'residual_node': i},
                  {'id': name(2*i+1), 'tail': i+1, 'head': 13, 'residual_node': 12+i}]
    dead_edges = list(combinations(range(14,24), 2))[:40]
    edges += [{'id': name(i), 'tail': tail, 'head': head, 'residual_node': 24}
              for i,(tail,head) in enumerate(dead_edges,24)]
    return {'id': 'cover-size-boundary', 'family': 'certificate-format-boundary',
            'accounting': {'domain': {'kind': 'integer_grid', 'bounds': [[0,1]]*12},
                           'nodes': nodes, 'observations': [], 'assumptions': []},
            'graph': {'vertices': ['s']+[f'arm{i}' for i in range(12)]+['bad']+[f'dead{i}' for i in range(10)],
                      'source': 0, 'bad_vertices': [13], 'edges': edges}}


class SignatureLoadingTests(unittest.TestCase):
    def test_safe_legal_model_has_cover_identifier_lower_bound_above_file_cap(self):
        model = large_cover_model()
        compiled = tpeg_checker.compile_model(model)
        self.assertEqual(len(compiled['edges']), 64)
        result = tpeg_oracle.evaluate(model)
        self.assertEqual(result, {'status': 'PROVED', 'states': 4096, 'feasible_states': 4096,
                                  'unsafe_states': 0, 'distinct_signatures': 4096})
        # All distinct signatures choose 12 pair edges plus 40 common edges;
        # equal cardinality makes every signature inclusion-maximal.
        lower_bound = result['distinct_signatures'] * (12+40) * (48+2)
        self.assertEqual(lower_bound, 10649600)
        self.assertGreater(lower_bound, checker.MAX_FILE_BYTES)

    def test_byte_limit_remains_fail_closed_before_json_parsing(self):
        with patch.object(Path, 'stat', return_value=SimpleNamespace(st_size=10649600)), \
             patch.object(Path, 'read_text') as reader:
            with self.assertRaisesRegex(checker.Invalid, 'input exceeds byte budget'):
                checker.load('owned-cover.json')
            reader.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
