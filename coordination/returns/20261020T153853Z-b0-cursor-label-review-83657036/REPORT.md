# B0-5090-002 Cursor 盲审回执

状态：`AI_FIRST_REVIEW_400_EXPORTED_REVIEW_REQUIRED`。这是探索性 AI 标签审核，不是人工金标，也不是 B0 检测评分完成。

- 任务：B0-5090-002
- 主机：DESKTOP-B5PNBNC
- 输入 commit：`0f85b4f6316a8e33c3f7250e866a4e49c3cc6d5f`
- Run ID：`20261020T153853Z-b0-cursor-label-review-83657036`
- 审核入口：Cursor Agent
- 实际模型：Grok 4.7
- 版本可见性：会话系统说明写明当前助手是 Grok 4.7（SpaceXAI 训练的语言模型）。没有另给独立构建号，型号和版本都记为该可见名称。
- 执行方式：逐条阅读盲审 packet。没有加载 Llama、PIGuard、PG1、PG2 或 DataSentinel，没有运行检测评分。

## 完成数量

20 个 batch 均完整阅读，每批 20 条，合计 400 个唯一 ID。没有截取前 512 tokens。重复的活动日志行先用完整行模板核对，未匹配的日志行为 0；每条文档里模板之外的句子都读过，包括出现在文首或文末的指令。

| 角色 | ai_label | 数量 |
| --- | --- | --- |
| data | 0 | 80 |
| quotation | 0 | 80 |
| attack | 1 | 240 |
| uncertain | null | 0 |

ambiguous 为 0。没有无法判定的条目。

## 盲审边界

- `proposed_labels_seen`：false。本次没有打开 `dataset_manifest.jsonl`、label_review、sources、private_mapping、二审 packet 或预设标签。此前 B0 协议只描述过条件族名称，没有给出这 400 条的条目标签。
- `other_reviewer_labels_seen`：false
- `detector_scores_seen`：false
- `human_review_performed`：false

## 文件

- `reviews.jsonl`：277711 字节，SHA256 `3e4583bf8808081398eb937f6c28c4807ede1250e67561d8ff5910be370b61c7`
- `reviewer_metadata.json`：625 字节，SHA256 `1b4edb92a080a22c97bcef9d48125561089504fe508677d658379712dfd8dfe4`

## 验证

```bash
conda run --no-capture-output -n longpibench-r0 python stage_b0/ai_review_v2/review_io.py --channel cursor --reviews coordination/returns/20261020T153853Z-b0-cursor-label-review-83657036/reviews.jsonl --metadata coordination/returns/20261020T153853Z-b0-cursor-label-review-83657036/reviewer_metadata.json
```

退出码 0。结果 `n=400`、`complete=true`、`exact_model_known=true`、`blindness_declared=true`，状态 `AI_REVIEW_SCHEMA_AND_COVERAGE_VALID_NOT_LABEL_TRUTH_VALIDATION`。该检查只核结构、原文证据和覆盖，不判断标签真伪。

全量审核已导出。未生成 human_signoff，未比较预设标签，未启动 400 条检测、B4/B5、级联或训练。
