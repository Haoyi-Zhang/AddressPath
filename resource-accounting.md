# Resource accounting

## Declared ceilings

The project contract permits at most four CPU cores, 4 GiB RAM, no swap, 45 minutes per individual run, 8 aggregate CPU-hours for the complete campaign, and no GPU, external compute, model API, private data, or real device. The implementation voluntarily uses one pinned worker and a 2 GiB address-space limit for scientific subprocesses.

The arithmetic and TPEG schemas cap each finite input box at 4,096 states. TPEGs admit at most 64 vertices, 64 edges, and 4,096 signature entries. Arithmetic inputs admit at most 16 coordinates, 64 nodes, 16 observations, and 128 compiled inequalities. These are admission limits, not demonstrated scalability points.

## Retained campaign measurements

The retained TPEG campaign is split into bounded sequential groups. Summing the per-group records gives:

- 72 models;
- 49,258 states per independent enumerator;
- 31,197 admitted states;
- 48.194666065 CPU seconds;
- 48.224942648 wall seconds;
- 93,356 KiB maximum recorded resident set;
- one worker.

The 74-method combined mutation run records 16.397232943 CPU seconds, 16.405750858 wall seconds, and 94,508 KiB peak RSS. The graph characterization meta-check records 1.398687751 CPU seconds, 1.400077886 wall seconds, and 95,276 KiB peak RSS.

The retained 86-case arithmetic-regression campaign takes less than one CPU second in its six groups. It is included for proof-kernel regression and is not added to the TPEG case count. The independent arithmetic meta-check covers 3,915 systems and 11,160 finite states; its retained run records 1.115538905 CPU seconds, 1.115601412 wall seconds, and 93,228 KiB peak RSS.

## Clean staged reproduction

A fresh reproduction was run in four separate invocations against one empty output directory:

```bash
python3 reproduce.py --output reproduction-audit --stage core
python3 reproduce.py --output reproduction-audit --stage tpeg-middle
python3 reproduce.py --output reproduction-audit --stage tpeg-tail
python3 reproduce.py --output reproduction-audit --stage validation
```

The final report records:

- status: `PASS`;
- one pinned worker;
- 87.456036784 cumulative CPU seconds;
- 87.496167824 cumulative stage wall seconds;
- 95,400 KiB maximum recorded peak RSS.

Per-stage records are:

| Stage | CPU seconds | Wall seconds | Peak RSS KiB |
|---|---:|---:|---:|
| `core` | 9.640037533 | 9.654066546 | 94,000 |
| `tpeg-middle` | 25.750067958 | 25.756313827 | 93,612 |
| `tpeg-tail` | 25.755829741 | 25.765345615 | 93,864 |
| `validation` | 26.310101552 | 26.320441836 | 95,400 |

This scope includes fresh model generation, 86 arithmetic decisions, 72 TPEG decisions, exact certificate-object comparison, independent finite-oracle checks, 74 mutation-test methods, the 3,915-model arithmetic meta-check, the 2,865-antichain graph meta-check, table generation, and standalone checker invocations. Paper compilation and PDF rendering are separate.

Timing and RSS fields are deliberately excluded from semantic equality comparisons. Exact input JSON, decision fields, counts, certificate objects, mutation outcomes, characterization results, and structural tables must match.

## Interpretation

These values are kernel-reported measurements for named commands, not a complete historical account of every interactive development action, browser transfer, TeX invocation, or scalar operation. Summing retained campaign measurements and clean reproduction would double-count scientific work rerun by reproduction, so no aggregate is presented as a unique all-session total.

No run approached the declared CPU, memory, wall-time, download, expanded-input, or archive ceiling. The largest retained exact signature cover has 64 entries and 13,277 bytes. The exponential family shows why this bounded fallback is not presented as a scalable replacement for symbolic verification.
