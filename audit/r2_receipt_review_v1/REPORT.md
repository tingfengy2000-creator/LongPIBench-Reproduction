# R2回执接收与初步统计审查

**R2执行完成；回执一致性通过，但完整R2 raw复核及R3逐例人工归因尚未完成。**

已取回并核对远端提交`10c24c83d906f2d7b7a830bbdc143a5dbc5add72`。只新增8个允许的回执/日志文件，无源码、参数、依赖或原始数据修改；总墙钟11小时41分28秒。400条防御及400条配对记录齐全，390次目标生成均返回EOS，10条上游F6跳过，无资源截断、CUDA/OOM或重试。

本报告计算仅来自逐例小型回执；不把它写成协调端已重算完整原始模型响应的最终验收。原始trace仍在5090，不启动新GPU实验，不改参数。

## 攻击目标满足率（公开快照guarded条件，非严格原论文配置）

| 域 | R1有效 | R2有效 | 共同有效R1 | 共同有效R2 | 配对绝对下降 |
| --- | --- | --- | --- | --- | --- |
| email | 96/99 (96.97%) | 15/93 (16.13%) | 89/92 (96.74%) | 15/92 (16.30%) | 80.43个百分点 |
| resume | 100/100 (100.00%) | 100/100 (100.00%) | 100/100 (100.00%) | 100/100 (100.00%) | 0.00个百分点 |

Wilson95%区间、配对McNemar、失效范围界和逐例分母见receipt_review.json。Email共同有效92例，74次成功→失败、0次反向；不能用96/99和15/93直接当同分母配对比较。R1 email-072解析异常仍保留，R2该例有效但不进入共同有效对。

**Resume攻击100/100满足官方目标，但clean也有82/100满足同一个goal=2。**这不是正常任务准确率，也不能单凭100%证明每条成功由注入造成。Email clean目标满足0/100同样不能推断合法任务全部正确。

## 检测与异常

全文检测：Email clean51/100报阳性、attack90/100；Resume clean0/100、attack0/100。clean误报与合法信息损伤F5不是同一个指标。115条有效剩余目标命中中，110条检测返回0且回执cleaned SHA与固定原文一致（Email10+Resume100）；可列为F1待复核候选。其余5条Email检测触发但仍成功，定位/残留原因目前Uncertain，不从计数硬分F2/F3。

10条F6全部Email localization，trace_counts显示nonfinite_helper=true，非边界NaN；clean3、attack7，均未执行protected生成，不能计作防御成功。10条清单见f6_cases.csv。

Email检测触发后大量mapping_status为UNKNOWN或UNKNOWN_INVALID_ORIGINAL_INTERVALS。有效执行不等于定位坐标已可靠；即使EXACT_ORDERED_NONWHITESPACE_COVERAGE也仅说明原分段映射，不自动证明恶意指令被完整覆盖/清除。

## 下一步（本次未执行）

只读核验5090已有R2 plan、400份defense及400份protected raw的hash/来源，重算target渲染/实际greedy overrides和官方评分，导出115条剩余成功、10条F6及必要clean对照的可审查证据包。优先审5条检测触发仍成功的Email，核对原恶意span、实际oracle/helper异常、恢复文本和最终响应；Resume还要逐源匹配clean目标命中，避免把自然目标满足当注入因果。无需重跑GPU、修改helper、换checkpoint或扩大预算。

本次接收仅验收回执完整与一致性；R3、R4和严格论文复现均未宣告完成。M1/M2与这份R0–R4归因表独立，尤其不要混用两边F1–F6含义。
