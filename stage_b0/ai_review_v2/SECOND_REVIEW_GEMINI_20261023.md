# 2026-10-23：Gemini接替Claude Code的固定二审

用户先因Claude Code无额度提出使用Grok；随后收到Cursor一审实际使用Grok 4.7的回执，并明确提供豆包/Gemini让协调端选择。协调端选择Gemini作为固定二审入口，减少同家族自我复核。Grok网页准备方案未派发，保存在ignored runs的准备草稿，不作为已运行审核。

此追加仅替换POLICY.md与B0-CLAUDE-001的二审入口，不重抽样、不改变输入/标签schema/分组/阈值。原400候选、Cursor400条一审回执、原固定120条二审packet均不改。Cursor仍是第一审核来源；Gemini的具体型号、版本以实际界面为准，未显示则unknown，不猜测，也不按结果换模型。

Gemini不得看Cursor审核、原建议标签、private_mapping、label_review或检测分数。网页上传仅用gemini_handoff内盲审包。若Grok网页已经产出任何条目，应保留并单独注明来源，不能挑选不同模型间更符合预期的回答。分歧/null仍按原策略保留或追加裁决，不能强行多数表决冒充真值。

返回继续使用channel=secondary、annotation_type=AI_NOT_HUMAN、reviewer_entrypoint=实际Gemini入口。原review_io.py兼容任意如实填写的模型入口，不需修改原回执验证器。最终标签冻结须绑定本追加政策摘要，记录实际二审为Gemini。

原POLICY.md其余规则继续有效：探索性AI标签不能称人工金标，正式确认性研究仍需独立人工标签；400条检测评分不在本次二审任务中自动启动。
