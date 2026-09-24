# Reviewer-hardening checks

This directory adds a compact, exact-arithmetic path-budget certificate and a
second implementation that does not import the production checker.  Run:

```bash
python3 run_suite.py --output results
```

The suite contains deterministic development and post-construction holdout
families, implementation-diversity checks, renaming and positive-scaling
metamorphic tests, exact small-state oracles, an exponential representation
separation, a 4,096-pair non-enumerative scaling check, an integer-only
incompleteness witness, mutation rejection, and a fail-closed path cap.

The holdout split is a robustness check, not a preregistered experiment.  No
model parameters are trained; the relevant risk is benchmark-specific logic,
not statistical overfitting in the machine-learning sense.
