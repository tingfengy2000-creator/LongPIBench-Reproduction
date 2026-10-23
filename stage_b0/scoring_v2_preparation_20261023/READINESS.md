# 2026-10-23 B0探索评分前置状态

状态：`WAITING_B0_5090_003_EXECUTION`。不是模型可用性验收通过，也不是400条评分任务已派发。

GitHub连接器实时读取machine-5090为`2ed81a2cc5fb2caebf1659ab89e78811ee7940e1`，与协调审核分支`395bc2f4c75d41a2e5e95c4029c0c3101b98c92d`相比落后4个提交，没有新的003回执。用户进一步确认“未执行003”。原始查询摘要见remote_status.json；本机Git fetch经本地代理及单次直连均失败，未据旧tracking ref冒充远端新状态。

## 已完成的准备

- 400条候选仍为原manifest SHA256 `02c8352e3c5a33dc2af164f321f97e9ba9e7ded48b67ae16663d270dfc18c954`；80源及开发240/探索留出160分组不改。
- 已发布的探索性标签门位于`coordination/returns/20261022T153529Z-b0-gemini-completion-2ba621b8/exploratory_label_freeze.json`。本轮重新运行`freeze_gemini_labels.py --check-only`通过；120条双AI一致暂定、280条单AI暂定，未决0；不是人工金标。
- 审核工具14项测试、原统计/全覆盖6项测试均通过，共20项。它们验证工程与统计实现，不是检测性能证据。
- 原协议、固定模型revision、提示、精度、全覆盖窗口、Max聚合、开发阈值规则保持不变；原R0–R4/M1/M2/G0文件不改。

## 现在交5090执行

使用已发布的`coordination/tasks/B0-5090-003.md`，基准审核分支HEAD `395bc2f`已包含该任务及路径修复。保护当前工作区，仅在无运行中的GPU实验、工作区干净、分支为machine-5090时fetch并ff-only合入`origin/codex/b0-ai-label-review`。不得reset/stash/强推，不合入旧main来替代审核分支。

三个独立进程依次核验PG2、DataSentinel、Llama；实际缓存固定`/mnt/e/LongPIBench-Reproduction/models/b0-cache`。仅PG2允许下载新权重；不重下现有Llama/Mistral，不改依赖或trust配置。独立角色权限/普通加载失败可继续下一角色；OOM、未释放进程、磁盘不足停止全部。每次真实状态和退出码按原任务记录，不重试择优。

本机无法直接操作5090，提示词需由用户交给5090本地Cursor。此文档不表示5090已经开始。

## 003回执验收清单

1. 回传commit可从远端取得；仅新增本次小型availability.json和汇总REPORT，未覆盖原回执、代码、模型、历史输出。
2. 实际主机DESKTOP-B5PNBNC及CUDA RTX5090证据；三角色进程独立，缓存最终resolve到D/E盘；记录实际输入commit、命令、退出码和唯一Run ID。
3. PG2固定`a8ded8e697ce7c355e395a0df51f94adb4a2fd27`：真实config及权重哈希、BENIGN/MALICIOUS标签身份、512上下文、FP32及有限logits/类别softmax。403或未审auto_map须保留阻碍，不能标可用。三条短控制不是检测性能。
4. DataSentinel：复用已冻结Mistral+large/checkpoint-5000，实际固定文件核验、原generation defaults、适配器激活、原二值接口控制；不构造风险概率。底座滑窗/上下文仍分开记录。
5. Llama：本地固定revision、真实BF16不量化、有限前向和短生成证据；local_spec仅核旧已验收哈希与当前文件大小的范围须如实披露，不夸成重新全量权重哈希验收。短控制不等于B4/B5提示对照或400条已跑。
6. 逐角色验收，允许部分通过/部分阻碍；不以总退出码0覆盖角色失败，也不以旧CPU探针代替同一5090比较条件。

## 收到003后才能派发的评分工作

当前`stage_b0/run_classifiers.py`仍是原人工签认入口，拒绝无human_signoff是预期行为，不能直接用于AI标签探索，也不能伪造签认。现有入口仅覆盖PG1/PIGuard；完整PG2、DataSentinel、B4/B5评分与汇总尚须准备并验证后另派明确任务。

新入口须显式调用`require_exploratory_label_freeze`、记录标签门及协议摘要；仅追加新文件，原人工门与旧准备包不改。单窗口与原生推理一致、原文token全覆盖、精确模型文件核验、结构化输出解析与不自动修复、异常保留、耗时与显存记录均须先检查。不能把此计划当作已经可执行的全量脚本。

运行条件仍是原协议的同一5090串行、batch1：PG1/PG2/PIGuard FP32全覆盖非重叠原生tokenizer窗口+Max；DataSentinel原NF4/BF16与二值规则；同一Llama BF16 greedy/seed42/max_new_tokens192完成B4/B5。每角色独立新Run ID，禁止覆盖和无记录重试。所有模型同一冻结400条件；原始分数全部保留。

开发/留出分析顺序固定：只用development冻结global和domain各自10%/5%FPR阈值、PIGuard级联95%开发召回门槛，再一次性汇总exploratory_holdout；不从留出调阈值、选择提示或更换标签。DataSentinel/B4/B5仅二值操作点，不捏造连续ROC。级联仅按原PIGuard→B5规则缓存重放并标注延迟重构，不声称在线p95。

按域、ordinary/HB、攻击族、有效/invalid/unknown分母报告；同源成组区间、固定模板和单作者构造限制不改。未独立运行目标业务任务时，目标满足、新增目标变化和任务损伤保持unknown；检测结果不能叫因果ASR。B0结束停止，不自行训练或开发新算法。
