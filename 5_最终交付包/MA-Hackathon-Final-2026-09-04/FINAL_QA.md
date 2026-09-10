# Final QA Status

**FAIL · 19/20 deterministic checks passed.**

| Check | Status |
|---|---:|
| required deliverables present | PASS |
| no symlinks | PASS |
| no raw pickle or private/raw checkpoint directory | PASS |
| JSON files parse | PASS |
| CSV files parse with stable row widths | PASS |
| seven executed notebooks contain no error outputs | PASS |
| portable HTML report validation and browser verification passed | PASS |
| PPTX has 16 slides, 16 notes, eight embedded figures and renders 16 pages | FAIL |
| pickle opcode intake gate passed | PASS |
| pool algebra identity gate passed | PASS |
| joint scenario endpoint support gate passed | PASS |
| headline scenario values and recent-null boundaries match source tables | PASS |
| analysis sample split reconciles exactly | PASS |
| scenario intervals use the documented t(45) critical value and bounded units | PASS |
| headline semantics are consistent across report, scripts, notes and PPTX | PASS |
| 2025 no-deployment boundary matches holdout metrics | PASS |
| working-copy parquet schemas omit names, exact locations and full narrative text | PASS |
| no credential-like values in text artifacts | PASS |
| reproducibility seed is neutral and consistent | PASS |
| external-facing artifacts omit archival source-file links | PASS |

Full machine-readable evidence: `audit/final_qa.json`.

This receipt validates internal consistency, artifact structure and privacy boundaries; it does not convert observational associations into causal evidence or authorize deployment.
