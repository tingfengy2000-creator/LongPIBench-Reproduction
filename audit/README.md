# LongPIBench Stage R0 审计交付

审计日期：2026-10-17。状态：**R0 审计已完成；正式 R1/R2 尚不具备全部运行条件。没有产生任何本地模型 ASR。**

后续进展：[协调端代码与Cloud回执审查](07_coordinator_update_20261017.md)。用户已明确代码与方法由协调端负责，Cursor只执行GPU任务；当前任务为R0-5090-002。

建议先读 [审计结论与阻碍](04_findings_and_blockers.md)，再使用 [可直接交给 Codex 的中文执行 Prompt](05_codex_execution_prompt.md)。

| 文件 | 内容 |
| --- | --- |
| [00_reproduction_environment.md](00_reproduction_environment.md) | 当前实机、5090 可行性、模型、依赖、许可信息入口 |
| [01_code_and_paper_audit.md](01_code_and_paper_audit.md) | 原论文、Table 4、代码结构、数据流与差异 |
| [02_dataset_audit.md](02_dataset_audit.md) | 固定数据版本、200 条原始样本检查、400 条预构造输入 |
| [03_baseline_run_plan.md](03_baseline_run_plan.md) | R0 补齐、R1—R4 分阶段执行与验收 |
| [04_findings_and_blockers.md](04_findings_and_blockers.md) | 风险证据、优先级、最小适配边界 |
| [05_codex_execution_prompt.md](05_codex_execution_prompt.md) | 可复制执行的中文交接 Prompt |
| [06_failure_attribution_protocol.md](06_failure_attribution_protocol.md) | F1—F6、Uncertain、指标与人工复核规则草案 |
| [prepared_inputs.jsonl](prepared_inputs.jsonl) | 官方构造器生成的干净／攻击输入，**不是推理结果** |
| [evidence/](evidence/) | 论文原文、版本、校验和、实机信息、ZIP 元数据、离线探针 |

目录约定：`upstream/` 是未修改的官方仓库克隆；`data/<HF SHA>/` 是原始公开数据；`scripts/` 是本次审计脚本。工作目录最初为空，没有Git仓库。审计过程中用户进一步授权建立跨设备Git协作项目，因此随后建立私有协作仓库并准备提交推送；没有安装模型环境、下载完整模型权重或启动训练／正式推理。

用户已确认另一台RTX5090 32GB设备可随时连接，设备上有Cursor；正式GPU工作转由该设备执行。详见根目录README和coordination/中的第一项任务，远端仍需回传实测预检。

来源下载曾遇到终端网络限制和 arXiv 证书链问题；公开仓库通过获准网络调用取得，论文改用系统信任证书下载，未关闭 TLS 校验。`source_manifest.json` 保留首次采集失败；后续成功下载的论文以 `evidence_integrity.json` 及最终交付清单校验，不覆盖失败记录。
