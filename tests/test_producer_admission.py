"""Owned finite regressions for producer/checker arithmetic boundaries."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import checker
import producer
import tpeg_checker
import tpeg_producer


def scalar_model():
    k = str(2 ** 511)
    return {"id": "wide-compiled-zero", "family": "finite-admission-regression",
            "domain": {"kind": "integer_grid", "bounds": [[0, 1]]},
            "nodes": [{"input": 0}, {"constant": 0, "terms": [[0, k]]},
                      {"constant": 0, "terms": [[1, k]]}],
            "assumptions": [], "observations": [{"node": 0, "lower": 0, "upper": 0}],
            "assertion": {"node": 2, "upper": 0}}


class ProducerAdmissionTests(unittest.TestCase):
    def test_compiled_large_coefficient_uses_admissible_finite_cover(self):
        model = scalar_model()
        result = producer.make(model)
        self.assertEqual(result["certificate"]["kind"], "finite_cover")
        self.assertEqual(checker.verify(model, result["certificate"]), "PROVED")

    def test_structured_zero_edge_preserves_complete_fallback(self):
        scalar = scalar_model()
        model = {"id": "wide-cut", "family": "finite-admission-regression",
                 "accounting": {key: scalar[key] for key in
                                ("domain", "nodes", "assumptions", "observations")},
                 "graph": {"vertices": ["source", "bad"], "source": 0,
                           "bad_vertices": [1], "edges": [
                               {"id": "e", "tail": 0, "head": 1, "residual_node": 2}]}}
        result = tpeg_producer.make(model)
        self.assertEqual(result["certificate"]["kind"], "uniform_cut")
        self.assertEqual(result["certificate"]["edge_proofs"][0]["certificate"]["kind"],
                         "finite_cover")
        self.assertEqual(tpeg_checker.verify(model, result["certificate"]), "PROVED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
