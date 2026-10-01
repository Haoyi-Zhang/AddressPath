# Counter Evidence Isolation Artifact

This repository is the standalone artifact for **Path Certificates for Conditional Address-Translation Isolation from Noisy Counter Evidence**. It implements a bounded, defensive proof system for translation-path evidence graphs (TPEGs), exact synthetic cases, independently implemented finite oracles, strict certificate checkers, mutation tests, and two exhaustive small-model characterization checks.

The artifact answers a model-level question: given a finite integer accounting model, interval observations, and a declared acyclic translation-path graph, do **all** admitted states exclude every source-to-bad path? It does not infer a graph from counters, reconstruct hidden behavior, generate attacks, probe hardware, or certify a deployed processor.

## Retained results

The fixed TPEG corpus contains 72 models:

| Decision or method | Count |
|---|---:|
| `PROVED` | 42 |
| `INSUFFICIENT` | 22 |
| `INCONSISTENT` | 8 |
| Sink-adjacent-zero baseline proofs | 12 |
| Uniform-cut proofs | 36 |
| Additional maximal-signature-cover proofs | 6 |

The direct TPEG oracle enumerates 49,258 states in total, of which 31,197 are admitted and 62 are unsafe negative-control states. The largest case has 4,096 states and 12 graph edges. The largest exact signature cover contains 64 maximal signatures and occupies 13,277 bytes.

The complete mutation suite has 74 methods and makes 289 certificate-checker calls: 174 are accepted and 115 are rejected as intended. The graph meta-check exhaustively covers 40 small DAGs and 2,865 maximal-signature antichains; both the uniform-cut and maximal-signature characterizations pass.

An older 86-model arithmetic regression suite is retained because every uniform-cut edge proof uses that exact rational/integer kernel. It yields 41 proved, 37 insufficient, and 8 inconsistent decisions. A separate arithmetic meta-check exhaustively covers 3,915 generated one- and two-input systems and 11,160 finite states. It exercises every three-way decision and every certificate kind and finds complete agreement among the producer, direct finite semantics, and checker. Neither arithmetic suite is counted as additional architecture evidence.

## Reproduction

Requirements: Linux and Python 3.10 or newer. Only the Python standard library is used. The portable route is four resumable invocations against one fresh output directory:

```bash
python3 reproduce.py --output reproduction --stage core
python3 reproduce.py --output reproduction --stage tpeg-middle
python3 reproduce.py --output reproduction --stage tpeg-tail
python3 reproduce.py --output reproduction --stage validation
```

Each invocation prints start/end progress for every bounded substep and writes a `stage-*.json` marker. The later stages refuse to run unless all prerequisites passed. The `core` stage refuses to overwrite an existing output directory; remove or rename it before intentionally starting again.

On a workstation where one longer invocation is acceptable, the same sequence can be requested with:

```bash
python3 reproduce.py --output reproduction-all --stage all
```

The retained clean four-stage run reports `PASS` after regenerating all 158 fixed inputs, rerunning every decision, comparing every favorable/inconsistency certificate object, rerunning the independent finite oracles, the 74-method mutation suite, both exhaustive meta-checks, all aggregate tables, and three standalone checker entry points. Across the four invocations it used one pinned CPU, 87.456036784 cumulative CPU seconds, 87.496167824 cumulative stage wall seconds, and at most 95,400 KiB recorded peak RSS. Timing and memory may vary; exact non-timing decisions, certificates, counts, characterization results, and structural tables must not.

Check one uniform-cut certificate without invoking the producer:

```bash
python3 src/tpeg_checker.py \
  tpeg_cases/tpeg-021.json \
  tpeg_results/certificates/tpeg-021.json
```

Expected output: `PROVED`. The bounded signature-cover endpoint is:

```bash
python3 src/tpeg_checker.py \
  tpeg_cases/tpeg-044.json \
  tpeg_results/certificates/tpeg-044.json
```

Expected output: `PROVED`.

## Trust boundary

The producers are untrusted. `src/tpeg_producer.py` proposes a decision and certificate; `src/tpeg_checker.py` reparses the model, recompiles exact affine forms, checks strict schema and resource budgets, and verifies the certificate without importing the producer. `src/tpeg_oracle.py` independently evaluates the affine DAG and graph reachability by direct enumeration. The arithmetic layer follows the same producer/checker/oracle split.

A `uniform_cut` certificate provides:

1. an admitted-state witness proving non-vacuity;
2. a source-side vertex set that contains the source and excludes every bad vertex; and
3. exactly one separately checked arithmetic zero proof for every edge leaving the set.

A `signature_cover` certificate provides:

1. an admitted-state witness;
2. exactly the maximal open-edge signatures realized by admitted states; and
3. the canonical reachable set for each signature, with no bad vertex reachable.

The signature checker re-enumerates every admitted state and recomputes the exact maximal antichain. This makes the proof form sound and complete for the declared bounded model but intentionally exponential in the worst case. `INCONSISTENT` has a separate arithmetic contradiction certificate. `INSUFFICIENT` carries no proof certificate and exposes only aggregate counts.

## Repository map

- `src/tpeg_checker.py` - strict TPEG certificate checker.
- `src/tpeg_producer.py` - bounded untrusted TPEG certificate producer.
- `src/tpeg_oracle.py` - separately implemented direct finite TPEG oracle.
- `src/checker.py`, `src/producer.py`, `src/oracle.py` - exact local arithmetic proof kernel and regression oracle.
- `tpeg_cases/`, `tpeg_results/` - 72 fixed TPEG models, raw results, certificates, and resource records.
- `cases/`, `results/` - 86 local arithmetic regression models and evidence.
- `tests/`, `run_tests.py` - acceptance and rejection mutations for both proof layers.
- `exhaustive_meta.py` - independent tiny-graph/maximal-antichain characterization check.
- `exhaustive_arithmetic_meta.py` - exhaustive small arithmetic decision/certificate cross-check.
- `tables/` - generated CSV, TeX, and JSON summaries used by the paper.
- `validation/` - retained mutation results, both meta-check reports, and clean-reproduction summary.
- `proofs.md` - self-contained written proof companion.
- `FORMAT.md` - strict input and certificate formats.
- `protocol.md` - frozen corpus, baselines, decisions, and falsification rules.
- `claim_evidence_ledger.csv` - material claim-to-evidence mapping.
- `external_resources.csv` - scholarly, template, policy, and runtime source inventory.
- `resource-accounting.md` - measured scopes and limits.
- `reproduce.py` - staged, offline, bounded reproduction driver.

## Interpretation limits

`PROVED` means that the supplied finite TPEG is nonempty and every admitted abstract state is path-safe. A concrete ownership-isolation statement additionally requires two external premises: every in-scope concrete epoch maps to an admitted state, and every concrete ownership violation induces an open source-to-bad path. This repository does not discharge either processor-specific premise.

`INSUFFICIENT` means only that at least one admitted state opens a declared bad path. The path may be an abstraction artifact, so the result is not a vulnerability report. `INCONSISTENT` means the accounting assumptions admit no state and is never relabeled as safety.

The written general theorems are not machine checked. The checkers are ordinary Python, the fixed suite is not an independent blind review, and the synthetic corpus is not a representative hardware workload sample. Exact reproduction validates this packet's finite evidence, not its real-world abstraction.

## Provenance and license

Generative-AI assistance was used in research design, formalization, code, synthetic data, experiments, analysis, validation, writing, and self-audit. The artifact itself invokes no model API. Human authors must inspect and accept responsibility for all content before external use and comply with the live publisher and venue policies.

Newly authored code, documentation, and synthetic inputs are provided under the included MIT license to the extent applicable rights exist. External papers, publisher assets, and the Python runtime are not redistributed here; their locators and use are recorded in `external_resources.csv`.


## Final verification gates

The standard reproduction remains split into four bounded stages:

```bash
python3 reproduce.py --output reproduction --stage core
python3 reproduce.py --output reproduction --stage tpeg-middle
python3 reproduce.py --output reproduction --stage tpeg-tail
python3 reproduce.py --output reproduction --stage validation
```

The `validation` stage also runs `tools/verify_research_records.py` and `tools/final_code_audit.py`. These checks validate the 21-row claim/evidence ledger, the 36-row external-resource ledger and its exact packaged URL inventory, strict JSON/CSV parsing, absence of network-capable imports and dynamic execution, archive hygiene, and Python syntax. The URL inventory is an offline correspondence check; it does not claim that every endpoint was reachable during the final clean build, and it does not prove the correctness of third-party content.

An additional non-default determinism exercise reran all four stages under `PYTHONHASHSEED=12345`; all JSON/CSV/TeX outputs agreed after removing runtime-only timing and memory fields. Its machine-readable record is `audit/hash-seed-determinism.json`.

The artifact proves only the finite-model statements encoded by its inputs and checkers. It does not establish path coverage, event binding, epoch fidelity, or isolation for a deployed processor. `INSUFFICIENT` is an evidentiary result, not a vulnerability report.

## Reviewer-hardening gate

Run `python3 run_all_checks.py --output full-reproduction` for the original staged reproduction plus the independent architecture cases, compact-certificate mutation tests, provenance audit, SMT-LIB export, compactness benchmark, claim/evidence matrix, and venue-readiness checks. The architecture cases use architecture-shaped synthetic graph patterns and synthetic evidence; they are not silicon validation.

## One-command clean reproduction

```bash
python3 final_reproduce.py --output reproduction-final
```

The driver removes a stale output directory by default, invokes every legacy
reproduction stage, and then runs the independent reviewer-hardening suite.
Use `--keep` to fail rather than remove an existing output directory.
