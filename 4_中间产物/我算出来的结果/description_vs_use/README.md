# Description vs use · sensitivity comparison

Status: validated comparison generated from the corrected 2026-08-31 working run. This is not a final-package update.

## Bottom line

- **Current channel is directionally robust.** `CH` is positive under both `use` (0.101665, 95% CI 0.035671 to 0.167658) and `description` (0.129794, 95% CI 0.087522 to 0.172066). The description point estimate is 0.028130 higher, but this is not a formal cross-model difference test.
- **Recent interaction is representation-sensitive.** `use` gives a positive `VG` (0.041748, 95% CI 0.014326 to 0.069169); `description` gives -0.013572 with a confidence interval crossing zero (-0.044115 to 0.016971).
- **The current-channel estimate is sensitive to recurring language.** After removing train-only recurring 5-grams, `use` CH changes from 0.101665 to 0.052319 (95% CI -0.015770 to 0.120409; p=0.129), while `description` CH changes from 0.129794 to 0.057988 (95% CI 0.001340 to 0.114635; p=0.045). Both point estimates are substantially attenuated; this is sensitivity evidence, not a decomposition of how much templates "explain."
- The fields measure closely related but non-identical environments: common-sample correlations are H=0.9047, G=0.9164, CH=0.8586, and VG=0.9009.

## Comparability checks

- Model rows: `use` 1,234,131; `description` 1,234,124. Description is a strict subset, missing only 7 rows from the use sample.
- Nonempty coverage: use 97.3121%; description 97.3114%.
- Median tokens: use 10; description 93.
- Description identity check: max absolute error 1.721e-15 against threshold 1e-9; passed.
- Working use and description coefficients match the corrected `_rebuild` outputs at rtol=1e-6 and atol=1e-8.

## Coefficients

| Term | use estimate (95% CI; p) | description estimate (95% CI; p) | desc - use |
| --- | ---: | ---: | ---: |
| C | 0.520247 (0.440232, 0.600261; 0) | 0.445054 (0.312708, 0.577399; 2.21e-08) | -0.075193 |
| H | 0.403605 (0.275829, 0.531382; 9.05e-08) | 0.515361 (0.442617, 0.588104; 0) | 0.111756 |
| CH | 0.101665 (0.035671, 0.167658; 0.00331) | 0.129794 (0.087522, 0.172066; 1.66e-07) | 0.028130 |
| V | 0.049666 (-0.092252, 0.191585; 0.485) | 0.136727 (-0.072764, 0.346219; 0.195) | 0.087061 |
| G | -0.138532 (-0.256054, -0.021009; 0.0219) | -0.225185 (-0.370063, -0.080306; 0.00306) | -0.086653 |
| VG | 0.041748 (0.014326, 0.069169; 0.00366) | -0.013572 (-0.044115, 0.016971; 0.376) | -0.055319 |

## Recurring-language sensitivity

- Rule: masked 5-grams defined using 2016-2024 training documents only, appearing in at least 659 training documents and at least 3 countries.
- Approved recurring phrases: use 409; description 9,334.
- Loans with a nonzero removed-token share: use 38.8510%; description 96.0418%.
- Median removed-token share: use 0.0000; description 0.4390. Description is much longer (median 93 vs 10 tokens), so phrase counts are not directly comparable as an institutional-template rate.

| Field / term | Raw estimate (95% CI; p; n) | After recurring-language removal (95% CI; p; n) | Residual - raw |
| --- | ---: | ---: | ---: |
| use / CH | 0.101665 (0.035671, 0.167658; 0.00331; 1,234,131) | 0.052319 (-0.015770, 0.120409; 0.129; 1,149,206) | -0.049345 |
| use / VG | 0.041748 (0.014326, 0.069169; 0.00366; 1,234,131) | 0.058463 (0.026083, 0.090843; 0.000708; 1,149,206) | 0.016716 |
| description / CH | 0.129794 (0.087522, 0.172066; 1.66e-07; 1,234,124) | 0.057988 (0.001340, 0.114635; 0.045; 1,230,306) | -0.071806 |
| description / VG | -0.013572 (-0.044115, 0.016971; 0.376; 1,234,124) | 0.007778 (-0.038808, 0.054363; 0.738; 1,230,306) | 0.021350 |

## Interpretation boundary

This report covers raw field choice and recurring-language sensitivity for the 2016-2024 log-duration HDFE model. The matched-sample raw-field 2025 holdout is reported separately in `HOLDOUT_2025.md`; template-removed 2025 extrapolation, the description 72-hour HDFE model, heterogeneity, and a description-based Narrative Attention Engine have not been tested. The data have no Lending Partner identifier, so phrases are described only as recurring or boilerplate-like language. Coefficient differences are descriptive and all estimates are conditional associations, not causal effects.

## Sources

- `4_中间产物/我算出来的结果/outputs/rq1_main_table.csv`
- `4_中间产物/我算出来的结果/outputs/robustness.csv`
- `4_中间产物/我算出来的结果/outputs/description_robustness.csv`
- `4_中间产物/我算出来的结果/outputs/boilerplate_like_phrases.csv`
- `4_中间产物/我算出来的结果/outputs/boilerplate_share_distribution.csv`
- `4_中间产物/我算出来的结果/outputs/description_boilerplate_phrases.csv`
- `4_中间产物/我算出来的结果/outputs/description_boilerplate_share_distribution.csv`
- `4_中间产物/我算出来的结果/audit/description_robustness_manifest.json`
- `4_中间产物/我算出来的结果/outputs/text_field_diagnostics.csv`
- `4_中间产物/我算出来的结果/outputs/text_selection_diagnostics.csv`
- `4_中间产物/data/description_model.parquet`
