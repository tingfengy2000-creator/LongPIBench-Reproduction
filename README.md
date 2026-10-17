# LongPIBench-Reproduction

LongPIBench / PromptLocate 基线复现与逐案例失败归因。本仓库用于本机 Codex 与 RTX 5090 32GB 主机上的 Cursor 通过 Git 交接代码、任务和可核查的回执。

**当前阶段：R0 审计与5090环境准备。尚未运行正式模型实验，没有本地 ASR。**

- [完整 R0 审计入口](audit/README.md)
- [给5090设备Cursor的第一条命令](coordination/CURSOR_START_HERE.md)
- [当前任务](coordination/tasks/R0-5090-001.md)
- [协作协议](coordination/PROTOCOL.md)
- [阶段化研究执行 Prompt](audit/05_codex_execution_prompt.md)
- [固定上游与研究条件](configs/upstream_lock.json)

本机为 RTX 5060 8GB，负责代码、证据与审计；用户已确认可随时连接另一台 RTX 5090 32GB 设备，负责后续GPU工作。远端规格仍需预检回执证实。

## 快速开始

在5090设备安装Git并登录有本私有仓库权限的账号后：

```bash
git clone https://github.com/tingfengy2000-creator/LongPIBench-Reproduction.git
cd LongPIBench-Reproduction
git switch -c machine-5090
python scripts/remote_preflight.py --label machine-5090
```

随后让Cursor按 `coordination/CURSOR_START_HERE.md` 完成任务并提交回执。Linux可用python3；Windows可用py或python，使用实际可运行的解释器。

原始数据和权重保存在本地ignored目录，Git只承担代码、配置、审计与小型回执。已有合成输入和公开来源证据用于核查，不包含模型推理结果。上游仓库不嵌套提交，使用锁定commit重新拉取。
