# R0-5090-005 回执（浏览器登录后重跑）

- 任务：R0-5090-005
- 新运行 ID：20261017T133331Z-model-access-8ad2a511
- 主机：DESKTOP-B5PNBNC
- 环境：longpibench-r0
- 输入 commit：44290b6a9ff3d845e1a240289a2f220fd5c0c1c5
- 命令：conda run --no-capture-output -n longpibench-r0 python scripts/model_access_preflight.py --task-id R0-5090-005
- 退出码：2
- 状态：BLOCKED（BLOCKED_CONFIG_ACCESS）
- 未下载权重、未加载模型、未启动正式实验。

旧回执均保留。CLI 凭据仍存在（不读取 token）。浏览器已登录不等于该账号已获 Llama gated 授权。

| 角色 | 结果 |
| --- | --- |
| Llama-3.1-8B-Instruct @0e9e39f2 | GatedRepoError，HTTP 403 |
| Mistral-7B-v0.1 | PASS |
| gpt2 | PASS |

需要用与本机 CLI 登录相同的账号 tingfenggg 打开 https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct ，确认 Access granted 并接受协议。不要把 token 发给代理。
