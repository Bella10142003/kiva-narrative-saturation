# English Speaker Script · 8–10 minutes

## Slide 1 — When Every Story Sounds the Same

Good morning. Kiva borrowers are often encouraged to tell a more distinctive story. But a story is never seen in isolation. It appears beside other live requests, often using similar recurring language.

So our question is not simply, “Which stories are persuasive?” It is: when every story sounds the same, is the bottleneck competition right now, repetition from the recent past, or both?

Our answer is more selective—and more useful—than we expected. The strongest signal is what is live beside a story when that story enters the market. The older-listing measure is only a posting-age lexical proxy; we do not observe what lenders saw or remembered.

## Slide 2 — Two attention mechanisms imply two different fixes

We separate two mechanisms that can produce the same visible outcome: slower funding.

The first is active saturation. A loan enters a market containing many currently fundable alternatives, and its wording overlaps strongly with that active pool. The second is a recent-listing proxy: how much similar same-sector language was posted 35 to 65 days earlier. That proxy tests a wear-out hypothesis, but it does not observe page exit, impressions or memory.

The distinction matters operationally. If active competition dominates, Kiva should test how similar listings are timed and exposed. If recent wear-out dominates, editorial refresh becomes more relevant.

Instead of assuming one explanation, we measured both proxies and required each claim to survive scenario and robustness checks before recommending action.

## Slide 3 — 1.23 million training loans reconstruct each listing’s market

Our main training analysis contains 1,234,131 loans.

For each focal listing, we reconstruct the attention environment at posting. In the current window, volume is how many alternatives are available, overlap is the focal story’s mean lexical similarity to that active pool, and their interaction represents current saturation. We construct a posting-age proxy from listings 35 to 65 days earlier.

We compare masked text with recurring-language-removed text and test alternative time-based windows. Our primary outcome is log of one plus funding hours, with the probability of funding within 72 hours as a directly interpretable co-outcome.

Finally, we compare models out of time on the 2025 holdout. Every valid record in this extract has a raised date, so the analysis is conditional on this raised-only extract. Throughout, these are associations—not causal effects.

## Slide 4 — Current saturation is strong on log-time and 72-hour outcomes

This is our strongest diagnostic result.

On the log-one-plus-hours outcome, moving the current environment jointly from the 25th to the 75th percentile corresponds to a 124.35 percent higher conditional geometric mean of one plus funding hours. The 95 percent interval is 103.71 to 147.08 percent, a ratio of 2.24. This is not an arithmetic mean duration.

The independent co-outcome is easier to read operationally: the probability of funding within 72 hours is 14.68 percentage points lower, with a 95 percent interval from minus 17.69 to minus 11.67 points.

Both endpoints are populated in the observed training data. Even so, these are associations—not estimates of what would automatically happen if Kiva changed its interface tomorrow.

## Slide 5 — The current signal depends partly on how text is represented

Using masked use text, the current volume-by-homogeneity interaction is 0.1016, with a p-value of 0.0033. After removing recurring language, the estimate falls to 0.0523, with a p-value of 0.129.

The estimate is roughly halved and is no longer statistically distinguishable from zero in the residual specification. This does not prove that templates explain half of the effect, because we have not formally tested the difference between the two coefficients.

Description text gives another useful check: its current interaction is 0.1323 and significant, while its recent interaction is negative and not significant.

Together, these results shift the managerial focus away from telling borrowers to “write better” and toward testing platform- and partner-level processes.

## Slide 6 — The recent-listing proxy produces no detectable joint penalty

The recent-listing proxy tells a different story.

For the representative joint shift from low to high recent-listing saturation, the back-transformed log-time contrast is minus 1.43 percent. Its 95 percent interval ranges from minus 15.82 to plus 15.43 percent.

The corresponding 72-hour contrast is minus 0.51 percentage points, with an interval from minus 3.86 to plus 2.84 points.

Both intervals include zero. Because the main measure is a posting-age proxy rather than observed exposure, we do not find support for an average wear-out claim. That is not the same as proving that wear-out can never occur.

## Slide 7 — Robustness preserves the current signal, not a broad wear-out claim

There is an important nuance. The continuous recent volume-by-overlap interaction is positive in the masked-use specifications. But that coefficient tests a local conditional interaction. The joint scenario asks about the net log-time change when recent volume and overlap move together.

The current interaction remains positive in both the 14-day and 16-day posting-window checks. The recent interaction does not survive those time-based checks, and description text also does not support it.

The honest conclusion is therefore: live-market saturation is a strong but representation-sensitive diagnostic association, while the recent-listing proxy is not robust enough to support a wear-out action.

## Slide 8 — Narrative features do not improve 2025 prediction

A variable can explain a historical association without improving future prediction.

On the 2025 holdout, the narrative-enhanced model does not outperform the controls-only model on our main operational metrics.

For 35-day log MAE, where lower is better, the results are 0.9822 versus 0.9663. For the 72-hour Brier score, also lower-is-better, they are 0.1369 versus 0.1354. For AUC, where higher is better, they are 0.8921 versus 0.8987.

Log-loss improves slightly, and we acknowledge that. But one modest metric improvement does not offset the lack of improvement on MAE, Brier and AUC. We also have not estimated uncertainty for these metric differences, so we say “did not outperform,” not “significantly worsened.”

These results do not support deploying a narrative scoring engine.

## Slide 9 — The evidence supports experiments, not borrower scoring

Our recommendation is deliberately narrower.

First, when current saturation is high, Kiva could test whether staggering similar listings or diversifying their exposure improves funding outcomes. Second, because the current interaction attenuates after recurring-language removal, Kiva and its Lending Partners could test alternative approved templates without placing additional writing burdens on borrowers.

These should be small randomized pilots, not immediate platform-wide changes. Outcomes should include time to funding and 72-hour funding probability, alongside guardrails for total funding, fairness across groups and borrower workload.

The saturation measures identify a market condition worth testing. They do not measure borrower quality and should not be used to rank or penalize borrowers.

## Slide 10 — Make room for authentic stories—then test before scaling

Our analysis leaves three conclusions.

First, the strongest practical signal is current attention pressure: many similar loans fundraising at the same time.

Second, the recent-listing proxy does not provide robust support for broad wear-out.

Third, narrative features do not add reliable 2025 predictive value on the main operational metrics.

So our recommendation is not to build a borrower score. It is to change the market around the story, test that change prospectively, and scale only what improves funding without shifting the burden of platform competition onto borrowers.

## Optional 20-second closing

Our model is not ready to score borrowers—and that is exactly why our recommendation is safer: change the market around the story, test it prospectively, and only scale what improves funding without shifting the burden onto borrowers.
