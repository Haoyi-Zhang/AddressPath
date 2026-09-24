# Source boundary and reading record

## Calibration coverage

The retained calibration set contains **12 TACO research articles, five
foundational or demonstrably influential papers, and five adjacent
architecture-verification papers**.  For each of those 22 works, the substantive
arc available from the publisher full text or an author manuscript was
inspected: motivating problem, claimed principle, core mechanism or theorem,
evidence design, practical connection, limitations or conclusion, and the role
of figures and tables.  The compact pattern matrix and the paper-specific
lessons are recorded in `../research-plan.md`; exact locators, access mode, and
integration mode are recorded in `external_resources.csv`.

This is targeted scientific and narrative calibration, not a systematic review,
a bibliometric study, or proof that no related formulation exists.  Background
citations in the manuscript are not silently counted as full-paper calibration.
No external solver, benchmark, RTL, counter tool, or paper artifact was executed
or modified.

## Quantifier and contribution boundary

CounterPoint asks whether a noisy observation region is compatible with a
candidate microarchitectural model and uses feasibility to refute or refine
assumptions.  A nonempty feasible set is existential.  The TPEG property is
universal over all admitted states and additionally requires that every
in-scope concrete violation induce an open source-to-bad path.  CounterPoint's
empirical cases, decision diagrams, and counter measurements are not copied or
reproduced here, and this project does not claim that CounterPoint endorses the
lifting theorem.

The local rational implication rule is classical Farkas/linear-programming
reasoning.  The strict integer-quantum rule is also a small, familiar integer
reasoning step.  VIPR and later certificate-construction work establish much
stronger general integer-programming proof systems.  Neither a separate checker
nor an integer threshold is claimed as the contribution.  The contribution is
the architecture-facing decomposition into evidence coverage, violation-to-path
coverage, local edge closure, and global path separation, plus the exact bounded
fallback and its representation boundary.

Uniform cuts are graph separators whose outgoing edges are proved closed for
all admitted states.  Their local arithmetic proofs are conventional; the paper
proves the TPEG-specific soundness and the deletion characterization.  Exact
maximal-signature covers are a finite antichain representation.  They are not
claimed to be a new general symbolic-verification method.  Their role is a
checker-verifiable, bounded-complete fallback when state-dependent exclusion
prevents every fixed cut.  The explicit alternating-path family shows an
exponential lower bound for this exact representation only, not for BDD, SAT,
interpolant, or other proof systems.

## Architecture and security boundary

PipeCheck, COATCheck, RTLCheck, and RTL2MμPATH connect architectural obligations
to microarchitectural or RTL behavior.  They are not replaced by TPEG.  Their
kind of model derivation can help discharge the path-coverage and event-binding
premises that the present artifact intentionally leaves outside the checker.
An omitted path, an incorrect event binding, or an epoch outside the observation
scope invalidates concrete lifting even if the finite certificate is accepted.

Hardware–software contract and hyperproperty work establishes relational
security objectives that are stronger and semantically different from the
single-epoch ownership-path safety assertion checked here.  The manuscript does
not claim confidentiality, integrity, noninterference, timing-channel freedom,
correct page-table contents, or a security verdict for any deployed processor.
`INSUFFICIENT` means only that the supplied model and intervals do not entail
the declared assertion; `INCONSISTENT` means that no admitted state exists.

## Reuse and redistribution

All exact computational inputs consumed by the artifact are newly authored
synthetic JSON models retained in `cases/` and `tpeg_cases/`.  Scholarly text,
figures, empirical datasets, hardware models, and upstream solver code are not
redistributed.  The supplied ACM class and bibliography style are retained
unmodified with their license and source notice.  Public scholarly identifiers
support independent source retrieval, but the artifact has no network
requirement and does not download sources during reproduction.
