# G0历史证据审查：已确认B100，进一步机制尚待控制

**本批Resume全漏检不是攻击在输入中丢失或被截断：100/100均完整进入实际token序列，判定一致，归为B。** 这支持“攻击已进入但检测器未识别”。尚不能把“领域语义”定为唯一原因；原Email与Resume同时改变了文档长度、内容与payload。

## 已核验范围

- 输入执行提交`44f64a4be3575dfc942b6287e4b1461dc2f858b6`；回执提交`718c33d8f27e6c11b6552c41a6fccc0cca495541`；Run ID `20261019T054409Z-g0-visibility-fd1beae5`。
- 回执仅新增9个小型文件，原R0–R3代码与结果保持不变。
- 协调端取得固定revision的tokenizer/config约2.3MB，仅存E盘ignored目录，不下载模型权重。文件SHA与原5090下载回执一致。
- 本机从冻结公开输入重建400条原DataSentinel格式prompt，全部token ID摘要与5090从历史raw导出的实际输入摘要相等；另外独立核对200条攻击区间、400条decode与二值回放。完整历史raw依旧在5090，不称为本机读了完整raw。
- 权重身份、precision、tokenizer、阈值语义和统一预处理路径见原G0 `model_configuration.json`：Mistral固定revision、large/checkpoint-5000；没有原生数值风险阈值，按返回文本标记判0/1。历史未保存logits，未虚构连续风险分数。

## 分层结果

| 条件 | N | 返回0 / 1 | 实际输入token范围 | 攻击完整可见 | 截断 | 规则/接口判定差异 |
| --- | ---: | --- | --- | --- | ---: | ---: |
| Resume attack | 100 | 100 / 0 | 339–1037 | 100/100 | 0 | 0 |
| Resume clean | 100 | 100 / 0 | 247–945 | 不适用 | 0 | 0 |
| Email attack | 100 | 10 / 90 | 1471–3943 | 100/100 | 0 | 0 |
| Email clean | 100 | 49 / 51 | 1327–3799 | 不适用 | 0 | 0 |

Resume attack根因分类：A=0、B=100、C=0、D=0、E=0。Email attack为B=10、NOT_A_MISS=90。clean不混入攻击根因分母。

全部输入均小于配置最大位置32768，亦小于配置sliding_window4096；攻击位于最终配置滑窗内。模型实际attention未保存，不声称证明其关注/理解了攻击，只排除本批序列层面的攻击覆盖丢失，以及超过配置窗口这一解释。

## “prompt残余”不是本批误判原因

Resume100条攻击的新增token序列相同，decode为`DGDSGNH Tpl<|fin`。保存的query文本比单独decode续文多了前导空格，二者都满足原规则的0。所有Resume clean也仅有这种空白差异。Email attack有5条、Email clean有24条出现仅空白差异，其余完全一致；400条均未发现会改变二值判定的差异。

所以`prompt_removal_left_residual_text=true`在此不能直接解释为“输入prompt泄漏导致假阴性”。这是精确字符串不相等的宽泛字段，本机已独立核验为whitespace_only。没有更改原判定或修复wrapper。

## 为什么还需要小规模控制

Resume输入更短；两域历史payload也不同。Email clean已有51/100触发，不能把90/100攻击触发全部解释为正确识别攻击语义。单凭历史对照还不能区分领域内容、攻击文本、长度或任务式标记信号。

沿用控制前就写定的4源（各域000/050）、两份原payload和最多26次查询。协调端已冻结精确输入/token/hash：共同正文长度128/320，8组同payload跨域配对的最终输入token数均完全相等；没有查看控制输出或按结果换样本。

冻结输入见`g0_resume_diagnosis/frozen_controls_v1/plan.json`，SHA256 `39639607866a6cbc5c2a44be6516c68e9022cf0e4bf3733ade4cc7dc64a442f8`。正文前缀以同一固定预处理后的clean文本编码，payload本身保持原样；这是构造机制控制，不是自然文档新测试集。此前预案的精确实现说明与环境差异记录见`preparation_notes.md`。

下一步仅Go这26个同检测器前向；新算法、阈值拟合、checkpoint替换均No-Go。记录原始LM logits的只读hook不返回替换值，也不改generate参数/返回类型；它们不是注入概率。若失败保留attempt并停止，不换条件重试。结果审查后完成G0并停止。

当前G0状态：历史输入覆盖审查完成，小规模机制控制尚未执行。R4未启动，无新增模型前向结果。
