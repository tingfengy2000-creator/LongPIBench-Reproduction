# R3 只读证据任务准备记录 v1

状态：任务脚本已准备，本机完整性单元测试通过；5090 的完整 R2 raw 尚未在本次运行核验。此文档不是 R3 研究结果。

基于 `54ac8bd64603641ae4fbb64d2c225cb00fa5a4da` 新建协调端分支 `codex/r3-evidence-export`，该提交以 5090 的 `10c24c83d906f2d7b7a830bbdc143a5dbc5add72` 为祖先。使用独立 checkout 准备，不修改 ingress M1/M2 工作区。

仅新增：`scripts/export_r3_evidence.py`、`tests/test_r3_export.py`、`coordination/tasks/R3-5090-001.md` 和本文档。R1/R2 推理源码、配置、数据、旧输出及审查文件均未修改。

## 本机验证

命令：`D:\anocanda\python.exe -m unittest discover -s tests -p test_r3_export.py -v`

结果：5 项通过。覆盖插入来源区间并集与 unknown、原始文件 hash/目录逃逸拒绝、实际消息/解码/采样参数篡改拒绝、非有限 trace 与截断字段的保留。使用纯测试 fixture 和字符 codec，未产生真实模型评分或新的研究输出。

首次测试发现测试临时目录的父目录在新 checkout 中不存在，已在测试中显式创建 ignored runs 父目录；修正后通过。这是测试设施问题，不是数据失败。

另对两份新增 Python 文件完成 AST 语法检查。尝试重复执行旧的 `audit/r2_receipt_review_v1/verify.py` 时，该脚本在写入既有 `verification.json` 的 exclusive-create 步骤拒绝覆盖，退出非零；旧文件未变，此次尝试不记为新的完整验证通过。tracked 文件与父提交比较无变化。

## 执行与结论边界

远端必须使用现有 raw、固定输入和本地 tokenizer，只读重算评分及校验保存 token，不加载权重、不推理。成功后导出 115 条有效剩余目标命中与 10 条 R2 F6 的候选证据，附同源干净输出。全量 400 条审计摘要和完整 packet 留在新 ignored runs。

Resume 的 82/100 干净目标命中是既有评分语义的重要限制；机械 F1 候选不证明攻击因果。F2/F3/F4/F5 需独立审查，unknown 坐标不补造。证据导出后仍须由协调端逐案复核；不报 R3/R4 完成，不启动新算法。
