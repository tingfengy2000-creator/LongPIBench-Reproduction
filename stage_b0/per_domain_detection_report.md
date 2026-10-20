# B0领域检测报告：尚未评分

状态：`PENDING_HUMAN_LABEL_SIGNOFF_AND_REMOTE_EXECUTION`。当前没有B0真实评分或TP/FP/TN/FN；不能从工程加载控制填写性能。

候选共Email/Resume各40基础源、每源5变体；development各24源、exploratory_holdout各16源。新合成文本，不是自然总体样本；标签待用户人工签认。

实际运行后每模型按域、ordinary/HB、三攻击族输出TPR、FPR、连续分数AUROC/AP、development冻结10%及5%FPR阈值的留出Recall，同时报告实际留出FPR与覆盖/invalid。完整定义见protocol_v1.md。二值基线不制造连续分数。

Q1（PG2/PIGuard是否解决Resume漏检）和Q2（能否兼顾HB）均为**unknown，尚无本轮比较证据**。G0的B100仅是历史DataSentinel特定输入诊断，不能替代新数据对照。
