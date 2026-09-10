# 2025 holdout · use vs description

Status: matched-sample diagnostic generated from the corrected working checkpoints. This is not a final-package update.

## Design

- Train: 2016-2024 (1,234,124 loans); untouched holdout: 2025 (133,409 loans).
- All three models use the same rows and categorical context.
- `controls_plus_use` adds use-based C/H/CH/V/G/VG; `controls_plus_description` adds description-based C/H/CH/V/G/VG.
- Both sides use raw H/G and exclude recurring-language share to isolate field choice; this holdout does not test the template-removed specification.

## Bottom line

- Description outperforms use on every metric in the two primary tables, but the margins are small.
- Description does not stably outperform controls only: it improves hour MAE (166.71 vs 168.27) and 72-hour log-loss (0.4253 vs 0.4275), while the other seven reported primary metrics are worse.
- These are descriptive metric differences without paired uncertainty; they do not support deployment of borrower-level narrative scoring.

## Primary 35-day-follow-up duration metrics

| Model | log-hour MAE | log-hour RMSE | log-hour R2 | hour MAE |
| --- | ---: | ---: | ---: | ---: |
| Controls only | 0.9663 | 1.2283 | 0.5540 | 168.27 |
| Controls + use | 0.9831 | 1.2532 | 0.5358 | 168.60 |
| Controls + description | 0.9768 | 1.2447 | 0.5421 | 166.71 |

## Primary 72-hour metrics with at least 35 days of follow-up

| Model | Brier | ROC AUC | Average precision | Log-loss | Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| Controls only | 0.1340 | 0.9007 | 0.9052 | 0.4275 | 0.8189 |
| Controls + use | 0.1364 | 0.8936 | 0.8990 | 0.4284 | 0.8057 |
| Controls + description | 0.1350 | 0.8961 | 0.9004 | 0.4253 | 0.8092 |

Metric differences are descriptive; paired uncertainty was not estimated. Lower is better for MAE, RMSE, Brier, and log-loss; higher is better for R2, AUC, average precision, and accuracy.
