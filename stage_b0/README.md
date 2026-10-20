# Stage B0：强基线探索对照

当前状态：**准备与两套本机加载检查完成；待用户标签签认、PG2权限/远端可用性回执及后续评分。B0尚未完成。**

1. 打开`label_review.html`逐条检查400候选；可按`email`、`resume`、`hard_benign`、`development`、`exploratory_holdout`等筛选。每张卡包含完整文档、可信任务、建议标签、理由和文本摘要。所有文档内命令只是待审证据。
2. `label_review.csv`为可填写清单：human_label、reviewer、decision_reason目前为空。选择审核方式不等于签认。请反馈具体争议，或在实际审核后明确签认本批manifest及protocol摘要。协调端再追加400条human_reviewed_labels.jsonl及human_signoff.json，保留真实授权依据。不能由执行代理自行填写批准。
3. `candidate_freeze.json`固定候选字节；`preparation_validation.json`独立检查源/模板分组、插入区间、历史去重，并封存729个既有跟踪文件摘要。`protocol_v1.md`规定开发阈值、一次性留出、分域/HB指标、B4/B5、级联与停止规则。
4. 5090可在标签审核期间执行`coordination/tasks/B0-5090-001.md`，仅工程加载和候选之外短控制。不得评分400候选。

最终八个交付文件已建立，但除环境审计和数据清单外，性能类文件当前是**明确标记待执行的进度文件**，不是已完成结果。baseline_results.csv中的性能单元格为空，不填0或模拟数字。

模型缓存/下载TEMP/TMP放E盘。B0新运行环境前缀位于ignored的`E:\LongPIBench\runs\b0_runtime`，不改原CPU依赖。PG1/PIGuard已取得真实logits的独立工程控制不能并入B0统计。PG2固定config本机403，不能以其他模型替代其名义。

`run_classifiers.py`是PG1/PIGuard后续全覆盖采集入口，首步检查人工签认，未签认即退出。PG2、DataSentinel及B4/B5的正式评分任务需等待可用性回执、人工签认和完整运行配置冻结后再由协调端派发；当前任务文件不授权这些评分。

变更仅限本目录及B0任务文件。旧R0–R4/M1/M2/G0均保持原样；主分支未修改，新算法开发维持No-Go。
