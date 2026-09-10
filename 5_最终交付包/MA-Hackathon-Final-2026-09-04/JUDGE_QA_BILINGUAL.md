# Judge Q&A · Bilingual Answer Bank

## 1. Are you claiming that current saturation causes slower funding?

**EN:** No. We estimate conditional associations. Controls and fixed effects reduce some confounding, but unobserved exposure, ranking and partner processes may remain. Causal effects require a randomized platform intervention.

**中：** 不是。我们估计的是条件相关性。Controls 和 fixed effects 能减少部分混杂，但仍可能存在未观察到的曝光、排序和合作伙伴流程。因果效应需要平台随机实验。

## 2. What exactly does the 124.35 percent result mean?

**EN:** The outcome is `log(1 + funding hours)`. The joint contrast implies a 124.35% higher conditional geometric mean of `1 + hours`, a ratio of 2.24. It is not an arithmetic mean duration, not 124 additional hours, and not a causal intervention effect.

**中：** Outcome 是 `log(1 + funding hours)`。该联合对比表示 `1 + hours` 条件几何均值增加 124.35%，ratio 为 2.24；它不是算术平均时长、不是增加 124 小时，也不是因果效应。

## 3. Are the scenario endpoints extrapolated?

**EN:** We checked local empirical support. In a narrow ±0.10-IQR box around each current and recent P25/P75 endpoint, the smallest neighbourhood still contains 4,716 training loans. That reduces empty-support concern, but it does not establish exchangeability or causality.

**中：** 我们做了局部支持检查。在每个 current/recent P25/P75 端点周围 ±0.10 IQR 的窄邻域里，最少仍有 4,716 笔训练贷款。它降低了空洞外推担忧，但不建立可交换性或因果性。

## 4. Is the current result robust?

**EN:** It is robust to the 14-day and 16-day posting windows and appears again with description text. However, it is sensitive to recurring-language removal: the masked-use interaction is significant, while the residual estimate is smaller and not significant. We do not call it universally robust.

**中：** 它对 14 天、16 天窗口稳健，description 也再次出现；但对 recurring-language removal 敏感。因此我们不会说它在所有规格中都稳健。

## 5. Does boilerplate explain the current effect?

**EN:** We cannot make that causal decomposition. The estimate falls from 0.1016 to 0.0523 and loses conventional significance, which is consistent with recurring language contributing. Proving how much it explains requires a formal coefficient-difference test or an experiment.

**中：** 不能做因果分解。系数从 `.1016` 降至 `.0523` 并失去常规显著性，这与模板语言可能贡献部分信号一致；要证明贡献多少，需要正式差异检验或实验。

## 6. Your raw recent interaction is significant. Why reject wear-out?

**EN:** We do not reject every possible wear-out pattern. Our main recent measure is only a 35–65-day posting-age lexical proxy, not observed exposure or page exit. Its joint log-time back-transform is −1.43% and its 72-hour contrast is −0.51pp; both intervals cross zero, and the interaction also fails the time-based and description checks.

**中：** 我们没有否定所有 wear-out。主 recent 指标只是 35–65 天 posting-age lexical proxy，不是已观察的 exposure 或 page exit；联合 log-time 与 72 小时结果区间都跨零，time-based 与 description 检验也不支持更强结论。

## 7. How can VG be significant while the joint scenario is near zero?

**EN:** They are different estimands. VG tests a local conditional interaction. The joint scenario combines the V and G main effects with their interaction when both move from low to high. A local interaction can be significant while the net log-time contrast is close to zero.

**中：** 两者是不同 estimand。VG 检验局部条件交互；联合情景同时包含 V、G 主效应和 interaction。局部交互显著，不代表净实际变化显著。

## 8. Are you saying recent wear-out does not exist at all?

**EN:** No. The proxy contains a localized interaction signal, but it does not observe exposure or memory; the joint contrast is uncertain and robustness checks do not support a broad claim. Our conclusion is “not supported for action,” not “impossible.”

**中：** 不是。数据中有局部信号，但代表性实际效应不确定且稳健性不足。结论是“尚不足以采取行动”，不是“不可能存在”。

## 9. Why do the 14-day and 16-day checks matter?

**EN:** They test whether the conclusion depends on an outcome-dependent active pool or one chosen window. Current CH remains positive and significant under both windows, while lagged VG does not. That increases confidence in the current diagnostic signal.

**中：** 它们检验结论是否依赖 outcome-dependent active pool 或某一个窗口。Current CH 在两个窗口保持，lagged VG 不保持。

## 10. Did narrative features improve prediction in 2025?

**EN:** Not on the main operational metrics. The narrative model has higher MAE and Brier and lower AUC than controls-only. Log-loss improves slightly, but the overall comparison does not justify claiming incremental predictive value.

**中：** 在主要运营指标上没有。Narrative model 的 MAE 和 Brier 更高、AUC 更低；log-loss 略好，但整体不足以声称增量预测价值。

## 11. Are the holdout differences statistically significant?

**EN:** We have not presented paired uncertainty for the metric differences, so we do not claim statistically significant degradation. Our precise claim is that the narrative model did not outperform controls-only on MAE, Brier or AUC.

**中：** 目前没有 metric differences 的 paired uncertainty，因此不声称“显著变差”。准确表述是没有超过 controls-only baseline。

## 12. Why can log-loss improve while other metrics worsen?

**EN:** Metrics reward different properties. Log-loss is highly sensitive to assigned probabilities, while Brier and AUC capture different aspects of calibration and discrimination. One slight improvement does not establish overall operational superiority.

**中：** 不同指标奖励不同性质。Log-loss 对概率分配很敏感；Brier 和 AUC 反映其他校准与区分属性。一个指标略好不能证明整体优越。

## 13. Is the Narrative Attention Engine ready to deploy?

**EN:** No. The 2025 holdout does not show consistent incremental predictive value, and calibration gaps remain. The measures can generate experiments; they must not rank, approve or penalize borrowers.

**中：** 不可以。2025 holdout 没有一致增量价值，校准也有缺口。它只能生成实验，不可用于排序、批准或惩罚 borrower。

## 14. What should Kiva test first?

**EN:** A small randomized pilot in high-current-saturation conditions: compare normal exposure with staggered or diversified exposure. Separately test partner-approved template alternatives. Outcomes should include funding time and 72-hour funding, with fairness, total-funding and borrower-workload guardrails.

**中：** 在 high-current-saturation 条件下做小规模随机试验，比较常规曝光与错峰/多样化曝光；另测 partner-approved template alternatives，并加入公平性、总融资量和 borrower workload guardrails。

## 15. What is the contribution if the predictive model does not win?

**EN:** The contribution is disciplined mechanism separation. We identify a strong but representation-sensitive live-market association, show that the recent-listing proxy does not support broad wear-out, and prevent an unsupported scoring deployment. That converts analytics into a safer, testable platform decision.

**中：** 贡献是严谨地区分机制：识别强 live-market association，证明 broad wear-out 不稳健，并阻止缺乏依据的评分部署，把分析转化为更安全、可检验的平台决策。

## 16. Why use `use` rather than full description?

**EN:** `use` is closer to scan-stage content and has high coverage. We precommitted it as primary before outcome modeling and then ran a full description sensitivity. Description preserves the current association but does not support the recent-listing interaction, so the central conclusion is not an artifact of the short field alone.

**中：** `use` 更接近 scan-stage 且覆盖高，因此在看 outcome 之前冻结为主字段；随后完成 description 灵敏度。Description 保持 current、不支持 recent，因此核心结论不只来自短字段。

## 17. Why not run an AFT survival model?

**EN:** Every valid record in this extract has a `raisedDate`, including refunded statuses. There is no observable right-censored population to model. An AFT model would create the appearance of survival rigor without a censoring state supported by the data.

**中：** 每条有效记录都有 `raisedDate`，数据里没有可识别的 right-censored population。此时做 AFT 会制造形式上的生存分析，却没有数据支持的删失状态。

## 18. Are the recurring phrases really partner templates?

**EN:** We call them recurring language, not verified partner templates. The dataset has no partner ID, so recurrence across at least three countries is only a conservative source proxy. We do not attribute any phrase to a named institution.

**中：** 我们称其为 recurring language，不称为已验证 partner template。数据没有 partner ID，跨至少三个国家只是保守来源代理；不会归因具体机构。

## 19. Could active-pool endogeneity explain the result?

**EN:** It may contribute: slow loans stay visible longer and enter more later pools. That is why we precommitted posting-window checks independent of later funding duration. Current CH remains positive in both 14-day and 16-day windows, but unobserved demand and exposure confounding can still remain.

**中：** 可能。慢贷款停留更久，会进入更多后来者的 active pool。因此我们用了不依赖后来融资时长的 14/16 天 posting checks；current CH 仍为正，但未观察需求和曝光混杂仍可能存在。

## 20. Will an exposure experiment simply move funding away from other borrowers?

**EN:** That is the central guardrail risk. The pilot must measure total funding and distributional outcomes, not only treated-loan speed. We would scale only if gains do not come from harming other vulnerable borrowers.

**中：** 这是最重要的 guardrail 风险。Pilot 必须同时测总融资量和分配结果，而不只看 treatment loan 速度；只有收益不是通过伤害其他弱势 borrower 获得时才可扩大。
