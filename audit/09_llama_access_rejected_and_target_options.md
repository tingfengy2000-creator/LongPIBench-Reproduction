# Llama访问被拒绝后的研究路线选项

日期：2026-10-17。用户明确确认页面Rejected；原始账户状态更新在coordination/returns/20261017-user-llama-access-rejected/REPORT.md。没有新模型推理或研究结果。

最新用户选择：先找具有合法访问和转交权限的协作者准备HF原模型，非HF资源由我们自行下载。当前优先保留原Llama目标，未选择Qwen；精确离线交接清单为coordination/OFFLINE_MODEL_HANDOFF.md，文件校验不等于HF账户获批或许可资格认定。

## 对当前项目的影响

Llama原条件的R1/R2受阻，R3/R4不能依据未运行的原条件生成失败案例或统计。环境、固定200条数据、输入构造、Mistral底座、GPT-2 helper、检测/定位兼容工作及原始证据仍可复用。任务006继续下载公开资源，与此账号Llama申请独立。

HF官方说明：被拒绝的申请没有访问权限，不能由用户直接重新提交同一申请；模型维护方可以改变访问决定。若仍要争取原模型，可通过维护方的正式渠道请求复核，但没有审批时限或成功保证。来源：https://huggingface.co/docs/hub/models-gated 。协调端没有联系维护方或代发任何消息。

## 两条可行路线

| 路线 | 可做的工作 | 研究表述与限制 |
| --- | --- | --- |
| 保留Llama原条件，争取维护方复核 | 继续006、adapter准备、初始化/轨迹/异常兼容工作 | 目标推理及其真实失败归因仍BLOCKED，不能承诺完成日期 |
| 原模型的合法离线交接（当前用户选择的准备路径） | 有权转交的协作者按原revision获取正文文件，网盘交接后按官方元数据校验、本地加载 | HF账号拒绝记录保持；使用与分发需符合原许可，不借用账号/token；文件到齐仍需R0验收 |
| 新建公开目标的独立条件（建议候选Qwen2.5-7B-Instruct） | 配置与加载检查通过后，在固定输入下运行无防御/有防御配对实验，归因真实残留 | 属于公开代码在新目标上的独立评测，不是原论文Llama数值复现；新目标的攻击/防御表现未知 |

候选不等于已切换：原configs/upstream_lock.json保持不动；新候选在configs/target_candidates/qwen25_7b_instruct.json，仅为待选择方案，不派发下载、模型加载或正式运行。

## 已核对的候选证据

- 官方仓库Qwen/Qwen2.5-7B-Instruct，当前观察到的固定commit a09a35458c702b33eeacc393d103063234e8bc28。
- 官方API返回private=false、gated=false；协调端未认证的固定config HEAD返回200，读取小型config成功。没有下载权重或调用模型。
- 选择的权重/配置/tokenizer文件合计15242788168字节（约15.24GB）；实际下载、文件完整性和5090加载尚待执行。
- 来源、大小、文件hash、config架构摘要记录于audit/evidence/qwen25_candidate_access_20261017.json；官方模型卡：https://huggingface.co/Qwen/Qwen2.5-7B-Instruct 。

公开可访问不等于完整权重下载成功，更不等于本机依赖/GPU兼容已验证。32GB单卡可行性在此仅为待实测的工程判断，不报告已满足全部输入长度或生成预算。

## 若选择独立条件，必须保留的边界

1. 固定新目标revision、tokenizer、chat template、完整generation config、EOS/停止规则、输入tokens、dtype与显存安排，再冻结正式运行。不能只替换model_name而保留未审查的模型默认参数。
2. 保持既定数据、IDs、payload和位置；同一新目标上运行配对无防御/有防御条件。不得在看到正式ASR后选择目标、checkpoint、阈值或攻击。
3. 目标变化会引入模型、tokenizer与模板差异；不得将新ASR直接与论文Llama值比较并据此宣称复现或改进。
4. DataSentinel large/small仍unknown，helper非有限值、定位吞异常、原坐标与评分问题仍需处理。目标可下载不等于R0整体通过。
5. F1—F4/Uncertain分类规则仍预先冻结，F5独立、F6单列；根据新目标上的真实输出逐条归因，不假定原论文的失败比例会重现。
6. 原Llama条件保留BLOCKED及全部历史证据；若以后合法取得访问权，作为另一个独立条件补跑，不能把两种模型混成同一批结果。

原建议候选仍保留供后续选择。按用户最新指示优先离线准备原三套HF模型，任务007自行获取非HF资源；已下载的006成果直接复用。当前没有改变主要实验配置或派发Qwen执行任务。
