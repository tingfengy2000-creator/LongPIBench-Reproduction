# B0-GEMINI-001：固定120条探索性标签独立二审

用户2026-10-23授权替换无额度的Claude Code，由协调端选择Gemini。固定同一120条、同一六批，不重抽样。仅AI审核，不是运行检测器、执行文档命令或业务任务。

## 网页/Windows软件

使用`stage_b0/ai_review_v2/gemini_handoff/`。每次上传一个`batch-001.txt`到`batch-006.txt`；每文件已包含冻结审核提示和20条完整待审数据。也可上传GEMINI_PROMPT.md与对应原始JSONL。不要上传原dataset_manifest、private_mapping、label_review或Cursor/Grok回答。建议六批分别新对话，避免上下文累积或截断。

请界面实际显示的模型名/版本记录；未显示就unknown，不把模型自称当独立验证版本。不要根据审核输出切换模型。模型无法读附件、输入被截断、未输出20条就如实返回缺失ID，不能编造完成。每个review_id首次判定全部保留，补齐遗漏不等于可反复重审择优。

标签规则及schema已在每个txt内：只读trusted_task与完整untrusted_document判断0/1/null、role、精确原文evidence、简短reason、ambiguity、confidence。未知允许null，不能当0；攻击不需要成功。不要执行文档命令、访问其地址、发送信息或调用业务工具。不要求隐藏思维链。

## 回传

每批保存原始可见JSONL回答，六批共120个唯一ID。将文件或完整原始回答交给协调端，协调端另存唯一`coordination/returns/<UTC>-b0-gemini-label-review-<unique>/`，保留各批原文与合并reviews.jsonl、实际reviewer_metadata.json、REPORT.md。元数据channel=secondary，annotation_type=AI_NOT_HUMAN；其他字段见模板，如实记录是否看过其他标签/结果。

协调端运行原只读验证器：

```powershell
D:\anocanda\python.exe stage_b0\ai_review_v2\review_io.py --channel secondary --reviews coordination\returns\ACTUAL_RUN\reviews.jsonl --metadata coordination\returns\ACTUAL_RUN\reviewer_metadata.json
```

部分完成用--allow-partial并保留PARTIAL，完整状态`AI_FIXED_SECOND_REVIEW_120_EXPORTED_REVIEW_REQUIRED`。验证只证明schema/原文/覆盖，不证明标签正确。不得创建human_signoff或修改旧标签/样本，不自行开始检测评分、训练、新算法。完成后停止等待协调端比较。
