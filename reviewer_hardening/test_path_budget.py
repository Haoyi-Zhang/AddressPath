#!/usr/bin/env python3
"""Regression tests for the two independently implemented path-budget checkers."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import path_budget as pb
import independent_path_budget as ipb


def single_edge_model(*, name: str = "single", bounds=None, constraints=None, open_expr=None):
    bounds = bounds or {"x": [0, 1]}
    constraints = constraints if constraints is not None else []
    open_expr = open_expr or {"coeffs": {"x": 1}, "const": 0}
    return {
        "name": name,
        "variables": ["x"],
        "bounds": bounds,
        "nodes": ["s", "b"],
        "source": "s",
        "bad": "b",
        "constraints": constraints,
        "edges": [{"name": "e", "src": "s", "dst": "b", "open": open_expr}],
    }


def cert(model, multipliers=None, witness=None):
    return {
        "type": "path_budget",
        "model": model["name"],
        "witness": witness if witness is not None else {"x": 0},
        "obligations": [{"path": ["e"], "multipliers": multipliers or {}}],
    }


class PathBudgetRegressionTests(unittest.TestCase):
    def assertBothReject(self, model, certificate):
        parsed = pb.parse_model(model)
        with self.assertRaises(Exception):
            pb.check_certificate(parsed, certificate)
        with self.assertRaises(Exception):
            ipb.check(model, certificate)

    def test_alternating_n2_full_box_budget_and_signature_count(self):
        model, certificate = pb.make_alternating_model(2)
        parsed = pb.parse_model(model)
        self.assertEqual(pb.oracle(parsed, state_cap=16)["allowed_states"], 9)
        self.assertEqual(len(pb.max_signatures(parsed, state_cap=16)), 4)
        with self.assertRaises(pb.ModelError):
            list(pb.allowed_states(parsed, cap=10))
        pb.check_certificate(parsed, certificate)
        ipb.check(model, certificate)

    def test_integer_empty_model_is_inconsistent_and_not_proved(self):
        model = single_edge_model(
            name="integer_empty",
            constraints=[{"name": "impossible", "coeffs": {"x": 1}, "rhs": -1}],
        )
        certificate = cert(model, {"impossible": 1}, {"x": 0})
        self.assertEqual(pb.oracle(pb.parse_model(model))["decision"], "INCONSISTENT")
        self.assertEqual(ipb.oracle(model)["decision"], "INCONSISTENT")
        self.assertBothReject(model, certificate)

    def test_dummy_fixed_zero_indicator_rejected(self):
        model = single_edge_model(name="fixed_zero", bounds={"x": [0, 0]})
        self.assertBothReject(model, cert(model))

    def test_constant_zero_indicator_rejected(self):
        model = single_edge_model(name="constant_zero", open_expr={"coeffs": {}, "const": 0})
        self.assertBothReject(model, cert(model))

    def test_two_half_indicators_rejected(self):
        model = {
            "name": "two_halves",
            "variables": ["x"],
            "bounds": {"x": [0, 1]},
            "nodes": ["s", "m", "b"],
            "source": "s",
            "bad": "b",
            "constraints": [],
            "edges": [
                {"name": "a", "src": "s", "dst": "m", "open": {"coeffs": {}, "const": {"num": 1, "den": 2}}},
                {"name": "b", "src": "m", "dst": "b", "open": {"coeffs": {}, "const": {"num": 1, "den": 2}}},
            ],
        }
        certificate = {"type": "path_budget", "model": model["name"], "witness": {"x": 0},
                       "obligations": [{"path": ["a", "b"], "multipliers": {}}]}
        self.assertBothReject(model, certificate)

    def test_bool_rational_component_rejected(self):
        model, certificate = pb.make_alternating_model(1, "bool_num")
        certificate["obligations"][0]["multipliers"]["pair_0"] = {"num": True, "den": 1}
        self.assertBothReject(model, certificate)

    def test_float_rational_component_rejected(self):
        model, certificate = pb.make_alternating_model(1, "float_num")
        certificate["obligations"][0]["multipliers"]["pair_0"] = {"num": 1.0, "den": 1}
        self.assertBothReject(model, certificate)

    def test_unsafe_certificate_rejected_by_both(self):
        model, certificate = pb.make_alternating_model(2, "unsafe")
        model["constraints"] = [{"name": "loose", "coeffs": {v: 1 for v in model["variables"]}, "rhs": 4}]
        certificate["obligations"][0]["multipliers"] = {"loose": 1}
        self.assertEqual(pb.oracle(pb.parse_model(model), state_cap=16)["decision"], "INSUFFICIENT")
        self.assertEqual(ipb.oracle(model, state_limit=16)["decision"], "INSUFFICIENT")
        self.assertBothReject(model, certificate)

    def test_missing_witness_rejected(self):
        model, certificate = pb.make_alternating_model(1, "no_witness")
        certificate.pop("witness")
        self.assertBothReject(model, certificate)

    def test_witness_constraint_violation_rejected(self):
        model, certificate = pb.make_alternating_model(1, "bad_witness")
        certificate["witness"] = {"x0": 1, "y0": 1}
        self.assertBothReject(model, certificate)


if __name__ == "__main__":
    unittest.main(verbosity=2)
