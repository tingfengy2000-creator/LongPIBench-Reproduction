# R0-5090-005 回执（换账号登录后）

- 新运行 ID：20261017T152132Z-model-access-98dd33a5
- 输入 commit：2b617c971aac212accabb9193c32ffabab2d716f
- 主机：DESKTOP-B5PNBNC
- 环境：longpibench-r0
- 命令：conda run --no-capture-output -n longpibench-r0 python scripts/model_access_preflight.py --task-id R0-5090-005
- 退出码：0
- 状态：CONFIG_ACCESS_PASS_NOT_MODEL_ACCEPTANCE
- 未下载权重、未加载模型、未启动正式实验。

CLI 凭据存在。whoami 为 Liam11222（不读取 token）。旧 403 回执均保留。

| 角色 | 结果 |
| --- | --- |
| Llama-3.1-8B-Instruct @0e9e39f2 | PASS，config 855 bytes |
| Mistral-7B-v0.1 | PASS |
| gpt2 | PASS |

这只证明固定 config HEAD 可访问，不等于 Llama 权重已下载或 GPU 加载通过。
