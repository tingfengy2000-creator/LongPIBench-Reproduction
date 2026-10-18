# Stage M1 独立机制探索

入口：[mechanism_report.md](mechanism_report.md)。任务二准备：[independent_data_design.md](independent_data_design.md)。环境与字段：[environment_audit.md](environment_audit.md)、[score_schema.md](score_schema.md)。

24个新写良性片段，真实固定Prompt Guard评分；纯格式配对有分数变化，没有0.5分类翻转。官方构造文档中另见1条内容/长度仍混杂的尾块误报。没有正式论文确认性结论，也未开发LCMD或边界鲁棒算法。

原始证据在`raw/20261018T134643Z-m1-boundary-efd3eb5b/`；源与全文见证为`sources_and_conditions.jsonl`。所有写入使用排他创建，禁止覆盖或重跑当前目录。`plan.json`在真实评分前已提交。

本次顺序（历史命令，仅供复核；不要在已有产物目录直接重跑）：

```powershell
. ./ingress_detection_pilot/storage_paths.ps1
& ./ingress_detection_pilot/.venv/Scripts/python.exe ./ingress_detection_pilot/stage_m1/prepare.py
# 提交冻结方案 e43a80b 后：
& ./ingress_detection_pilot/.venv/Scripts/python.exe -u ./ingress_detection_pilot/stage_m1/run.py
& D:/anocanda/python.exe ./ingress_detection_pilot/stage_m1/analyze.py
& ./ingress_detection_pilot/.venv/Scripts/python.exe ./ingress_detection_pilot/stage_m1/audit_candidates.py
& D:/anocanda/python.exe ./ingress_detection_pilot/stage_m1/verify.py
```

若需独立重复，另立新任务/目录/Run ID保留本次证据；不更改旧960或R2。当前阶段到交付为止，不自动执行后续实验。
