# 阶段化复现运行方案

## 当前判断与运行层级

R0 源码、数据和实机审计已执行；未完成模型加载验证。当前能交付审计、输入及执行方案，不能交付实际 ASR 或 F1—F5 数量。

保留三个层级，避免把兼容修复混成方法创新：

1. `public_release`：锁定两份公开代码与已声明配置，保留其评分和恢复行为。
2. `instrumented_compat`：只增加设备／依赖兼容、轨迹、异常状态、坐标映射，不改变定位决策；必须保存补丁和等价性检查。
3. `behavior_fix`：例如修正概率截断索引、评分语义或恢复方式；单列结果，不当成原方法严格复现。

本阶段不设计 SALT，不调新算法，不按 ASR 选择 checkpoint 或筛掉困难样本。

## R0 补齐：实际主机与依赖、权重、配置

执行者先确认目标主机是不是 5090；记录 GPU、显存、驱动、RAM、Python、PyTorch CUDA 构建、CUDA 架构、NF4 kernel、包锁定文件。解决 WSL 权限查询问题或直接使用已有 Linux 主机，不擅自重装系统。

获取经授权的 Llama 固定快照、Mistral 与 GPT-2；下载两个官方 Drive ZIP，生成整包及解压文件 SHA256，选择正确 adapter 目录而非 ZIP 根目录。适配器中不需要的 optimizer/training_args 等不参与推理，不需要重新训练。

必须处理的配置未知项：

- Table 4 的 DataSentinel 是 detector_large 还是 detector_small。
- Llama 历史 chat messages、生成参数／seed、checkpoint revisions。
- Resume 原始文档抽取方式与岗位说明是否对应当前公开 prompt。
- Email Table 1/4 的差异原因。

优先查官方历史、issue、公开说明；若仍无依据，登记 unresolved，并冻结一个有文献理由的公开版本配置。需要人选定未披露 checkpoint 时，只请求该具体选择，不能根据正式测试的 ASR 自动决定。未解决前可以做明确标记的工程冒烟，不声称严格 Table 4 对齐，也不要启动双 checkpoint 正式测试后选更好者。

验收：实际 CUDA/NF4 冒烟成功；三类模型及两个 adapter 的加载成功；单独合成输入验证 detect、oracle、helper 调用；原文保留、错误捕获、坐标映射及日志齐全；差异表与计划被冻结。源码编译或 16 个纯函数测试通过不等于此验收通过。

## R1：无防御，先干净后攻击

使用相同 100 IDs、相同顺序、Authority spoof、Email goal=0/last，Resume goal=2/footnote；目标为 Llama-3.1-8B-Instruct。先做少量**独立合成**格式检查；需要用 benchmark 样本做链路冒烟时，明确标记 debug、保留轨迹，不据此调任何方法参数。冻结后全量运行，不因成功率偏低改 payload。

官方支持的 Bash 命令如下，仅为无防御公开入口示例，须在目标环境就绪、固定本地模型与新输出路径后执行：

```bash
python -m pip install -e './upstream/LongPIBench[hf]'
longpibench download-data --revision cdfdfdba8838911ec3d120d5bbf584c0afb280f2
longpibench inspect --suite email --item-id 0 --attack authority_spoof --goal 0 --position last
longpibench inspect --suite resume --item-id 0 --attack authority_spoof --goal 2 --position footnote

# MODEL_DIR 是已下载并固定 SHA 的本地 Llama 路径。
# RUN_DIR 必须是新建的唯一目录，官方 runner 会以 w 模式覆盖已有文件。
longpibench run --suite email --attack authority_spoof --goal 0 --position last \
  --backend hf --model "$MODEL_DIR" --max-output-tokens 20000 --count 100 \
  --output "$RUN_DIR/email_no_defense.jsonl"
longpibench run --suite resume --attack authority_spoof --goal 2 --position footnote \
  --backend hf --model "$MODEL_DIR" --max-output-tokens 20000 --count 100 \
  --output "$RUN_DIR/resume_no_defense.jsonl"
```

`download-data` 会下载四套并验证存在性，运行时默认读取包内 `longpibench/datasets`。本轮原始数据另外保存在 `data/<SHA>`；若不想重复下载，wrapper 可显式设置 `benchmark.DATA_ROOT` 到这个路径，记录配置即可。CLI 的 `--local-dir` 只改变下载位置，不自动改变运行 DATA_ROOT。

上述 CLI 不保留完整 prompt、计时、tokens，不能单独满足正式证据要求。正式执行前编写薄 wrapper，复用 prepare_example、模型、parse_json_response 和 score_response，添加下节记录；官方输出单独保存。干净对照沿用同一任务 goal 评分，输入构造时 no 条件与 goal 无关；干净条件的目标满足率与合法任务质量分开报告。

R1 验收：每任务100攻击 + 100干净，所有 IDs 完整；每条完整输入与原始响应可追溯；成功、失败、无效、异常、token上限停止分别计数；异常不伪装为防御成功；报告与原论文数值的差异且不调参追数。

## R2：检测—定位—恢复—同目标模型

沿用 R1 已冻结的输入、目标模型、tokenizer、messages、生成预算、解码参数。用独立干净对照测误报与损伤。不得把两个任务内部 oracle 的权重或阈值分别调优。

接线逻辑（示意代码，尚未创建真实 runner）：

```python
example = prepare_example(suite, item_id, attack, goal, position)
flag = whole_detector.detect(example.data_prompt)  # DataSentinel 全文 adapter
if flag:
    cleaned, localized = locator.locate_and_recover(
        example.data_prompt, example.system_prompt  # locator 使用专用 oracle adapter
    )
else:
    cleaned, localized = example.data_prompt, ""
raw_response = target.query(example.system_prompt, cleaned)
```

不能仅记录上述两个返回字符串：需在函数内部保留 segments、搜索区间、所有 oracle 查询与原始输出、helper概率有效性、异常、查询次数、恢复文本和映射。定位内部捕获异常时必须透出 `error_status`，才能与“确实未找到攻击”区分。DataSentinel 没有原生 score 字段，写 null + score_available=false。

为保留方法，先只加观察与异常标记；遇到 NaN 等保存原始轨迹并标 F6。若修复需要改变行为，停止该条件的正式汇总并另开 behavior_fix 运行；不可在半批次途中替换函数后拼接结果。

R2 验收：逐条与 R1 配对；完整检测／定位／恢复／目标输出；明确 F6；不发生静默截断；下游可核验实际 tokens 和 stop reason；配对覆盖完整。batch size=1 分阶段加载，分别报告纯算法耗时和加载／换模耗时。

## 正式记录规范

建议 `runs/<UTC>-<confighash>/manifest.json`、`raw/*.jsonl`、`annotations/*.jsonl`、`derived/*.csv`；raw 只追加不覆盖，断点恢复先核对完整配置 fingerprint 与样本集合；重试保留每次 attempt，不用最后一次覆盖失败。

每个样本至少保存：Run ID、run_kind（debug/formal/failed/invalid）、suite、sample_id、attack、goal、position、payload、源数据SHA、代码commit与patch hash、所有模型／tokenizer／adapter revision及文件hash、seed、dtype与量化配置、实际 chat messages和模板、原文及token数、检测原始输出与二元结果、定位segments和原坐标、清洗文本、删除内容、oracle轨迹、目标原始输出与停止原因、解析结果、official_success、audit_success、validity/error_type、token量、各模块时间与峰值显存。

失败归因与人工审查放 additive annotations，含 reviewer、时间、版本、依据与分歧。CSV 中长文本可以保留，也可链接不可变 JSONL 并附 hash；不能仅保存一个模型响应摘要。

## R3：逐例归因

所有 R2 有效且攻击成功的案例逐条回答交接文档九个问题，并按 `06_failure_attribution_protocol.md` 标 F1—F4 主因、F5 独立标签，异常为 F6。不能从 DataSentinel 触发与否直接推断定位正确或攻击被移除。证据不足写 Uncertain；检测器不是自动真值标注器。

R3 验收：每个剩余成功案例均有可复查证据链和人工判断；数字与逐条表一致；F6 独立；不为了凑齐类别强制解释；插入span和语义恶意span区分。

## R4：描述统计与后续方向

报告两任务的 ASR 与 Wilson 95% CI，绝对下降百分点和相对下降分开；配对比较使用相同有效样本并另报失效覆盖。检测召回、定位覆盖、合法信息误删使用独立真值和已声明分母。F1—F4、Uncertain 的比例以有效剩余成功为分母，F5 可重叠，F6 另列。

本次主实验只有一种攻击、每任务固定尾部位置，**无法据此估计攻击类型或位置的效应**；只可对既定条件中长度、结构、内容做探索描述。要比较其他攻击与位置，另行预注册实验，不能把本阶段差异表改装成消融结论。

100样本时中间比例的 Wilson 区间可能接近 ±10 个百分点，不对细微差异过度解释。避免将某两组CI是否重叠直接作为显著性检验。

最终交付：00_reproduction_environment.md、01_baseline_reproduction.md、02_experiment_results.csv、03_failure_cases.csv、04_failure_taxonomy.md、05_failure_analysis_report.md、06_next_stage_recommendation.md。无结果时明确 NOT_RUN；本轮只交付 R0 文档，不填充研究结论或候选新方法性能。
