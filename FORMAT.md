# TPEG model and certificate format

The checker accepts strict UTF-8 JSON. Duplicate keys, floating-point literals, non-finite values, missing fields, and unexpected fields are rejected. Integers are JSON integers. Rational values are either JSON integers or strings of the form `numerator/positive-denominator`; decimal strings are not accepted.

## Model envelope

A TPEG model has exactly four top-level fields:

```json
{
  "id": "tpeg-001",
  "family": "accounting-window",
  "accounting": { ... },
  "graph": { ... }
}
```

`id` and `family` are nonempty strings of at most 64 characters.

## Accounting model

```json
{
  "domain": {
    "kind": "integer_grid",
    "bounds": [[0, 1], [0, 3]]
  },
  "nodes": [
    {"input": 0},
    {"input": 1},
    {"constant": 0, "terms": [[0, 1], [1, -1]]}
  ],
  "observations": [
    {"node": 2, "lower": 0, "upper": 1}
  ],
  "assumptions": []
}
```

The input dimension is 1--16. Bounds are inclusive integers in `[-4096,4096]`; the Cartesian product may contain at most 4,096 states. The first `d` nodes must be the canonical input nodes `{"input": i}` in order. Every later node is an affine combination of earlier nodes with a rational constant and at most 64 distinct parent terms. There are at most 64 nodes.

Each assumption or observation is a closed interval on one node. At most 16 observations and 128 assumptions are admitted, and the final compiled system, including box inequalities, may have at most 128 inequalities. Reversed observation intervals are valid syntax and describe an inconsistent input; empty domain bounds are malformed and are rejected. Parsed rationals are limited to 512 bits and compiled exact values to 4,096 bits.

## Translation-path graph

```json
{
  "vertices": ["request", "walk", "bad-use"],
  "source": 0,
  "bad_vertices": [2],
  "edges": [
    {"id": "e00", "tail": 0, "head": 1, "residual_node": 2},
    {"id": "e01", "tail": 1, "head": 2, "residual_node": 3}
  ]
}
```

There are 2--64 uniquely named vertices. `source` is one vertex index; `bad_vertices` is a nonempty sorted unique list that excludes the source. There are 1--64 uniquely named edges, sorted lexicographically by `id`. `tail < head` is required, so the declared vertex order is topological. `residual_node` identifies an accounting node.

Every edge residual must compile to an integer-valued affine form on the integer grid and must be nonnegative over the entire declared input box. An edge is open in state `z` exactly when its residual is at least one. The schema rejects a graph in which no bad vertex is structurally reachable when all edges are enabled; such a graph would make the property true without evidence.

A state is admitted when it lies in the input box and satisfies every assumption and observation interval. A model is:

- `INCONSISTENT` if no state is admitted;
- `INSUFFICIENT` if at least one admitted state opens a source-to-bad path;
- `PROVED` if the admitted set is nonempty and every admitted state is path-safe.

## Uniform-cut certificate

```json
{
  "kind": "uniform_cut",
  "witness": [0, 0],
  "reachable": [0, 1],
  "edge_proofs": [
    {"edge": "e03", "certificate": { ... arithmetic certificate ... }}
  ]
}
```

`witness` must be an admitted state. `reachable` is a sorted unique source-side set that contains the source and excludes every bad vertex. `edge_proofs` must contain exactly the sorted set of graph edges whose tail lies in `reachable` and whose head lies outside it. Each embedded arithmetic certificate is checked against a freshly constructed local model asserting that the corresponding residual is at most zero. Because residuals are globally nonnegative, the accepted local proof establishes that the edge is identically closed on every admitted state.

The outgoing cut must be nonempty. Certificates cannot omit a cut edge, add a non-cut edge, or substitute another residual.

## Maximal-signature-cover certificate

```json
{
  "kind": "signature_cover",
  "witness": [0, 0],
  "signatures": [
    {
      "open_edges": ["e00", "e02"],
      "reachable": [0, 1, 3]
    }
  ]
}
```

`witness` must be admitted. `signatures` is a sorted unique list with at most 4,096 entries. For each entry, `open_edges` is a sorted unique edge-id list and `reachable` must equal the canonical graph-reachability closure from the source under exactly those edges. No listed reachable set may contain a bad vertex.

The checker independently enumerates the complete integer box, filters admitted states, computes each exact open-edge signature, and reduces the resulting family to its set-inclusion-maximal members. The supplied entries must equal that maximal antichain exactly. A cover cannot prove an inconsistent model, omit a maximal signature, add an unrealized signature, forge reachability, or replace the exact antichain with a merely safe superset.

## Inconsistency certificate

```json
{
  "kind": "inconsistent",
  "certificate": { ... arithmetic inconsistency certificate ... }
}
```

The embedded certificate is checked by the independent arithmetic checker against the accounting constraints. The result is `INCONSISTENT`, never `PROVED`.

## Arithmetic certificates

The local arithmetic checker supports four kinds:

- `linear`: an admitted witness and nonnegative Farkas multipliers proving an affine upper bound;
- `quantized`: the same identity with a strict bound below the valid lattice quantum;
- `finite_cover`: an admitted witness plus one checked result for every integer state in the declared box;
- `inconsistent`: an exact contradiction certificate, optionally using the finite grid when rational feasibility differs from integer feasibility.

See `src/checker.py` and `proofs.md` for exact identities. The checker never trusts a numeric objective value supplied by the producer.

## Separate binary-affine path-budget backend

`reviewer_hardening/path_budget.py` and `independent_path_budget.py` consume a
different named-variable graph with one bad vertex. Each edge's `open` affine
expression must be exactly `x` or `1-x`, with that coordinate bounded by `[0,1]`.
It is therefore Boolean and equals the edge-open indicator. A general TPEG
residual opens on positivity; its threshold indicator need not be affine. No
adapter from arbitrary residuals is supplied, and `src/tpeg_checker.py` does not
dispatch a `path_budget` envelope.

The separate certificate has exactly `type`, `model`, `witness`, and
`obligations`; `type` is `path_budget`, `model` matches the supplied model name,
and the admitted integer witness assigns all named variables. Each obligation
contains `path` and nonnegative rational `multipliers` keyed by constraint name.
Obligations must equal the complete canonical source-to-bad path set, subject
to the 4,096-path cap. Their weighted affine coefficients must match the sum of
declared edge indicators; that sum's constant plus the weighted right-hand side
must be at most the path length minus one. Exact witness, coefficient, path and
indicator checks are required. See the backend source for its graph schema.

## Result files

`run_tpeg_cases.py` writes one JSON result per model. Timing fields are measurements, not certificate inputs. `INSUFFICIENT` files contain only aggregate unsafe-state counts and no path or state witness. Certificate JSON is stored separately under `tpeg_results/certificates/` only for `PROVED` and `INCONSISTENT` decisions.
