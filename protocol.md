# Frozen experimental protocol

## Question and outcome rule

For each owned synthetic TPEG, determine whether interval-valued accounting evidence proves that every admitted state excludes every declared source-to-bad translation path. The three outcomes are fixed before aggregation:

- `PROVED`: at least one state is admitted and every admitted state is path-safe;
- `INSUFFICIENT`: at least one admitted state is unsafe;
- `INCONSISTENT`: no state is admitted.

Inconsistency is not counted as a proof. `INSUFFICIENT` is not a vulnerability finding and retains no unsafe state or path.

## Frozen methods

1. **Sink-adjacent-zero baseline.** Proves only when every edge entering a bad vertex is universally closed.
2. **Uniform-zero cut.** Deletes every edge closed in all admitted states and tests whether bad vertices remain reachable. A positive result is emitted only with local arithmetic zero proofs for every outgoing cut edge.
3. **Uniform cut plus exact maximal-signature cover.** Uses the uniform cut when available; otherwise, for a safe finite model, emits exactly the maximal admitted open-edge signatures and their canonical reachable sets.
4. **Independent direct oracle.** Evaluates the original affine node list and graph independently of the producer/checker.

The complete method is not compared against a stochastic estimator or a hardware measurement because the claim is exact bounded correctness, not population performance.

## Corpus

The 72 TPEG cases are deterministic and all are included. There is no train/test split and no tuning against held-out outcomes.

| Family | Cases | Purpose |
|---|---:|---|
| `accounting-window` | 20 | Exact integer boundary around a terminal foreign-use count; includes safe and unsafe widths. |
| `source-cut` | 6 | Upstream source separation that the sink-zero baseline misses. |
| `interior-cut` | 6 | A fixed interior barrier with live edges on both sides. |
| `merge-boundary-cut` | 6 | Multiple upstream paths blocked after a merge. |
| `multi-bad-cut` | 6 | One cut separates several declared bad vertices. |
| `alternating-cut-cover` | 6 | Safe state-dependent exclusion with no universally closed edge; 2--64 maximal signatures. |
| `hidden-bypass` | 8 | Unsafe direct or alternate path; must force abstention. |
| `wide-path` | 6 | Weak intervals admit a complete path; must force abstention. |
| `inconsistent-evidence` | 8 | Empty evidence constraints; must be diagnosed separately. |

The generator is deterministic and uses no random seed. Maximum retained dimensions are 12 input coordinates, 18 accounting nodes, two observations, 24 compiled inequalities, eight graph vertices, 12 edges, and 4,096 enumerated states. These maxima are not all attained by one model.

The 86 arithmetic cases predate the graph layer and are retained unchanged as regression tests for local edge-zero proofs. They do not expand the TPEG corpus or its practical scope.

## Hypotheses and falsifiers

The protocol tests the following claims:

- every accepted uniform cut blocks every source-to-bad path;
- a uniform cut exists exactly when deletion of universally closed edges separates source and bad;
- exact maximal signatures suffice for all bounded safe models;
- the exact signature representation can grow exponentially;
- inconsistent inputs and insufficient evidence remain distinct;
- the producer, strict checker, and independent oracle agree on all fixed cases.

A claim fails if any of the following occurs:

- the checker accepts a cut that omits an outgoing edge or contains a bad vertex;
- any embedded arithmetic proof targets the wrong residual or fails exact identity/nonnegativity checks;
- a signature cover omits or adds a maximal admitted signature;
- canonical reachability differs from the certificate or reaches a bad vertex;
- a hidden bypass is proved safe;
- an inconsistent model is reported `PROVED`;
- the producer and direct oracle disagree on decision or aggregate state counts;
- either exhaustive small-model characterization disagrees with direct finite semantics;
- clean regeneration changes any non-timing result, certificate object, or structural table.

All cases and all test outcomes are retained; there is no exclusion after observing results.

## Mutation suite

The 74 test methods cover both acceptance and rejection paths. TPEG-specific mutations include malformed topological order, duplicate identifiers, negative or nonintegral residuals, structurally vacuous graphs, non-admitted witnesses, cuts containing bad vertices, omitted or extra cut edges, substituted residual proofs, forged local multipliers, omitted or duplicate signatures, unrealized signatures, forged reachable sets, reachable bad vertices, hidden bypasses, cyclic graphs, and oversized models. Arithmetic mutations include incorrect dual identities, negative multipliers, missing witnesses, non-strict quantization, malformed finite-cover tags, and false contradiction certificates.

The resulting 289 checker calls are predetermined logical diagnostics, not a random mutation score or a claim of complete code coverage.

## Independent meta-checks

The graph meta-check enumerates 40 relevant four-vertex DAGs with at most four edges and 2,865 candidate maximal-signature antichains. It directly classifies each family and compares:

1. exact safety with safety of all maximal signatures; and
2. existence of a uniform-zero cut with source-to-bad separation after deleting edges absent from every signature.

The arithmetic meta-check independently generates 3,915 small exact systems: 3,375 one-input systems and 540 two-input systems. Across 11,160 finite states it obtains 1,222 `PROVED`, 941 `INSUFFICIENT`, and 1,752 `INCONSISTENT` decisions. It exercises all four favorable/diagnostic certificate kinds (`linear`, `quantized`, `finite_cover`, and `inconsistent`) and compares direct finite semantics, the untrusted producer, and the strict checker. The check fails on any status mismatch, rejected favorable certificate, certificate attached to an insufficient result, or missing decision/certificate category.

Both test spaces are exhaustive only for their declared tiny generators. They are independent implementation cross-checks, not substitutes for the written general proofs.

## Resource and safety boundary

Every scientific run uses one worker even though the project ceiling permits four. Case subprocesses apply a 2 GiB address-space limit and CPU/wall limits below the project ceilings. The full clean reproduction uses no network, external solver, GPU, model API, private data, real device, active probing, execution synthesis, exploit generation, or human participant.

The campaign reports exact finite-state counts and measured CPU/RSS for the specified commands. It does not extrapolate a performance curve to the full schema, claim all-session resource metering, or treat a finite count as hardware workload breadth.
