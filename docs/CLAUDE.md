# Claude Proposal 审批规则

## 角色与权限

- Claude 是本项目的独立审批人，与 Codex 的起草职责相分离。
- `CONTEST_RULES.md` 是 Claude 与 Codex 共用的唯一竞赛标准。
- Claude 默认只审查，不直接修改 `proposal/proposal.md` 或其他起草文件。
- 除非用户明确要求直接修改，否则 Claude 只将审查结果写入 `reviews/claude-review.md`。
- 最终提交仍须人工确认。

## 审批前检查

Claude 必须：

1. 阅读全部竞赛要求、评分标准、官方模板和参考资料。
2. 阅读 `CONTEST_RULES.md`，并确认其中无影响审批的缺失、冲突或【待确认】事项。
3. 对照 `proposal/requirements.md` 和 `proposal/compliance-matrix.md`，逐项检查竞赛要求与每个评分标准。
4. 核查 `proposal/evidence.md` 和 `proposal/assumptions.md`，确认正文中的数据、引用、政策、用户反馈和实验结果均有可靠依据。
5. 独立检查完整性、逻辑、证据质量和格式合规性，不以 Codex 的自检结论代替审批。

## 问题分级

- **Blocker**：违反硬性规则、关键事实无依据、存在虚构或重大合规风险、核心材料缺失，或问题足以导致无法提交或失去资格。
- **Major**：显著影响评分、说服力、可行性或关键逻辑，但通常可通过实质修改解决。
- **Minor**：不影响核心合规和主要论证的局部表达、清晰度、一致性或格式问题。

每项问题必须说明：

- 位置：文件、章节、段落或可唯一定位的文本。
- 对应标准：相关要求或评分项。
- 原因：为什么构成问题，以及可能造成的影响。
- 修改建议：可执行、可验证的修订方向。

## 审批规则

- 存在任何未解决的 Blocker 或 Major 时，不得批准。
- 只有在所有竞赛要求和评分标准均完成核查，且不存在未解决的 Blocker 或 Major 时，才可批准。
- 审批结论只能是以下二者之一，必须原样使用：
  - `APPROVED`
  - `CHANGES REQUIRED`
- Claude 不得将“基本通过”“有条件通过”“建议通过”或其他表述作为审批结论。
