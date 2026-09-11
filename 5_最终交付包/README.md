# 5 · Final deliverable

> 最终交付包。已定稿，勿改。

The frozen submission package.

**Start here:** [`REPORT.en.md`](MA-Hackathon-Final-2026-09-04/REPORT.en.md) — the full report in English.
It also reads as a web page at **[https://bella10142003.github.io/kiva-narrative-saturation/](https://bella10142003.github.io/kiva-narrative-saturation/)**.

**Language.** English is the primary version throughout: the report, methods appendix, runbook, QA record,
speaker notes and all 42 result tables. Kept alongside as the submitted artefacts, in Chinese:
`REPORT.md` and its HTML rendering, `JUDGE_QA_BILINGUAL.md`, `SPEAKER_CUES_ZH.md`.

| Path | What it is |
|---|---|
| `MA-Hackathon-Final-2026-09-04/REPORT.en.md` | **The full written report (English)** |
| `…/REPORT.md` | The Chinese original as submitted |
| `…/METHODS_APPENDIX.md` | Methods appendix — estimator, pools, controls, clustering |
| `…/outputs/` | 42 result tables as CSV, including `rq1_main_table.csv` and `robustness.csv` |
| `…/figures/` | 8 figures as PNG and PDF, each with its source data table |
| `…/src/` | 18 clean modules — `build_pool_features.py`, `fit_main_models.py`, `text_pipeline.py`, `safe_pickle_audit.py` and others |
| `…/notebooks/` | Auto-generated S0–S6 audit notebooks that re-execute the pipeline |
| `…/FINAL_QA.md` · `…/audit/` | The 20 QA gates and the manifests behind them |
| `…/MANIFEST_SHA256.txt` | SHA-256 of every packaged file |
| `…/RUNBOOK.md` | How to re-run everything from scratch |
| `…/JUDGE_QA_BILINGUAL.md` · `…/SPEAKER_NOTES_EN.md` | Presentation material |
| `When_Every_Story_Sounds_The_Same v*.pptx` | Deck revision history, v2.4 through v3.0. v3.0 (20 slides) is the latest |
| [`../site/Kiva_Presentation_v3.0.pdf`](../site/Kiva_Presentation_v3.0.pdf) | **v3.0 exported to PDF** — readable in the browser without downloading |

Note: 19 files in this package had absolute local paths redacted before publication, so their hashes no
longer match `MANIFEST_SHA256.txt`. See *A note on redaction* in the [root README](../README.md).
