# LongPIBench-Reproduction

LongPIBench / PromptLocate 基线复现与逐案例失败归因。本仓库用于本机 Codex 与 RTX 5090 32GB 主机上的 Cursor 通过 Git 交接代码、任务和可核查的回执。

**当前阶段：R0 审计与5090环境准备。尚未运行正式模型实验，没有本地 ASR。**

最新进展：环境004已按用户回执验收，环境清单保存及固定200条数据通过。Mistral/GPT-2配置访问通过；[R0-5090-005](coordination/tasks/R0-5090-005.md)当前因Llama未认证401受阻，待5090本机用户交互登录HF后由本地Cursor重试。真实模型加载及正式运行仍待验收；下文较早环境状态保留作历史。

- [完整 R0 审计入口](audit/README.md)
- [给5090设备Cursor的第一条命令](coordination/CURSOR_START_HERE.md)
- [当前入口：5090电脑Windows PowerShell身份检查](coordination/WINDOWS_5090_CONNECT.md)
- [当前任务：独立Conda环境与CUDA/NF4实测](coordination/tasks/R0-5090-004.md)
- [已接收的环境盘点](coordination/tasks/R0-5090-003.md)
- [当前下一步：WSL2内部GPU与Python检查](coordination/WSL_5090_NEXT.md)
- [最新入口：Ubuntu内Conda与网络检查](coordination/WSL_SHELL_AND_CONDA.md)
- [后续GPU任务：CUDA/NF4与最小导入](coordination/tasks/R0-5090-002.md)
- [协调端代码进展与回执审查](audit/07_coordinator_update_20261017.md)
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
python scripts/remote_preflight.py --label actual-5090 --task-id R0-5090-002 --require-gpu "RTX 5090" --min-vram-mib 30000
```

随后让Cursor按 `coordination/CURSOR_START_HERE.md` 完成任务并提交回执。Linux可用python3；Windows可用py或python，使用实际可运行的解释器。

上次回执186e6df来自无GPU Cloud VM，状态BLOCKED，已集成；必须改用真实5090电脑桌面的本地Cursor。执行端只负责GPU命令与证据，主要代码和方法由协调端修改。

第二次回执66a50d6同样来自无GPU Cloud VM，已接收；硬件检查正确返回2并停止。用户已确认可进入真实5090电脑的Windows PowerShell，当前先在那里执行两条身份检查，不继续重复Cloud任务。尚无5090硬件验收、CUDA/NF4或真实模型结果。

后续用户已实际回传DESKTOP-B5PNBNC的RTX5090/32607MiB/驱动610.88，已单列为人工终端证据；当前进入该电脑现有环境盘点R0-5090-003。尚未验证其Python、WSL、CUDA/NF4和模型，先盘点再确定安装方案。

Windows盘点现已回传：Git、Python3.14和Ubuntu-24.04 WSL2可见；Conda未在PATH找到。接下来复用现有WSL2并核验Linux侧GPU/Python，Windows Python保持不动；未安装推理环境，未启动正式实验。

WSL内部GPU查询现已回传，显示真实5090/32607MiB/610.88，系统Python3.12.3；交互Ubuntu提示符出现(base)，Linux侧Conda及网络仍待确认。两种终端命令已分开写明，未开始安装或研究推理。

Conda与网络盘点已完成：Miniforge/Conda26.3.2，base交互Python3.13.13，已有gmtp-compat和llmguard-paper1；PyPI及cu128索引HEAD200。当前创建独立longpibench-r0/Python3.11候选环境，先测torch2.7.1/cu128+BNB0.46.1。固定直接依赖见requirements/r0-compat-candidate.txt；尚无实机CUDA/NF4通过或完整模型结果。

`repro/` 新增硬件检查、OPI最小加载入口、debug接线、官方评分与审计分离、不可覆盖的attempt存档。它仍不是正式实验runner，尚缺真实模型验证及完整定位坐标/内部轨迹。离线测试：`python -m pytest tests -q --basetemp .pytest-local-UNIQUE -p no:cacheprovider`，UNIQUE应替换为新的目录名，避免覆盖上次测试目录。

原始数据和权重保存在本地ignored目录，Git只承担代码、配置、审计与小型回执。已有合成输入和公开来源证据用于核查，不包含模型推理结果。上游仓库不嵌套提交，使用锁定commit重新拉取。
