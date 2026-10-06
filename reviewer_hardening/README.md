# Binary-affine path-budget backend

This directory adds a compact, exact-arithmetic path-budget certificate and a
second implementation that does not import the production checker.

This is a separate named-variable, single-bad-vertex interface. Every edge
indicator must be exactly `x` or `1-x` on a Boolean-bounded coordinate. No general
TPEG residual-threshold adapter is supplied; the main TPEG dispatcher accepts
only its documented uniform-cut, signature-cover and inconsistency envelopes.

Run:

```bash
python3 run_suite.py --output results
```

The suite contains deterministic development and post-construction holdout
families, implementation-diversity checks, renaming and positive-scaling
metamorphic tests, exact small-state oracles, an exponential representation
separation, a 4,096-pair non-enumerative scaling check, an integer-only
incompleteness witness, mutation rejection, and a fail-closed path cap.

Both path enumerators first discard vertices that cannot reach the bad vertex.
This preserves all bad paths while avoiding expansion of exponentially many
irrelevant dead-end prefixes. The complete-bad-path cap is unchanged. Focused
traversal regressions are in `../tests/test_path_enumeration.py`.

The holdout split is a robustness check, not a preregistered experiment.  No
model parameters are trained; the relevant risk is benchmark-specific logic,
not statistical overfitting in the machine-learning sense.

The retained suite runs both finite oracles on all 700 models and both
certificate checkers on the 391 safe cases. Its 309 `unsafe_rejected` cases
record the first checker's rejection, not both checkers' systematic negative
coverage. Separate regression tests exercise a representative negative with
both checkers.
