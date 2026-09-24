# Dated venue-readiness matrix

**Target:** ACM Transactions on Architecture and Code Optimization (TACO)  
**Freeze date:** 2026-09-20

This file is a readiness matrix, not a guarantee of admissibility or acceptance. The live submission portal and current journal instructions override the frozen checks below. `venue_source_status.json` records retrieval status and hashes for the official ACM pages consulted; an HTTP refusal is never treated as proof of a rule.

| Area | Frozen project status | Machine checked | Must be rechecked by accountable authors at submission |
|---|---|---:|---|
| ACM LaTeX class | Uses `acmart`; class options are recorded in `venue_mechanical_status.json` | Yes | Confirm the journal's currently requested review format and class options |
| Anonymous review package | Visible text, PDF metadata, author commands, acknowledgments, emails, and repository identifiers are scanned | Yes | Remove or restore identities exactly as required by the live workflow |
| Paper structure | Title, abstract, CCS concepts, keywords, body, references, limitations, and artifact statement are checked | Yes | Confirm article type and any journal-specific section requirements |
| Length | Body/reference start and total pages are measured from the built PDF | Yes | Confirm current TACO length and overlength rules; the package does not infer them from stale memory |
| Bibliography | Citation-key closure, identifier uniqueness, metadata snapshots, and known corrections are checked | Yes | Human source-content audit and permissions review |
| Figures/tables | Source data, labels, PDF rendering, font embedding, and clipping are checked | Yes | Accessibility text and production-stage requirements |
| Reproducibility | Clean-archive replay, exact semantic results, independent oracles, and checksums are checked | Yes | Decide whether to request or enter an ACM artifact-review workflow if available/applicable |
| Authorship and AI use | A broad AI-use record and human-responsibility gate are included | Partly | Determine eligible human authors, contribution statements, conflicts, disclosures, and current policy wording |
| Ethics/security | Defensive scope and non-exploit framing are explicit | Yes | Institution-specific review, export-control, disclosure, and legal obligations |
| Copyright/licensing | Third-party source code is not vendored in the architecture provenance layer | Yes | Complete ACM rights forms and verify permissions for any externally supplied material |
| Submission metadata | Not present in the anonymous archive | N/A | Enter title, abstract, authors, ORCIDs, conflicts, funding, suggested reviewers, and declarations in the live portal |

A project can pass every machine check here and still be unsuitable for submission if its scientific claims are not endorsed by accountable domain experts. This matrix deliberately leaves portal-only and human-responsibility steps open rather than asserting compliance that the artifact cannot establish.
