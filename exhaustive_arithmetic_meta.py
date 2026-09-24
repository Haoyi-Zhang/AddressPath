#!/usr/bin/env python3
"""Exhaustively cross-check the arithmetic certificate layer on tiny models.

The enumerator builds a fixed, deterministic universe of one- and two-input
integer-grid affine DAGs.  A deliberately simple evaluator computes the exact
finite-state status without using checker.compile_model(), producer.translate(),
or the certificate proof rules.  The producer's classification and every
favorable certificate are then checked against that direct result.

This is finite implementation evidence, not a proof of the general theorems.
"""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path
import resource
import sys
import time
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
import checker  # type: ignore  # local standalone module
import producer  # type: ignore  # local standalone module


def q(value: Any) -> F:
    """Parse only the tiny integer/rational literals generated below."""
    return F(value)


def direct_status(model: dict[str, Any]) -> tuple[str, int, int]:
    """Evaluate the declared model directly over its finite integer box."""
    bounds = model["domain"]["bounds"]
    admitted = 0
    violating = 0
    for state in product(*(range(lo, hi + 1) for lo, hi in bounds)):
        values: list[F] = []
        for node in model["nodes"]:
            if "input" in node:
                values.append(F(state[node["input"]]))
            else:
                value = q(node["constant"])
                for parent, coefficient in node["terms"]:
                    value += q(coefficient) * values[parent]
                values.append(value)
        constraints = [*model["assumptions"], *model["observations"]]
        if not all(q(item["lower"]) <= values[item["node"]] <= q(item["upper"])
                   for item in constraints):
            continue
        admitted += 1
        assertion = model["assertion"]
        if values[assertion["node"]] > q(assertion["upper"]):
            violating += 1
    if admitted == 0:
        return "INCONSISTENT", admitted, violating
    if violating:
        return "INSUFFICIENT", admitted, violating
    return "PROVED", admitted, violating


def make_model(identifier: str, bounds: list[list[int]], coefficients: tuple[int, ...],
               offset: int, interval: tuple[int, int] | None,
               upper: int) -> dict[str, Any]:
    dimensions = len(bounds)
    nodes: list[dict[str, Any]] = [{"input": i} for i in range(dimensions)]
    nodes.append({
        "constant": str(offset),
        "terms": [[i, str(coefficient)] for i, coefficient in enumerate(coefficients)],
    })
    observations = [] if interval is None else [{
        "node": dimensions,
        "lower": str(interval[0]),
        "upper": str(interval[1]),
    }]
    return {
        "id": identifier,
        "family": "tiny-arithmetic-meta",
        "domain": {"kind": "integer_grid", "bounds": bounds},
        "nodes": nodes,
        "observations": observations,
        "assumptions": [],
        "assertion": {"node": dimensions, "upper": str(upper)},
    }


def universe() -> Iterable[dict[str, Any]]:
    intervals_1d: tuple[tuple[int, int] | None, ...] = (
        None, (-2, -1), (-1, 0), (0, 0), (0, 1), (1, 2), (-1, 1), (1, 0), (2, -1)
    )
    index = 0
    for bounds in ([[-1, 1]], [[0, 1]], [[0, 2]]):
        for coefficient in range(-2, 3):
            for offset in range(-2, 3):
                for interval in intervals_1d:
                    for upper in range(-2, 3):
                        index += 1
                        yield make_model(
                            f"arith-meta-{index:04}", bounds, (coefficient,),
                            offset, interval, upper,
                        )

    intervals_2d: tuple[tuple[int, int] | None, ...] = (
        None, (-1, 0), (0, 0), (0, 1), (1, 0)
    )
    for a in range(-1, 2):
        for b in range(-1, 2):
            for offset in range(-1, 2):
                for interval in intervals_2d:
                    for upper in range(-1, 3):
                        index += 1
                        yield make_model(
                            f"arith-meta-{index:04}", [[0, 1], [0, 1]],
                            (a, b), offset, interval, upper,
                        )


def main(output: Path) -> None:
    wall0 = time.perf_counter()
    cpu0 = time.process_time()
    statuses: Counter[str] = Counter()
    certificates: Counter[str] = Counter()
    proof_layers: Counter[str] = Counter()
    admitted_states = violating_states = finite_states = 0
    maximum_basis_systems = 0
    models = 0

    for model in universe():
        models += 1
        expected, admitted, violating = direct_status(model)
        result = producer.make(model, cap=5000)
        if result["exact_status"] != expected:
            raise AssertionError(
                f"status disagreement for {model['id']}: "
                f"direct={expected}, producer={result['exact_status']}"
            )
        expected_states = 1
        for lo, hi in model["domain"]["bounds"]:
            expected_states *= hi - lo + 1
        finite_states += expected_states
        admitted_states += admitted
        violating_states += violating
        statuses[expected] += 1
        maximum_basis_systems = max(maximum_basis_systems, result["basis_systems"])

        cert = result["certificate"]
        if expected == "INSUFFICIENT":
            if cert is not None:
                raise AssertionError(f"insufficient model carries a certificate: {model['id']}")
            proof_layers["no_certificate"] += 1
            continue
        if cert is None:
            raise AssertionError(f"favorable model lacks a certificate: {model['id']}")
        checked = checker.verify(model, cert)
        if checked != expected:
            raise AssertionError(
                f"checker disagreement for {model['id']}: expected={expected}, checked={checked}"
            )
        certificates[cert["kind"]] += 1
        if result["linear_status"] == expected:
            proof_layers["linear_or_inconsistency"] += 1
        elif result["quantized_status"] == expected:
            proof_layers["quantized"] += 1
        else:
            proof_layers["finite_cover"] += 1

    expected_models = 3915
    if models != expected_models:
        raise AssertionError(f"universe changed: expected {expected_models}, got {models}")
    if not {"PROVED", "INSUFFICIENT", "INCONSISTENT"} <= set(statuses):
        raise AssertionError("tiny universe does not exercise all three decisions")
    if not {"linear", "quantized", "inconsistent", "finite_cover"} <= set(certificates):
        raise AssertionError("tiny universe does not exercise every certificate kind")

    result = {
        "models": models,
        "one_input_models": 3375,
        "two_input_models": 540,
        "finite_states_evaluated": finite_states,
        "admitted_states": admitted_states,
        "violating_states": violating_states,
        "status_counts": dict(sorted(statuses.items())),
        "certificate_kind_counts": dict(sorted(certificates.items())),
        "proof_layer_counts": dict(sorted(proof_layers.items())),
        "maximum_basis_systems": maximum_basis_systems,
        "checks": {
            "direct_status_vs_producer": "PASS",
            "favorable_certificate_vs_checker": "PASS",
            "insufficient_has_no_certificate": "PASS",
            "all_decisions_and_certificate_kinds_exercised": "PASS",
        },
        "cpu_s": time.process_time() - cpu0,
        "wall_s": time.perf_counter() - wall0,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path,
        default=Path("validation/arithmetic-meta-check.json"),
    )
    arguments = parser.parse_args()
    main(arguments.output)
