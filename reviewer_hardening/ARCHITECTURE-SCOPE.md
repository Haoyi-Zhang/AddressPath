# Architecture-shaped case scope

The case names denote common translation-control motifs: serial page-walk and
permission gates, two-stage translation, context fan-out, and a recheck chain.
Only the graph shape is architecture-motivated.  The event variables and
numeric constraints are synthetic and deterministic.  These cases therefore
test checker behavior and modeling expressiveness; they do not certify Sv39,
a RISC-V IOMMU, Rocket Chip, or any deployed implementation.

A concrete claim would additionally require a reviewed mapping from RTL and
execution epochs to graph states, event-binding validation, path completeness,
and evidence that every ownership violation induces a modeled bad path.
