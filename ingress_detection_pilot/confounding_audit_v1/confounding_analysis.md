# 混杂因素与可识别性

主结论和全部数值见diagnostic_report.md。本文件区分“领域之外存在分数关联”与“长度校准提供独立检测价值”。

| 因素 | 已控制/审计 | 主要局限 |
| --- | --- | --- |
| Domain | Domain Max独立阈值；Domain+Length仅取本域近邻；逐域ROC/PR | 域内内容与长度仍未平衡 |
| Token length | 在域内及精确Chunk数组内做秩关联、阻塞置换 | 未打乱内容；不作因果或贡献百分比分解 |
| Chunk count | 旧L与新D+L均固定k=28 | Chunk数由Token数确定，域内近邻少，尾概率有并列 |
| Position | single/first/interior/tail分开；每源一个首尾差 | 全局位置不直接输入；内容与特殊token格式和角色共线 |
| Content | 准确token hash；预设指令词及数字/标点描述 | 无语义真值，不能用词表缺失证明内容无影响 |
| Boundary format | 检查起始/结束特殊token | 没有格式配对干预，本轮不更改分块或新评分 |
| Calibration allocation | 原G/L精确复现，新D/D+L仅用原良性cal | 相同预算不保证同一实际FPR；并列与有限样本影响工作点 |
| Model label | 作者Space+独立controls；不改历史映射 | 预期语义已确认，训练实现仍未完整恢复；控制集不代表总体 |

DeBERTa的Domain Max覆盖L相对G新增16次检出的100%，但其历史FPR为11.25%而L为10%，所以100%是样本集合覆盖，不是“领域因果解释100%”或公平固定FPR优越性。D+L相对D在每域的排序和AP不增进一步削弱长度模块的依据。
DistilBERT的D仅覆盖L新增31次检出的18次（58.1%），不能宣称领域解释了该模型的全部收益。D+L Resume工作点及Token关联是未解决的局部信号，应进入新数据验证设计而非直接开发。
Prompt Guard的Resume单Chunk组内也有强Token关联，因此“高分完全由尾块造成”的说法不成立；但尾块首尾差依然显著。两种现象可以共存，缺少干预时不能分配贡献。

绝对文档位置没有进入局部模型。2900块里，相同输入token的重复组得分完全一致，但没有跨position_role的相同token组，无法从自然重复构成位置机制对照。

当前可得结论：DeBERTa长度条件化主要表现为领域代理；Token关联在其他模型Resume内仍有，判别增量及机制尚未确认。LCMD保持NO-GO，所有因果解释标UNRESOLVED。
