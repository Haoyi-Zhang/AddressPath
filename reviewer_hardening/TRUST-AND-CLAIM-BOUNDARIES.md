# Trusted computing base and claim boundaries

## Favorable-result trusted base

A `PROVED` result is sound only relative to all of the following:

1. **Declared finite model.** Variable domains, affine constraints, graph nodes, edges, source nodes, bad nodes, and edge-opening predicates faithfully state the intended abstract problem.
2. **Certificate checker.** The small checker correctly parses exact integers/rationals, reconstructs canonical graph objects, validates arithmetic witnesses, and rejects omitted or extra obligations.
3. **Host execution semantics.** Python arbitrary-precision integer and `fractions.Fraction` behavior, the standard-library JSON parser wrapper, and filesystem bytes are functioning as specified.
4. **Conditional refinement premises.** Every in-scope concrete epoch maps to an allowed abstract state; every in-scope concrete ownership violation induces an abstract source-to-bad open path; event binding, reset/overflow behavior, concurrency, and ownership labels are correct.

The certificate generator, benchmark labels, plotting code, expected-result files, and paper tables are **not** trusted for proof soundness. They may propose a certificate, but the checker must reconstruct and validate every obligation. The independent finite oracle and architecture-case oracle are validation evidence, not members of the proof base.

## Deliberate nonclaims

The project does not establish security of a named processor, completeness of a particular performance-counter interface, RTL-to-model equivalence, absence of unmodeled speculative or concurrent paths, full noninterference, exploitability, or a universal polynomial-time decision procedure. `INSUFFICIENT` means that the supplied model and evidence do not prove the property; it is not a vulnerability report. `INCONSISTENT` means that no declared state satisfies the assumptions; it is not a favorable security result.

## Complexity contract

| Mechanism | Checker work in the explicit input | Potential source of blow-up |
|---|---|---|
| Local arithmetic proof | Polynomial in variables, constraints, and witness entries | Generator may need expensive proof search |
| Uniform cut | Polynomial in the explicit cut, graph, and local proofs | Finding a useful cut is outside checker soundness |
| Path budget | Polynomial in the **explicit canonical bad-path list** and arithmetic witnesses; no state enumeration | A DAG may contain exponentially many simple bad paths |
| Maximum-signature cover | Polynomial in the explicit state/signature cover and reachability data | Exact state/signature representation may be exponential |
| Independent oracle | Enumerates all bounded states | Exponential in encoded domain size; validation only |

The compact path-budget rule therefore removes state enumeration for the demonstrated families, including a family whose explicit signature cover has exponential size. It does not imply polynomial behavior for arbitrary graphs or establish completeness beyond its declared arithmetic proof system.
