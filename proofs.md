# Proof companion

This document states the mathematics checked by the repository. It is a written proof companion, not a proof-assistant development. The paper is the authoritative exposition; this file gives an implementation-oriented statement of each obligation.

## 1. Accounting semantics and exact affine compilation

Let the finite input domain be

\[
D=\prod_{i=1}^{d}\{L_i,L_i+1,\ldots,U_i\}\subseteq\mathbb Z^d.
\]

The node list is acyclic. The first `d` nodes are the coordinates of `z∈D`; every later node is a rational affine combination of earlier nodes. By induction over node order, each node `j` denotes one exact rational affine form

\[
f_j(z)=a_j^Tz+c_j.
\]

The compiler in `src/checker.py` performs exactly that induction with `fractions.Fraction`. Every closed interval `l≤f_j(z)≤u` becomes two exact inequalities. Adding the box inequalities yields a system `Az≤b`. The TPEG compiler repeats the affine expansion independently after the base checker validates syntax.

**Lemma 1 (exact compilation).** For every `z∈D`, evaluation of the original affine DAG and evaluation of its compiled form agree at every node. Consequently `z` satisfies the source assumptions and observations exactly when `Az≤b`.

**Proof.** Input nodes are coordinate projections. For a derived node, assume equality for every parent. Substituting the parent affine forms into the declared rational linear combination gives the compiler's coefficient vector and offset, hence preserves the value. Interval compilation is algebraic rearrangement, so satisfaction is preserved. ∎

No floating-point rounding is involved. Parser and expression-size limits are denial-of-service controls, not mathematical approximations.

## 2. TPEG safety semantics

A TPEG is a directed acyclic graph `G=(V,E)` with source `s`, nonempty bad set `B⊂V\{s}`, and one declared nonnegative integer-valued residual `ρ_e(z)` for each edge. The checker verifies nonnegativity over the complete input box, which is stronger than nonnegativity only on admitted states.

For admitted state `z`, define

\[
\operatorname{Open}(z)=\{e\in E: \rho_e(z)\ge1\}.
\]

Because every residual is integer valued and nonnegative, an edge is closed exactly when its residual is zero. A state is safe when no vertex in `B` is reachable from `s` using only `Open(z)`. Let `S={z∈D:Az≤b}`. The exact decision is:

- `INCONSISTENT` if `S=∅`;
- `INSUFFICIENT` if some `z∈S` is unsafe;
- `PROVED` if `S≠∅` and every `z∈S` is safe.

The nonempty requirement prevents vacuous safety from contradictory evidence.

## 3. Conditional lifting to concrete ownership isolation

Let `C` be a declared set of concrete epochs and `Iso(τ)` the concrete ownership property. Let `α:C→D` be an abstraction. Assume:

1. **Evidence coverage:** `α(τ)∈S` for every `τ∈C`.
2. **Violation-to-path coverage:** if `¬Iso(τ)`, then every edge of some source-to-bad path has positive residual at `α(τ)`.

**Theorem 2 (conditional lifting).** If the TPEG decision is `PROVED`, then `Iso(τ)` holds for every `τ∈C`.

**Proof.** A violating epoch would map, by evidence coverage, to an admitted state. Violation-to-path coverage would make that state unsafe. This contradicts universal TPEG safety. ∎

The implementation cannot check these processor-specific premises. They are part of the model contract. `INSUFFICIENT` does not establish a concrete violation because the open abstract path may be spurious.

**Proposition 3 (extension non-monotonicity).** A proof for `G` need not survive adding a source-to-bad path. It survives only if every added path is blocked in every admitted state or is excluded by concrete scope.

**Proof.** Add a direct source-to-bad edge with constant residual one. The admitted set is unchanged but every admitted state becomes unsafe. The converse follows from path reachability. ∎

This is the formal reason that path completeness is a separate obligation.

## 4. Local arithmetic zero certificates

For one edge residual, the local model asks whether

\[
q(z)=c^Tz+q_0\le0
\]

for every integer `z` satisfying `Az≤b`, while retaining an admitted witness.

### 4.1 Rational linear certificate

A `linear` certificate supplies an admitted integer witness `w` and nonnegative rational multipliers `λ≥0` satisfying

\[
A^T\lambda=c,
\qquad
b^T\lambda+q_0\le0.
\]

For every feasible `z`,

\[
q(z)=c^Tz+q_0=\lambda^TAz+q_0
\le\lambda^Tb+q_0\le0.
\]

The witness proves non-vacuity. The checker recomputes all identities exactly.

### 4.2 Quantized certificate

Let `δ>0` be any valid lattice quantum for `q(D)`: every value of `q` is an integer multiple of `δ`. The checker derives a valid quantum from the exact coefficient and offset subgroup. A `quantized` certificate checks the same nonnegative linear identity but requires the rational upper bound to be strictly less than `δ`. Since no positive multiple of `δ` lies below `δ`, every feasible integer value is nonpositive.

Strictness is essential. A bound equal to `δ` permits one positive quantum and is rejected as a proof of zero.

### 4.3 Finite cover and inconsistency

A `finite_cover` certificate checks every state in `D`, recording whether it is inadmissible or, if admitted, satisfies the assertion. It is sound and complete for the declared bounded grid, not for an unbounded model. An inconsistency certificate proves `S=∅` either by an exact rational contradiction or by exhausting the finite integer grid. Inconsistency is a third decision, never a safety proof.

## 5. Uniform-cut certificates

For vertex set `R⊆V`, let

\[
\delta^+(R)=\{(u,v)\in E:u\in R,\ v\notin R\}.
\]

A uniform-cut certificate contains an admitted witness, a set `R` with `s∈R` and `R∩B=∅`, and one accepted local zero certificate for every edge in `δ⁺(R)`.

**Theorem 4 (uniform-cut soundness).** Every admitted state is safe when a uniform-cut certificate is valid.

**Proof.** Suppose an admitted state opens a path from `s` to a bad vertex. Since the path starts in `R` and ends outside `R`, it has a first edge in `δ⁺(R)`. The corresponding local certificate proves that edge's nonnegative residual is at most zero in every admitted state, hence exactly zero and closed. This contradicts the path being open. ∎

Define the universally closed edge set

\[
Z=\{e\in E:\forall z\in S,\rho_e(z)=0\}.
\]

Delete `Z` from `G` and let `R*` be the vertices reachable from `s` in the remaining graph.

**Theorem 5 (uniform-cut characterization).** A uniform cut exists exactly when `R*∩B=∅`.

**Proof.** If `R*` excludes every bad vertex, every edge leaving `R*` must be in `Z`; otherwise that edge would extend reachability. Thus `R*` is a uniform cut. Conversely, let `R` be any uniform cut. Every edge leaving `R` lies in `Z`, so no path in `G\Z` can leave `R`; every vertex reachable from `s` lies in `R`, which excludes `B`. ∎

The producer uses this characterization. It computes the edges absent from every admitted signature, deletes them, and chooses `R*`. The checker does not trust that computation: it checks the supplied cut and each local certificate directly.

A sink-adjacent-zero baseline is the special case requiring every edge whose head is bad to be universally closed. It is sufficient but not necessary: an upstream cut may separate all paths while sink-adjacent residuals remain unconstrained.

## 6. Maximal-signature covers

For admitted state `z`, its signature is the open-edge set `σ(z)=Open(z)`. Let

\[
\Sigma=\{\sigma(z):z\in S\},
\qquad
\operatorname{Max}(\Sigma)=\{\sigma\in\Sigma:\nexists\tau\in\Sigma,\sigma\subsetneq\tau\}.
\]

Path safety is downward closed under edge deletion.

**Lemma 6 (downward closure).** If graph `(V,τ)` has no source-to-bad path and `σ⊆τ`, then `(V,σ)` has no source-to-bad path.

**Proof.** Every path using edges in `σ` is also a path using edges in `τ`. ∎

**Theorem 7 (maximal-signature sufficiency).** If every signature in `Max(Σ)` is safe, every admitted state is safe.

**Proof.** Each finite signature `σ∈Σ` is contained in at least one inclusion-maximal member `τ∈Max(Σ)`. Safety of `τ` and Lemma 6 imply safety of `σ`. ∎

**Theorem 8 (bounded exactness).** For the declared finite grid, a certificate that lists exactly `Max(Σ)` and checks every listed signature safe exists if and only if the exact TPEG decision is `PROVED`.

**Proof.** Soundness is Theorem 7 plus the admitted witness. If the exact decision is `PROVED`, the finite family `Σ` is nonempty and every member is safe, so its finite maximal antichain exists and is a valid certificate. ∎

The checker re-enumerates the entire grid and requires equality with the exact maximal antichain; it does not accept an arbitrary safe cover. It recomputes canonical reachability for every listed signature. This choice reduces trust in the producer at the cost of exponential worst-case work.

## 7. Exponential exact-cover family

For `n` independent bits `x_1,…,x_n`, build `n` parallel two-edge source-to-bad paths. On path `i`, the first edge has residual `x_i` and the second has residual `1-x_i`. In every state exactly one edge per path is open, so no complete path is open and the model is safe. Every edge opens in some state, so `Z=∅` and no uniform cut exists.

Each bit vector yields a distinct signature containing exactly one edge from every path. No such signature strictly contains another, hence all `2^n` signatures are maximal.

**Theorem 9 (exact-cover lower bound).** The exact maximal-signature representation used by the checker has `2^n` entries on this family.

The retained corpus uses `n=1,…,6`, holding the input box at 4,096 states by adding inert bounded coordinates as necessary. The number of maximal signatures is 2, 4, 8, 16, 32, and 64; the final certificate is 13,277 bytes. This is a lower bound for this exact representation, not for every possible symbolic proof system.

## 8. Producer decision completeness under the repository bound

The bounded producer enumerates every state in the declared box, computes the admitted signatures, and counts unsafe states.

- If no state is admitted, it returns a separately checked inconsistency certificate.
- If any admitted state is unsafe, it returns `INSUFFICIENT` and no certificate.
- If all admitted states are safe and deleting universally closed edges separates source from bad, it returns a uniform-cut certificate.
- Otherwise it returns the exact maximal-signature cover.

**Proposition 10.** Subject to the parser and 4,096-state bounds and successful local arithmetic-certificate construction, the producer returns the exact three-way decision, and every positive decision has a checker-accepted certificate.

**Proof.** Exhaustive enumeration gives the exact admitted and unsafe sets. Theorem 5 is complete for uniform cuts. Theorem 8 supplies the fallback for every remaining safe finite model. Inconsistency is handled separately. ∎

The proposition concerns the bounded model only. It does not establish scalability beyond the declared limits.

## 9. Independent finite checks

`src/tpeg_oracle.py` does not import the TPEG checker or producer. It evaluates the original node DAG directly, filters intervals directly, constructs each open-edge set directly, and computes reachability directly. Every retained case requires oracle agreement on decision, admitted-state count, unsafe-state count, and number of distinct signatures.

`exhaustive_meta.py` independently generates all structurally relevant four-vertex DAGs with at most four edges and all tested maximal-signature antichains. For each family it compares exact safety with the signature criterion and compares uniform-cut existence with deletion of edges absent from every signature. The retained run checks 2,865 antichains, of which 683 are safe and 2,182 unsafe. Among safe families, 363 have a uniform cut and 320 are safe only through a signature cover. Both characterizations pass.

`exhaustive_arithmetic_meta.py` independently generates 3,915 small one- and two-input arithmetic systems. It directly enumerates 11,160 finite states, computes the three-way semantic decision without importing the producer, asks the producer for its decision and certificate, and sends every favorable or inconsistency certificate through the strict checker. The retained classification is 1,222 `PROVED`, 941 `INSUFFICIENT`, and 1,752 `INCONSISTENT`; all four certificate forms are exercised. Producer, direct semantics, and checker agree throughout.

These finite checks can expose implementation or statement mismatches. They do not replace the general proofs above, prove completeness outside their declared generators, or constitute external review.

## 10. What is not proved

The repository does not prove that any real performance counter is complete, that a supplied TPEG covers all processor paths, that an observation belongs to one request epoch, that a model is empirically accurate, or that a deployed processor satisfies a relational confidentiality property. It proves only the declared bounded graph property, and the concrete lifting theorem remains conditional on explicit refinement premises.
