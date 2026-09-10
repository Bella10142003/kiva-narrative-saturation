# Methods and Validation Appendix

## Claim boundary

All reported effects are conditional associations. No coefficient is presented as a causal intervention effect, borrower-quality measure, or production-ready score.

## Cohorts

- Official extract: 1,453,846 rows.
- Valid nonnegative funding duration: 1,453,840 rows.
- After the 65-day wash-in: 1,434,195. The extract begins 2016-01-01, so focal loans posted
  in the first 65 days have no complete [35,65)-day lag window; they are excluded rather than
  scored against a partial pool. The exclusion depends only on the posting date, and the excluded
  and retained 2016 loans have near-identical duration distributions.
- Main HDFE training sample: 1,234,131 loans posted in 2016–2024.
- Untouched main holdout: 133,409 loans posted in 2025.
- 35-day holdout slice: 123,489.

## Outcomes

- Primary: `log(1 + funding_hours)`.
- A scenario back-transform, `exp(delta) - 1`, is the percent change in the conditional geometric mean of `1 + funding_hours`; it is not an arithmetic mean duration.
- Co-outcome: funded within 72 hours when at least 72 calendar hours of follow-up are observable.
  The eligibility window is not a separate choice: the label is undefined without 72 hours of
  observation. It removes no training loan, since 2016-2024 sits far inside the extract boundary.
- Why 72 hours: it is the nearest whole day to the training median of
  69.25 hours. Binarising at the median gives
  50.57% positives and Bernoulli variance
  0.2500, the theoretical maximum, so the co-outcome carries
  maximal power; the best alternative among 1, 7 and 14 days reaches only 0.2347.
  Three days is also the unit Kiva triage already uses. Candidates: `outputs/co_outcome_threshold_choice.csv`.
- The binary co-outcome is immune to the extreme upper tail that `log(1 + funding_hours)` is
  sensitive to; agreement between the two is a specification check, and all six pool coefficients
  reverse sign across them as they must.
- No AFT model: the extract has no missing `raisedDate`, so true right censoring cannot be identified.

## Text and pools

- Masked hashed word (1,2)-gram TF–IDF, 2^17 features, train-only smooth IDF.
- Recurring-language threshold: exact 5-gram in at least 659
  train documents and at least 3 countries;
  409 phrases qualified.
- Current active same-sector pool; 14-day and P75-calibrated 16-day posting pools as precommitted checks.
- Recent [35,65)-day posting-age pool with seven-day half-life; it is a lexical-environment proxy, not observed exposure or page exit. Completed-only lag is a sensitivity.
- Main raw pool threshold n>=10; lagged Kish effective n>=10; sensitivities n>=5 and n>=20.

## Model

`log_funding_hours ~ C + H + C×H + V + G + V×G + controls | country + activity + week`

Controls: log loan amount, log borrower count, log repayment term, log platform seven-day posting volume. Primary covariance: country/week two-way CRV1.

## Validation inventory

- Full pickle opcode audit: no dangerous opcodes; restricted primitive deserialization.
- Pool identity: 600 exact comparisons; max raw error 2.909e-14; max residual error 2.509e-14.
- Description identity: 100 exact comparisons; max error 1.721e-15.
- Joint support: minimum 4,716 loans inside an endpoint neighbourhood.
- Alternative windows, pool thresholds, completed-only lag, one-way/two-way clustering, raw/residual text and description sensitivity.
- 2025 out-of-time validation against a controls-only baseline. Both outcomes are scored on a
  full-follow-up slice as well as on all observed loans, so neither carries an unchecked
  truncation exposure.

## Right truncation at the 2025 boundary

The extract ends when the last loan finished fundraising, and every row carries a
`raisedDate`. A loan still raising at that instant is therefore absent rather than
censored: it appears only if `funding_hours <= T - t`, so the admissible window narrows
to zero as the posting time approaches the boundary and only the fastest survive. The
gradient in `outputs/late_2025_followup_audit.csv` is the signature — median duration
falls from 65.4h with
full follow-up, to 37.1h
in the 72h-to-35d band, to 5.7h
over the final 72 hours. This is truncation, not a year-end demand effect: a demand shift
moves the distribution but cannot pin the daily maximum observed duration to the remaining
window, which is what the data show.

Handling differs by outcome because the defect differs. For the binary co-outcome the
label is undefined, not biased, so the
494 loans with under 72 hours of
follow-up are ineligible. For the continuous outcome the recorded duration is correct and
nothing is deleted; instead `2025_all_observed` and `2025_at_least_35d_followup` are
reported side by side so the reader can see whether any conclusion depends on the choice.
The same 35-day constant serves both the lag pool and this slice, and for the same reason:
it is the training P95 of 826.89 hours rounded up, so a focal loan
had a 95% chance to resolve. Because 35 days is 840 hours and exceeds that P95, a loan
posted exactly at the boundary loses under 5% of its conditional mass, and the loss falls
towards zero for earlier postings. Training years 2016-2024 sit at least one year inside
the boundary and are unaffected, so the main estimates carry no truncation exposure.

A second-order exposure is disclosed for completeness: pool features for late-2025 focal
loans are themselves built from the truncated population, since a loan that was live and
competing for attention but resolved after the extract is absent from the pool, which
understates the measured active pool. Kiva posts in batches, so the net distortion cannot
be given a clean point estimate. The `>=35d` slice removes this exposure as well, because
its focal loans look back over windows that close well inside the boundary.

## Known limitations

Missing exposure, ranking, click, promotion, image-quality and partner identifiers; active-pool endogeneity; the recent pool is a posting-age proxy rather than observed wear-out; lexical rather than semantic similarity; raised-only extract; temporal drift; country heterogeneity limited to the top 15 training-volume countries and sector heterogeneity to 14 estimable groups; subgroup cross-covariance not estimated in the Q screen.
