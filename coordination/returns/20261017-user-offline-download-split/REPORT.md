# 用户指示：HF与非HF下载分工

日期：2026-10-17。用户原话：“只能通过huggingface获取的模型 我们就这样找人帮忙下载，其余我们有办法的就自己下载”。这是用户选择的资源准备路径，不是已经取得模型或许可资格的证据。

按当前固定来源，委托合作者准备三套HF模型：原目标Llama-3.1-8B-Instruct、Mistral-7B-v0.1底座和GPT-2 helper。已有006文件保留复用，只补缺失内容。非HF的两个官方Drive adapter包和spaCy官方GitHub wheel由5090按任务007自行获取。

原Llama目标和revision保持不变；Qwen候选未选择、未下载、未执行。Llama合法离线交接需符合模型的访问、使用及分发许可；账户Rejected及四次403证据仍保留，文件到齐不等于HF账号获批。

已交付：coordination/OFFLINE_MODEL_HANDOFF.md、configs/offline_transfer_manifest.json、离线下载/验收工具及任务007。三项离线工具测试通过，命令语法检查通过，固定模型清单与upstream_lock一致。测试仅验证工具边界，未下载大权重、未加载模型、未运行正式实验。
