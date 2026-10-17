# R0-5090-001 回执

- 任务：`R0-5090-001`
- 运行 ID：`20261017T101922Z-machine-5090-1bbf8a93`
- 分支：`machine-5090`
- 输入 commit：`baa26d62fc28220478daa4f34b8a9f362b54cec1`
- 阶段：R0 环境预检与固定代码／数据恢复。**未启动正式 R1/R2，未做正式推理，未设计 SALT。**
- 任务状态：**BLOCKED**

不能把本回执写成 RTX 5090 实测，也不能把 CUDA 冒烟、包安装或 200 条哈希当成正式研究结果。

## 判定摘要

固定上游与 200 条 Email/Resume 数据已在本工作区恢复并哈希核对。候选隔离环境已安装，`bitsandbytes` 可导入，`longpibench` 可导入。

硬件与授权检查未通过：

1. 本机 **不是** RTX 5090 32GB。hostname=`cursor`，OS=Ubuntu 24.04.5，KVM 虚拟机，无 `/dev/nvidia*`，`nvidia-smi` 不存在。
2. 候选 torch `2.7.1+cu128` 已安装，但 `torch.cuda.is_available()==False`，CUDA BF16 kernel 与 NF4 GPU 加载均未执行。
3. 本机无 Hugging Face 登录；Llama-3.1-8B-Instruct 固定 revision 的 `config.json` 返回 **401**。未输出任何 token。
4. 本地无 Llama / Mistral / GPT-2 / DataSentinel / PromptLocate 权重。未下载大模型。
5. DataSentinel Table4 的 large/small checkpoint 仍为 **unknown**，未按任何 ASR 挑选。

## 实际命令与退出码

解释器：预检与上游恢复使用 `/usr/bin/python3`（CPython 3.12.3）。隔离环境使用 `/workspace/.venv-r0/bin/python`（CPython 3.11.17，由 uv 提供的独立解释器创建；未改系统 Python，未卸载已有包）。

| 命令 | 退出码 |
| --- | --- |
| `python3 scripts/remote_preflight.py --label machine-5090` | 0 |
| `python3 scripts/bootstrap_upstreams.py --download-data` | 0 |
| `/home/ubuntu/.local/bin/python3.11 -m venv .venv-r0` | 0 |
| `.venv-r0/bin/python -m pip install --upgrade pip` | 0 |
| `.venv-r0/bin/python -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu128` | 0 |
| `.venv-r0/bin/python -m pip install -e '/workspace/upstream/LongPIBench[hf,dev]' --extra-index-url https://download.pytorch.org/whl/cu128` | 0 |
| `.venv-r0/bin/python -m pip install bitsandbytes spacy` | 0 |
| `.venv-r0/bin/python -m spacy download en_core_web_sm` | 0 |

`environment.resolved.txt` 来自 `pip freeze`，已检查无私有 URL／凭据。该锁只记录本候选环境实际版本，**不是已验证的论文环境锁**。

Ubuntu 24.04 apt 无 `python3.11` 包；Conda 不存在。因此用 uv 安装独立 CPython 3.11.17，而不是改系统 Python。

## 硬件

| 项目 | 实测 |
| --- | --- |
| GPU | 无。`nvidia-smi` FileNotFoundError；`/dev/nvidia*` 空 |
| 宣称目标 | RTX 5090 32GB（本机未证实） |
| OS | Ubuntu 24.04.5 LTS，kernel 6.12.94+ |
| CPU | Intel Xeon，4 vCPU，KVM |
| 内存 | MemTotal 16387280 kB（约 16 GiB） |
| 磁盘 | 安装后约 238 GiB 可用（`df` 254G 总量，16G 已用） |

CPU 上 `bfloat16` 矩阵乘可以算出 `64`，这 **不满足** 任务要求的 CUDA BF16 kernel 检查。

## 固定代码与 200 条数据

`bootstrap_upstreams.py --download-data` 打印：`Pinned Email + Resume: 200/200 SHA256 verified`。事后复算：

| 资源 | 锁 | 实测 HEAD | dirty |
| --- | --- | --- | --- |
| LongPIBench | `c7b80114ae56f65fb8019ec82afdb3df91e4ed65` | 相同 | 否 |
| Open-Prompt-Injection | `fbed5cca347488f88363790ae3ae97c56116da6a` | 相同 | 否 |
| RainWatcher/LongPIBench 数据 | `cdfdfdba8838911ec3d120d5bbf584c0afb280f2` | emails 100 + person_info 100，SHA256 200/200 | 无覆盖 |

已有数据与审计快照一致，脚本未改写。`upstream/` 与 `data/` 按 `.gitignore` 不提交。

## 候选环境（未锁定为正式复现栈）

`.venv-r0` 实际版本：

- torch `2.7.1+cu128`（CUDA build 12.8）
- transformers `5.20.1`
- peft `0.21.2`
- bitsandbytes `0.50.2`（可导入；CPU gemm_4bit 提示缺少可选包 `kernels`，未当作 NF4 通过）
- accelerate `1.15.0`
- huggingface-hub `2.2.0`
- spacy `3.8.16` + `en_core_web_sm` `3.8.0`

与 OPI `environment.yml`（Python 3.9.19 / torch 2.3.1 / transformers 4.42.0 / bitsandbytes 0.43.1）不一致。这是兼容候选，不是论文精度条件。

`import longpibench` 成功。`import OpenPromptInjection` 失败：`ModuleNotFoundError: No module named 'google'`（来自 `OpenPromptInjection/models/PaLM2.py`）。未安装 `google-generativeai` / `openai` / `fschat` / `datasets`，以免在无 GPU 主机上继续扩大与旧 OPI 栈的差异。dry-run 显示补齐这些包会把 `fsspec` 从 `2026.7.0` 降到 `2024.3.1`，且仍不保证顶层导入成功。

## CUDA / NF4

- CUDA available：false，device_count=0，arch_list=[]
- CUDA BF16 matmul：未执行
- NF4：debug 合成 `bitsandbytes.nn.Linear4bit(..., quant_type='nf4')`，**因无 CUDA 跳过**。未使用正式样本，未下载公开小模型权重。

## 模型与 adapter

本地 `models/`、`weights/`、`~/.cache/huggingface/hub` 均不存在权重文件。

| 资源 | 状态 |
| --- | --- |
| Llama-3.1-8B-Instruct `@0e9e39f249a16976918f6564b8830bc894c89659` | 未登录；config 401。下载前需在 GPU 主机 `hf auth login`（不要把 token 写入仓库或聊天） |
| Mistral-7B-v0.1 `@27d67f1b5f57dc0953326b2601d68371d40ea8da` | 未认证 config HTTP 200；权重未下载 |
| gpt2 `@607a30d783dfa663caf39e06633721c8d4cfcd7e` | 未认证 config HTTP 200；权重未下载 |
| DataSentinel ZIP | 未下载。large=`detector_large/checkpoint-5000`，small=`detector_small/checkpoint-500`，Table4 选择 unknown |
| PromptLocate oracle ZIP | 未下载 |

GPU 主机在确认磁盘后可用（勿提交权重）：

```bash
# 先登录已获 Llama 授权的账号；不要打印 token
hf auth login
hf download meta-llama/Llama-3.1-8B-Instruct --revision 0e9e39f249a16976918f6564b8830bc894c89659 --local-dir models/Llama-3.1-8B-Instruct-0e9e39f2
hf download mistralai/Mistral-7B-v0.1 --revision 27d67f1b5f57dc0953326b2601d68371d40ea8da --local-dir models/Mistral-7B-v0.1-27d67f1b
hf download openai-community/gpt2 --revision 607a30d783dfa663caf39e06633721c8d4cfcd7e --local-dir models/gpt2-607a30d7
```

Adapter 来源仍是审计记录的 Google Drive 包；下载后应对 ZIP 与 `adapter_model.safetensors` 做 SHA256，并 **同时保留** large/small，禁止按正式 ASR 选 checkpoint。

## 需要协调端处理的问题

1. 本回执来自 Cursor Cloud Agent Linux VM，不是用户指定的 RTX 5090 32GB 主机。R0 GPU／NF4／显存验收必须在真实 5090 上重做。
2. 在 5090 主机用已授权 Hugging Face 账号本地登录后再核验 Llama 访问；不要把 token 交给代理或写入 Git。
3. DataSentinel Table4 checkpoint 仍未知；在找到原配置前保持 unknown。
4. OPI 顶层导入仍缺 Google／OpenAI／fschat／datasets；补齐方案需避免把候选 CUDA 12.8 栈静默降级，且不得改分段／阈值／payload／评分。
5. transformers 5.20.1 相对 OPI 声明的 4.42.0 是方法相容性未知项，不能当作已对齐论文实现。

## 尚未做的后续 R0 项（明确未完成）

- 真实 RTX 5090 识别与显存记录
- CUDA BF16 kernel 通过
- GPU 上 NF4 debug 加载
- 授权后的 Llama 快照、revision、文件 hash
- Mistral / GPT-2 / 两个 LoRA adapter 的完整权重与加载
- OPI 顶层 import 成功
- 任何检测、定位或目标模型推理

## 证据文件

- `preflight.json`：无安装预检（系统 python3.12；当时 upstream 尚未恢复）
- `r0_runtime_probes.json`：venv 内 CUDA／BNB／HF／导入／哈希
- `environment.resolved.txt`：候选环境 freeze
- `install_commands.log`：安装命令记录
