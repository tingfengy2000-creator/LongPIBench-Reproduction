# R0-5090-002 回执

- 任务：`R0-5090-002`
- 运行 ID：`20261017T112010Z-actual-5090-1114bdf6`
- 分支：`machine-5090`
- 输入 commit：`0945dfd0a15dc006ed1b0c858106d61939d288a0`（fetch 后将 `origin/main` 快进合并到 `machine-5090`）
- 任务状态：**BLOCKED**
- 阶段：硬件身份检查失败后按任务要求停止。未安装、未下载、未改主要代码或方法，未启动正式实验。

## 主机身份

| 项目 | 实测 |
| --- | --- |
| hostname | `cursor` |
| OS | Ubuntu 24.04.5 LTS，kernel 6.12.94+ |
| Python | `/usr/bin/python3`，3.12.3 |
| GPU | 无。`nvidia-smi` 不存在 |

这不是 RTX 5090 32GB 主机，也不是 5060 负对照机。不能把本次结果写成 5090 实测。

## 命令与退出码

工作区在 merge 前 `git status --short` 为空。已 `git fetch origin` 并 `git merge origin/main`（快进，`186e6df` → `0945dfd`）。未 reset、未强推、未在 main 开发。

| 命令 | 退出码 | 原始结果 |
| --- | --- | --- |
| `nvidia-smi --query-gpu=name,memory.total --format=csv` | 127 | `nvidia-smi: command not found` |
| `python3 scripts/remote_preflight.py --label actual-5090 --task-id R0-5090-002 --require-gpu "RTX 5090" --min-vram-mib 30000` | 2 | `hardware_gate.passed=false`；`torch_probe.status=SKIPPED_HARDWARE_GATE_FAILED` |

预检报告：`coordination/returns/20261017T112010Z-actual-5090-1114bdf6/preflight.json`

`hardware_gate.errors` 原文：

```text
nvidia-smi did not return a successful hardware inventory
No single GPU matches the required name and VRAM
```

`gpu` 原文：`FileNotFoundError: [Errno 2] No such file or directory: 'nvidia-smi'`

按任务：“看不到RTX5090及约32GB总显存就停止”；“退出码2意味着硬件检查失败，写回执后停止，不继续安装或下载”。因此下面两条**未执行**：

- `python scripts/gpu_runtime_probe.py --require-gpu "RTX 5090" --min-vram-mib 30000`
- `python scripts/bootstrap_upstreams.py` 以及 `from repro.opi_loader import load_opi_core`

没有第二份 `gpu_runtime.json`，因为 CUDA/NF4 脚本未启动。未使用上次 Cloud 候选 `.venv-r0`（torch 2.7.1+cu128 / transformers 5.20.1），该栈未被协调端认可。

## BF16 / NF4

未执行。硬件门控失败后跳过 torch 探测，无 CUDA 设备，无合成 64×64 NF4。不能从缺包或旧回执推断通过。

## 最小 OPI 导入

未执行。缺包或 loader 报错因此没有新的原始 traceback。需要协调端在真实 5090 主机通过硬件门后再派发导入检查。

## 尚未完成项

- 在真实 RTX 5090（单卡名称匹配且总显存 ≥ 30000 MiB）上重跑本任务
- CUDA 设备 0 的 BF16 矩阵乘
- 合成 NF4 CUDA 权重／量化状态／有限输出
- `load_opi_core()` 最小导入
- 完整模型链路与正式 R0 其余项（本任务本就不覆盖）

下一步：把同一命令放到 5090 电脑本地 Cursor 终端执行。本 Cloud VM 不能通过本任务。
