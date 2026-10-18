# Stage M2

入口：[07_mechanism_analysis.md](07_mechanism_analysis.md)、[08_go_no_go_report.md](08_go_no_go_report.md)。

NO-GO：当前不进入跨Chunk上下文一致性检测算法设计。本阶段为人工构造小样本机制探索；40基础源、80良性/攻击变体，每个条件共享这些源。不是自然业务分布、不是正式论文测试或算法收益证明。

环境/封存00、评分前计划01、80变体manifest02、官方/Shadow/恢复结果03–05、逐翻转归因06、下一阶段建议09。完整原始输入位于`E:/LongPIBench/runs/20261018T152953Z-m2-context-6e5c0c4d/frozen_inputs.jsonl`；真实评分`E:\LongPIBench\runs\20261018T153419Z-m2-full-974bbbce\observations.jsonl`，日志、start/completion同目录。原始大文件本地ignored，不随小型Git回执传输。

执行顺序：prepare.py -> 冻结ccdd523 -> run.py --phase smoke -> 烟测/分析预声明88356a9 -> run.py --phase full -> analyze.py -> verify.py --phase full -> adjudicate.py -> figures.py -> report.py -> finalize.py。
已有输出均排他创建，禁止覆盖重跑。所有缓存/模型/新原始数据在E盘，5090 R2不访问。M2已结束，不自动开始M3。
