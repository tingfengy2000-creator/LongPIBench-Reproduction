# R0-5090-005 回执（再次重跑）

- 任务：R0-5090-005
- 新运行 ID：20261017T134334Z-model-access-a54a3d6a
- 主机：DESKTOP-B5PNBNC
- 环境：longpibench-r0
- 输入 commit：053a8d9fff41ffbf33b8db9c97fc9c0935cb816d
- 命令：conda run --no-capture-output -n longpibench-r0 python scripts/model_access_preflight.py --task-id R0-5090-005
- 退出码：2
- 状态：BLOCKED（BLOCKED_CONFIG_ACCESS）
- 未下载权重、未加载模型、未启动正式实验。

旧回执均保留。CLI 凭据仍存在，未读取 token。

| 角色 | 结果 |
| --- | --- |
| Llama-3.1-8B-Instruct @0e9e39f2 | GatedRepoError，HTTP 403 |
| Mistral-7B-v0.1 | PASS |
| gpt2 | PASS |

与上一轮 8ad2a511 相同。账号 tingfenggg 对 gated Llama 仍无访问权。
