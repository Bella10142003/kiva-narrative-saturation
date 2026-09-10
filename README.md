# When Every Story Sounds the Same

**Narrative saturation and funding speed on Kiva** — UNSW MA Hackathon 2026, Team *5 GUYS*.

> 中文说明见 **[README.zh-CN.md](README.zh-CN.md)**（更详细，含逐步骤导读）。

Kiva borrowers compete for lender attention. This project asks whether a loan is funded more
slowly when the loans it competes against are not just **numerous** but also **narratively
similar** — when every story on the page sounds the same. We rebuild, for each of
**1,453,846 loans (2016–2025)**, the exact market that existed the moment it went live, and test
saturation as the *interaction* of pool volume and pool homogeneity.

---

## Headline results

| | Estimate | Interpretation |
|---|---|---|
| **RQ1 — active pool** (`C×H`) | β = **0.1017**, p = 0.0033 | Moving both volume and homogeneity from P25 → P75 lengthens time-to-funding by **+124.35 %** [103.71, 147.08] |
| **RQ2 — recent/completed pool** (`V×G`) | β = **0.0417**, p = 0.0037 | Survives — and strengthens to **0.0585** (p = 0.0007) after stripping lending-partner template language. Market-level *wear-out*, not just live competition |
| **RQ2 joint scenario** | −1.42 % [−15.81, +15.43] | Crosses zero because β<sub>V</sub> > 0 and β<sub>G</sub> < 0 offset each other — **not** evidence of no association |
| **RQ3 — 2016–2025 evolution** | annual marginal effects | [`rq3_year_effects.csv`](5_最终交付包/MA-Hackathon-Final-2026-09-04/outputs/rq3_year_effects.csv) |
| **RQ4 — where it bites** | sector × country | [`rq4_sector_effects.csv`](5_最终交付包/MA-Hackathon-Final-2026-09-04/outputs/rq4_sector_effects.csv) · [`rq4_country_effects.csv`](5_最终交付包/MA-Hackathon-Final-2026-09-04/outputs/rq4_country_effects.csv) |
| **2025 out-of-sample** | **negative result** | Adding narrative features worsens 6 of 7 metrics (R² 0.5524 → 0.5370; AUC 0.8986 → 0.8921). Reported as-is |

All 42 result tables: [`5_最终交付包/MA-Hackathon-Final-2026-09-04/outputs/`](5_最终交付包/MA-Hackathon-Final-2026-09-04/outputs/) ·
8 figures: [`.../figures/`](5_最终交付包/MA-Hackathon-Final-2026-09-04/figures/) ·
full report: [`REPORT.md`](5_最终交付包/MA-Hackathon-Final-2026-09-04/REPORT.md)

---

## Method in one screen

**Saturation channels.** For each focal loan we build two competitor pools of the same sector:

| Channel | Pool | Volume | Homogeneity | Saturation |
|---|---|---|---|---|
| `current` | loans live on the platform at the same moment | `C` = log(1 + pool size) | `H` = mean cosine similarity of the focal description to the pool (z-scored) | `C × H` → **RQ1** |
| `recent` | loans that went live 35–65 days earlier (7-day half-life weights) | `V` | `G` | `V × G` → **RQ2** |

**Why 35 days.** Training-period fundraising duration P95 = 826.891 h = 34.45 days → rounded up to 35.
Every loan in the lagged pool has a ≥95 % chance of having finished fundraising before the focal loan
appeared, so it cannot mechanically affect the focal outcome.

**Estimation.** High-dimensional fixed effects (country + activity + week) with 8 controls
(amount, lender count, term, platform volume, gender, repayment interval, weekday, hour),
two-way clustering on country × week. `pyfixest` 0.60.0.

**Discipline.** Variable definitions were **frozen before any results were inspected**
([step 03](3_分析步骤/03_冻结变量定义.ipynb), [`frozen_spec.csv`](5_最终交付包/MA-Hackathon-Final-2026-09-04/outputs/frozen_spec.csv)).
Pool algebra is verified against brute-force recomputation (max abs error 2.89e−14, threshold 1e−9).
The source `.pkl` is statically audited for dangerous opcodes before it is ever deserialised
([step 00](3_分析步骤/00_安全审计pickle.ipynb)).

---

## Repository layout

| Path | Contents |
|---|---|
| [`1_题目与数据/`](1_题目与数据/) | *Brief & data* — competition PDF, data dictionary, original instructions (raw data **not** included, see below) |
| [`2_提案/`](2_提案/) | *Proposal* — the submitted proposal PDF (the single source of truth), requirements checklist, compliance matrix, assumptions, evidence log |
| [`3_分析步骤/`](3_分析步骤/) | *Analysis pipeline* — 18 numbered notebooks, `00` → `17`, run in order |
| [`4_中间产物/`](4_中间产物/) | *Intermediates* — EDA scripts and tables, recomputation checks, audit manifests (bulk `.parquet` excluded, regenerable) |
| [`5_最终交付包/`](5_最终交付包/) | *Final deliverable* — report, methods appendix, deck, 42 tables, 8 figures, SHA-256 manifest, 20-gate QA |
| [`6_模拟验证/`](6_模拟验证/) | *Simulation validation* — synthetic data with a known ground truth, used early to check the method can recover it |
| [`7_审查记录/`](7_审查记录/) | *Review log* — independent review rounds against `CONTEST_RULES.md` |

Four steps carry most of the technical weight:
[03 freeze definitions](3_分析步骤/03_冻结变量定义.ipynb) ·
[05 build pool features](3_分析步骤/05_构造池特征CHVG.ipynb) ·
[07 main HDFE model](3_分析步骤/07_主模型HDFE.ipynb) ·
[11 counterfactual support check](3_分析步骤/11_反事实支撑域检查.ipynb)

---

## Reproducing

```bash
bash 建立环境.sh            # Python 3.13.3 venv + 15 pinned deps (requirements-lock.txt)
```

Place `Kiva_Loans.pkl` at `1_题目与数据/Kiva_Loans.pkl`, then run the notebooks in
[`3_分析步骤/`](3_分析步骤/) in numeric order. Paths are hard-coded relative to the repo root;
nothing needs editing. In VS Code select the kernel **`Kiva 竞赛 (.venv)`**.

Full runbook: [`RUNBOOK.md`](5_最终交付包/MA-Hackathon-Final-2026-09-04/RUNBOOK.md).

## Data availability

The source dataset (`Kiva_Loans.pkl`, 1.49 GB, 1,453,846 × 27) is **competition material and is not
redistributed here**. Neither are the ~370 derived `.parquet` files, which any of the notebooks will
regenerate. Everything committed to this repository is either our own code and writing, or
**aggregate** output — coefficients, quantiles, counts, and n-gram frequencies at document
frequencies above 24,000. No individual loan text, borrower name, or other row-level record is
published.

Kiva loan data is owned by [Kiva](https://www.kiva.org/); the competition brief and dataset were
supplied by UNSW for the 2026 MA Hackathon.

## Known gaps

Carried openly from [`7_审查记录/`](7_审查记录/) (round 4) rather than papered over:

- The **joint** V / G / V×G test that RQ2 specifies is not yet written into an artifact.
- RQ4's second question — whether the attention market runs *within sector* or *platform-wide* — has no corresponding output.
- Final QA is **19/20**: the PPTX render gate needs a Node environment (see review log R-01).
- Step 09's out-of-sample check uses an SGD prediction model; it does **not** cross-validate step 07's HDFE conditional association, and is not presented as doing so.

## A note on redaction

Before publishing, absolute local paths of the form `/Users/<name>/Desktop/...` were replaced with
`<PROJECT_ROOT>` / `<HOME>` in 19 files (audit manifests, reproduction notebooks, two review notes).
Those files' hashes therefore differ from the entries in
[`MANIFEST_SHA256.txt`](5_最终交付包/MA-Hackathon-Final-2026-09-04/MANIFEST_SHA256.txt); the
unmodified submitted package is retained offline. No numeric result was touched.

## License

Code and documentation in this repository: [MIT](LICENSE).
This does **not** extend to the Kiva dataset or to the UNSW competition materials reproduced in
[`1_题目与数据/`](1_题目与数据/), which remain the property of their respective owners.
