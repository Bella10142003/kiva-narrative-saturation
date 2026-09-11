# Running the proposal against simulated data: which components actually earn their place

> English version. The Chinese original is [`模拟验证报告.md`](模拟验证报告.md); every figure and verdict is
> carried over unchanged. Reproduce any number here with [`../run_demo.sh`](../run_demo.sh).

**Conclusion first.** The whole pipeline runs on 20,000 simulated loans in **38 seconds** — compute is not the
bottleneck. The real problem is elsewhere. Of the 14 methodology components in proposal v4, measurement shows
**3 genuinely earn their place, 4 are permanent no-ops, 5 are written in a way that misleads, and 2 actively
make the estimates worse.** Cutting the no-ops and the misleading parts roughly halves the analysis workload
without losing a single defensible conclusion.

---

## 1 · What this simulated data is

20,000 loans spanning 2016-01-01 to 2025-12-31, with a schema identical to the official 100-row sample (27
fields, same names, same types). Calibrated to the real sample's distributions: median fundraising duration
62.3 hours (real sample 61.7), maximum 839.9 hours (real 840.0), median loan amount 350 (real 362.5). 8.9 % go
unfunded, and for 3.0 % even the termination date cannot be verified.

**Six things are planted deliberately**, each one turning a sentence of the proposal into something falsifiable:

| What is planted | Which proposal claim it tests |
|---|---|
| Known true coefficients β₁…β₆ (standardised: β₃ = 0.117, β₆ = 0.037) | Can the 2×3 measurement matrix separate the two channels? |
| A sector-week shock `u[s,w]`, unobservable to the analyst and not absorbed by week FE | "The active pool is contaminated by outcomes, so we need a mirror pool" |
| 72 lending partners whose template intensity and funding speed are both driven by partner size | "Having no partner identifier is residual confounding we cannot fix" |
| Template share rising 0.25 → 0.70 over the years, pool size 3.6 → 12.5, homogeneity 0.105 → 0.211 | The two directional predictions in RQ3 |
| 8.9 % unfunded plus 3.0 % with unverifiable termination dates | The censoring model and the "fall back to the mirror pool" branch |
| The true driver lives in **`use`**, not in `description` | "The difficulty arises at the scanning stage" |

The active pool is determined by the *realised* endpoints of earlier loans, simulated loan by loan in time
order — so the endogeneity grows out of the process rather than being sprinkled on afterwards. Measured:
`corr(shock, active pool size) = +0.132` against `corr(shock, mirror pool size) = +0.016`.

> **One scale difference to keep in mind.** Spread 20,000 loans over 10 years and 11 sectors and the sector
> active pool averages just 9 loans; on the real 1.45M it is roughly 70× larger. Every conclusion below that
> concerns **precision** is therefore conservative — what is detectable here can only be easier on the real
> data, and only what is *undetectable* here needs the power extrapolation.

---

## 2 · Three components that genuinely earn their place

### 2.1 The dual-pool mirror — the best value in the entire design

The crowding coefficient from the active pool (same-sector loans still live at listing time) is badly
overstated:

| Specification | Estimate of C | Truth |
|---|---|---|
| Active pool | **0.444** | 0.138 |
| Active pool, controlling for the true shock (cheating benchmark) | 0.089 | 0.138 |
| **Mirror pool (posted in the prior 14 days, regardless of later status)** | **0.107** | 0.138 |

The active pool overstates C by 3.2×. The cheating benchmark proves the bias really does come from that
unobservable sector-week shock. The mirror pool, **without knowing the shock exists at all**, pulls the
estimate back to nearly unbiased.

**Verdict: keep, and promote to the main specification.** The proposal currently has it the other way around
— active pool primary, mirror pool secondary — and the two should be swapped. The cost is attenuated
homogeneity: H falls from a true 0.170 to 0.054, and C×H from 0.117 to 0.042, because the mirror pool is a
noisy proxy for the real active pool — textbook attenuation bias. This is an explicit trade:
**accept coefficient attenuation to remove endogeneity bias.** The proposal should say so plainly instead of
hedging with "we only interpret results consistent in both sign and magnitude".

### 2.2 Comparing `use` against `description` — useful, but only once

| Measurement | Correlation with truth |
|---|---|
| Active-pool homogeneity H (from `use`) | **0.999** |
| Active-pool homogeneity H (from `description`) | 0.538 |

In this simulation the true driver was placed in `use`, so this number is an echo of an assumption, not a
finding. But it does verify something worth knowing: **the two fields measure very different things** —
they correlate only 0.54 — so *which field you measure on* is a decision that changes the conclusion, and it
deserves to be stated in the proposal.

**Verdict: simplify.** Make `use` the primary measurement and run `description` once as a consistency check,
rather than carrying two parallel model suites.

### 2.3 The Day 1 audit — but only four items changed anything

Running it, the audit items that actually **triggered a decision** were:

- `whySpecial` has only 38 distinct values across 20,000 rows (0.19 %) → dropped under the proposal's own rule. The rule worked.
- Longest duration among funded loans is 839.9 hours → **L frozen at 35 days**
- 3.0 % of loans have unverifiable termination dates → triggers the fallback assumption
- Pool size distribution (mean 9.0, 39 % reaching 10 loans) → directly determines how the threshold is set

Every other audit item — duplicate IDs, language, missingness, 0.045 % duplicate text — passed and changed no
decision at all.

**Verdict: keep, narrowed to those four.**

---

## 3 · Four components that are permanent no-ops

### 3.1 "Report the share of the lagged pool still live, then re-estimate excluding them"

Measured: **0.0 %**. Because L is frozen at the fundraising ceiling (35 days) and every loan leaves the page by
day 35 at the latest, **overlap is zero by construction whenever L takes the ceiling**. This check is
identically zero on the real data too; writing it up is pure word count.

**Verdict: delete.** Replace with one sentence — "L is set to the fundraising ceiling, so the lagged pool and
the active pool do not overlap by construction" — which also closes the open question raised in section 5,
item 2 of the handover brief.

### 3.2 Reconstructing the platform-level pool

The platform-level crowding coefficient is **−0.49** against a truth of +0.138: the sign is inverted. The
reason is direct — platform-wide listing volume is nearly constant within a week, week fixed effects eat all
of its variation, and what remains is noise.

**Verdict: delete.** The RQ4 question of whether the attention market runs at sector or platform level can
stay as discussion, but this regression cannot answer it.

### 3.3 Restricted cubic splines

The truth is linear, so the spline **ought** to find nothing — and it finds nothing (two terms at t = +0.90
and −1.58, one of them numerically degenerate with a standard error computed as 0). The problem: whether it
*would* detect a genuinely non-linear truth is a question this simulation does not answer, while the fact that
it introduces numerical instability under a linear truth is something it does establish.

**Verdict: delete.** Replace with a quantile-binned plot of H, which the Day 6–7 presentation tooling has to
draw anyway. Zero cost, and easier to explain than a spline.

### 3.4 The 3-day / 14-day half-life sensitivity

Under a 7-day half-life, the weight at day 44 is only 5.7 % of the weight at day 15 — the half-life is doing
the work, not the hard cutoff. Swapping the sensitivity check to 3 or 14 days changes the rank correlation of
the lagged-pool measurement very little, and the estimates do not move.

**Verdict: remove from the main text** (one sentence in the appendix). Spend the words on defining L properly
instead.

---

## 4 · Five components written in a way that misleads

### 4.1 The pool size ≥ 10 threshold — it kills β₃ instead of protecting it

| Threshold | N | C×H estimate | Truth |
|---|---|---|---|
| No threshold | 16,818 | **0.077** (t = 4.3) | 0.117 |
| ≥ 5 | 11,132 | −0.035 (t = −0.8) | 0.117 |
| ≥ 10 | 7,018 | **−0.002** (t = 0.0) | 0.117 |

The mechanism is not subtle: **variation in C is exactly what identifies C×H**, and a pool-size threshold cuts
away precisely the half of the sample where C is small, leaving the interaction with no leverage. The
proposal's stated reason — "a mean computed from a pool of N = 2 is pure noise" — is not wrong, but what it
protects is the measurement quality of H, and what it costs is the identification of C. The latter is more
expensive.

**Verdict: rewrite.** Main specification takes no threshold (requiring only a non-empty pool), reports the pool
size distribution, and demotes ≥ 10 to a robustness check. Note: on the real data the pools are 70× larger and
the threshold would drop almost no rows — **so strictly speaking this finding is an artefact of the small
sample here** — but the mechanism it exposes (a threshold trading away identification) still holds, which is
why the proposal should move to "report the distribution, set no hard threshold".

### 4.2 The placebo's "one-third rule" — unevaluable on noise

Forward-window V×G = 0.0406, backward V×G = 0.0411, a **ratio of 0.99**, far above the one-third the proposal
demands. By the proposal's own criterion, this design **fails its placebo test.**

But the true forward effect is **0**. Neither coefficient is significant (t = 0.58 and 0.80) — they are both
noise, and the ratio of two noise terms of course says nothing. **A rule of the form "the forward coefficient
must be below one third of the backward coefficient" is meaningless when the backward coefficient is not
itself significant, and it fails a perfectly correct design.**

**Verdict: change the criterion.** Replace it with two: (a) the forward coefficient's confidence interval must
cover 0; and (b) a test of forward equals backward must reject — **executed only when the backward coefficient
is itself significant.** This is a genuine logical hole, and leaving it in would draw a question at the defence
that cannot be answered.

### 4.3 Raw / residual template decomposition — it barely moves anything

| Specification | H | C×H |
|---|---|---|
| `description`, raw | 0.043 | 0.053 |
| `description`, template-residualised | 0.050 | 0.023 |
| **With the true partner fixed effects added (cheating benchmark)** | 0.102 → 0.102 | 0.077 → **0.078** |

Stripping templates barely moves the estimates. More telling is the cheating benchmark: putting the **true**
partner fixed effects in moves C×H from 0.077 to 0.078 — **partner confounding is simply not a material source
of bias under this data-generating process.** In other words, the whole paragraph the proposal spends defending
"raw/residual decomposition as a substitute for partner FE" solves a problem that (at least here) does not
exist.

**Verdict: demote substantially.** Keep `boilerplate_share` as one covariate — one line of code — and reduce
the entire decomposition to a single robustness sentence. Saves roughly 60 words.

⚠️ This is the finding in this exercise most in need of discounting: the conclusion depends on the size of the
partner effect *I* specified. On the real Kiva, funding-speed differences across lending partners may be far
larger. **The safe statement is: do not defend the template decomposition as an identification strategy; treat
it as a descriptive robustness check.**

### 4.4 RQ4 by sector — only the top three sectors are estimable

| Sector | N | C×H (se) |
|---|---|---|
| Agriculture | 4,174 | −0.042 (0.162) |
| Food | 1,735 | −0.066 (0.143) |
| Retail | 1,055 | 0.170 (0.407) |
| Services | 20 | −0.197 (numerically degenerate) |
| Housing | 6 | 0.259 (numerically degenerate) |
| Education | 18 | −0.232 (numerically degenerate) |

In the truth, **every sector has an identical coefficient** — there is no real heterogeneity — yet the
estimates swing from −0.23 to +0.26. Telling a story off those point estimates would produce an entirely
fictional account of sector differences. This is exactly what the proposal's equivalence rule exists to
prevent, and that rule should stay.

**Verdict: narrow to the top three sectors plus one joint interaction test plus equivalence intervals.** The
remaining sectors cannot even absorb their fixed effects, which makes FDR correction moot.

### 4.5 The censored (AFT) model — worse than simply using the funded sample

| Parameter | Truth | OLS (funded only) | AFT (right-censored) |
|---|---|---|---|
| C | 0.138 | 0.444 | **0.695** |
| C×H | 0.117 | −0.002 | 0.083 |
| V×G | 0.037 | 0.041 | **−0.089** |

AFT drifts further from the truth on C and flips sign outright on V×G. Censoring affects 8.9 % of the sample;
model specification risk affects all of it.

**Verdict: demote to the appendix.** Run the main analysis on the funded sample and report, in the main text,
the unfunded share and its correlation with each measurement — a more honest and cheaper treatment.

---

## 5 · RQ3 is the tightest on power and must be rewritten

This is the most important item. RQ3 is written in the proposal as two **directional predictions** — active
saturation strengthening year over year, recent saturation strengthening faster still — tested through a
"saturation × year" interaction coefficient. Measured:

| | Truth | Estimate on 20k | Power extrapolation to 1.45M |
|---|---|---|---|
| C×H × year | +0.0064/yr | +0.0020 (se 0.0051) | se ≈ 0.0027, **t ≈ 2.4** |
| V×G × year | +0.0048/yr | **−0.0039** (sign flipped) | se ≈ 0.0026, **t ≈ 1.9** |

Splitting the sample does not rescue it either: V×G goes 0.058 → 0.018 between 2016–20 and 2021–25, **the
opposite direction from the truth.**

The power extrapolation corrects for intra-cluster correlation — rows per week rise from 34 to 2,812,
ρ ≈ 0.010, and the design effect rises from 1.16× to about 5.5×. A naive √N extrapolation would overstate
power by more than threefold. After correction:

- **β₃ (C×H): t ≈ 13.7** → comfortably detectable on the real data
- **β₆ (V×G): t ≈ 4.6** → detectable
- **The two year interactions: t ≈ 2.4 and 1.9** → right on the line

**Verdict: keep RQ3 — the brief requires an evolution perspective — but downgrade the quantitative claim.**
Specifically: rewrite the two directional predictions as "a descriptive account of year-by-year marginal
effects and their confidence intervals", explicitly labelled exploratory. The reason belongs in the proposal:
a year interaction slices the main effect ten ways, so its power is naturally a fifth of the main test's.

This rewrite has a side benefit — the handover brief's worry that "β₆ is conservative by construction, so a
null is not evidence that wear-out does not exist" folds in here and gets said once, clearly.

---

## 6 · Feasibility: compute is not the problem

| Step | Time on 20,000 rows |
|---|---|
| Day 1 audit | 0.2 s |
| Text cleaning and masking | 0.4 s |
| TF-IDF vectorisation (`use` + `description`) | 1.7 s |
| Template phrase identification | 0.6 s |
| Active pool (rolling sparse sums) | 3.2 s |
| Lagged pool (decay weighted) | 4.6 s |
| Mirror pool | 4.7 s |
| Forward placebo pool | 4.6 s |
| All 11 regressions (two-way clustered SE) | 2.2 s |
| **Whole pipeline** | **38 s** |

Extrapolating to 1.45M: pool construction is dense vector addition and subtraction at O(vocabulary size) per
loan, and the vocabulary grows from 1,376 (`use`) to roughly 30–50k, so **the dominant term is vocabulary ×
rows**. A rough estimate is 25–40 minutes per pool construction and 2–3 hours for one full pass. **Comfortably
inside a week, provided you do not build four pools** — which is the second reason to cut the platform-level
pool and the surplus robustness checks.

The real bottleneck is memory, not CPU: the TF-IDF sparse matrix for 1.45M descriptions is roughly 3–6 GB, plus
one dense pool vector per sector. Recommendation: run all main analysis on `use`, whose vocabulary is an order
of magnitude smaller, and run `description` once as a comparison.

---

## 7 · Verdicts at a glance

| # | Component | Verdict | Reason (measured) |
|---|---|---|---|
| 1 | Day 1 audit | **Narrow to 4 items** | Only 4 items changed a downstream decision |
| 2 | L set from data and frozen | **Keep** | One line of code; decides whether RQ2 stands |
| 3 | Lagged pool "still-live share + re-estimate" | **Delete** | Measured identically 0.0 %; zero by construction |
| 4 | 7-day half-life + 3/14-day sensitivity | **Move to appendix** | Estimates do not move |
| 5 | Pool size ≥ 10 threshold | **No threshold + report distribution** | The threshold drives β₃ from t = 4.3 to t = 0.0 |
| 6 | Dual-pool mirror | **Keep and promote to main spec** | Bias in C drops from 3.2× to near zero |
| 7 | `use` and `description` as parallel primaries | **`use` primary, `description` one comparison** | They correlate only 0.54; worth comparing, not worth doubling |
| 8 | Raw/residual template decomposition | **Demote to one covariate + one sentence** | Adding true partner FE barely moves the coefficient |
| 9 | Restricted cubic splines | **Delete** | Numerically degenerate; use a quantile-binned plot |
| 10 | Platform-level pool reconstruction | **Delete** | Collinear with week FE; sign inverts |
| 11 | Forward placebo test | **Keep** | The test itself is meaningful |
| 12 | Placebo "one-third rule" | **Change the criterion** | It fails a correct design |
| 13 | Censored AFT model | **Demote to appendix** | Further from the truth than OLS |
| 14 | RQ4 by sector + FDR | **Top 3 sectors + joint test** | Remaining sectors lack sample; estimates swing across ±0.25 |
| 15 | Equivalence rule (subgroups only) | **Keep** | Precisely what stops noise being told as sector difference |
| 16 | RQ3's two directional predictions | **Downgrade to descriptive evolution** | Power at t ≈ 2, and the sign already flipped in simulation |

---

## 8 · What this simulation cannot answer

Drawing the boundary honestly:

1. **Wherever the truth is something I set, the conclusion is an echo of an assumption.** "`use` is closer to
   the truth than `description`", "partner confounding is not a source of bias", "the effect is this large" —
   all three were specified at the generating end; none is a finding. Their value is narrower: **given those
   settings, can this estimation procedure recover them?**
2. **Pools are 1/70 the size of the real ones.** Every conclusion about thresholds and small-subgroup precision
   is conservative.
3. **Non-linearity is untested.** The truth is linear, so "the spline found nothing" does not mean "splines are
   useless on the real data". It only shows the spline is numerically unstable inside this pipeline.
4. **The text is template concatenation, not real borrower narrative.** Absolute cosine similarity levels do
   not extrapolate; only relative conclusions — which measurement recovered which truth — do.
5. **The power extrapolation depends on the effect sizes I set.** If the real effects are smaller, 1.45M rows
   may still not suffice — but there is now a framework you can re-run with different parameters (edit the
   `TRUE` dictionary in `generate_kiva_sim.py`).

---

## 9 · Reproducing this

From the repository root, [`run_demo.sh`](../run_demo.sh) runs the first three steps for you. Or, by hand:

```bash
python3 generate_kiva_sim.py     # generate the data (30 s) — CFG['N'] changes scale, TRUE changes effect sizes
python3 analysis_pipeline.py     # play the analyst: read only the delivered data, run Day 1–Day 5 (38 s)
python3 compare_to_truth.py      # score against the answer key
python3 extra_specs.py           # marginal contribution of each component + power extrapolation
```

> Library versions shift the numbers slightly. The figures quoted above are the ones recorded when the
> exercise was run; a fresh run reproduces the conclusions, not every digit.
