# Stage R0：环境与模型审计

## 结论

**单张 RTX 5090 32GB 有合理的运行可行性，推荐分阶段加载模型、batch size=1；尚未做 GPU 实测，不能承诺峰值显存或耗时。本机实测为 RTX 5060 8GB，不能把本机审计写成 5090 验证。**

本轮不需要商业模型 API，不需要训练。Hugging Face 下载权限与商业推理 API 是两回事；Llama 下载需要已获授权的账号。若拿不到官方适配器，不以重新训练模型冒充原基线。

## 当前实机证据

来源：`evidence/environment.json`，仅审计当前 PowerShell 中的 Python，不代表扫描了所有 Conda 环境。

| 项目 | 本轮观测 |
| --- | --- |
| GPU | NVIDIA GeForce RTX 5060，8151 MiB 总显存 |
| 驱动 | 616.92；nvidia-smi 显示的 CUDA 驱动能力不是已安装 PyTorch 的 CUDA 版本 |
| Python | `D:\anocanda\python.exe`，3.13.9 |
| 核心包 | 当前解释器未安装 torch、transformers、peft、bitsandbytes、huggingface-hub、spaCy |
| pytest / NumPy | 8.4.2 / 2.3.5 |
| WSL | 本轮查询返回 E_ACCESSDENIED；无法据此断言 WSL 未安装或无 Ubuntu |
| 研究目录 | `E:\LongPIBench`，初始为空 |
| PDF 检查 | 使用 Codex 附带 Python 的 pypdf 提取；Poppler 渲染并目视检查原论文第 8 页 Table 4 |

## 固定的公开快照

以下是**审计时获取的快照**，不是论文作者已经披露的实验版本。

| 资源 | 版本 |
| --- | --- |
| LongPIBench 代码 | `c7b80114ae56f65fb8019ec82afdb3df91e4ed65` |
| Open-Prompt-Injection 代码 | `fbed5cca347488f88363790ae3ae97c56116da6a` |
| RainWatcher/LongPIBench 数据 | `cdfdfdba8838911ec3d120d5bbf584c0afb280f2` |
| Llama-3.1-8B-Instruct 元信息 | `0e9e39f249a16976918f6564b8830bc894c89659` |
| Mistral-7B-v0.1 元信息 | `27d67f1b5f57dc0953326b2601d68371d40ea8da` |
| GPT-2 元信息 | `607a30d783dfa663caf39e06633721c8d4cfcd7e`，规范仓库 `openai-community/gpt2`，官方定位器默认名称为 `gpt2` |
| LongPIBench 论文 | arXiv:2608.28411v1，2026-08-28 |
| PromptLocate 论文 | 已下载 PDF 页内标识 arXiv:2510.12252v2，2025-10-17；下载链接未指定版本，留存文件 SHA256 |

模型权重尚未完整下载。需要在真实运行机器再次记录加载的本地 snapshot、tokenizer/chat template、generation_config 和文件校验和，不能仅凭模型名称宣称版本一致。

## 模型角色与权重核验

| 角色 | 实现及权重 | 核验程度 |
| --- | --- | --- |
| 下游任务模型 | `meta-llama/Llama-3.1-8B-Instruct` | HF 元信息可访问，gated=manual；未认证 config 请求返回 401，未核验用户已有权限 |
| 全文检测器 | Mistral-7B-v0.1 + DataSentinel LoRA | 官方 ZIP 可返回 HTTP 206 与 ZIP 头，已读中央目录和 adapter JSON |
| 定位 oracle | Mistral-7B-v0.1 + PromptLocate 专用 LoRA | 同上；**不是直接复用全文检测器的适配器** |
| 第三步辅助模型 | GPT-2 | 官方定位源码默认值，HF 元信息可访问；未加载权重 |
| 分句资源 | spaCy + `en_core_web_sm` | 当前未安装；OPI environment.yml 也未列出 spaCy，需要补齐 |

DataSentinel ZIP 共 **1,401,845,934 bytes**，包含 `detector_large/checkpoint-5000` 与 `detector_small/checkpoint-500`。公开 LongPIBench 代码没有指定 Table 4 使用哪一个，不能依据结果挑选。两者 adapter JSON 的基座均为 `mistralai/Mistral-7B-v0.1`，LoRA r=32、alpha=64。

PromptLocate ZIP 共 **701,657,336 bytes**，适配器目录是：

```text
7_1000_naive_minimax_mistral_3_1_backend_llama3_revise_beta_1_balance_finetune/checkpoint-500
```

其 adapter JSON 同样指定 Mistral-7B-v0.1、r=32、alpha=64。每份 `adapter_model.safetensors` 解压体积为 **864,513,616 bytes**，并非可忽略的小文件。通过 HTTP Range 仅读取了两个 ZIP 合计 7,928 bytes 的目录与 JSON；没有读取权重张量，也未完成 safetensors 完整性或加载兼容性验证。详见 `evidence/adapter_metadata.json`。

## 5090 32GB 运行方案与显存估算

估算不是实测：8B 模型 BF16 权重约 16 GB（约 14.9 GiB，实际以模型参数为准）。OPI 的两个 Mistral 实例各自使用 NF4、double quant、BF16 compute，另有适配器、激活、KV cache 和 CUDA 开销。不能只把 7B×0.5 byte 当作完整显存需求。

Llama 3.1 8B 的常见 BF16 KV 配置下，按 32 layers×8 KV heads×128 head dimension×K/V 2×2 bytes 估算，每 token 128 KiB；额外生成 20,000 tokens 的 cache 约 2.44 GiB，另加输入 cache。需以实际 config、缓存类型和 attention 实现复核。

建议流水线：

1. 单独加载 DataSentinel，完成全文检测并落盘后释放。
2. 加载定位 oracle + GPT-2，仅对已触发记录定位，保存完整轨迹后释放。
3. 加载 Llama，按同一顺序运行无防御及防御后输入；两组使用相同目标参数。

这样避免 Llama、两份 Mistral 和 GPT-2 同时常驻。每一步记录显存峰值；分批加载属于执行方式变更，要记录 RNG 初始化、执行顺序和解码参数，验证不会静默更改输出条件。共享同一 Mistral 基座切 adapter 可作为后续工程适配，但必须先对照独立实例，不能默认等价。

当前 8GB 机器仍可做数据、评分器、输入构造、日志及部分受限推理检查。CPU offload 或目标模型量化或许能运行，但不能把这些未经验证的条件写成原论文精度条件的严格复现。

## 依赖与安装建议

LongPIBench 需要 Python>=3.10，HF extra 要求 transformers>=4.51、torch>=2.2、accelerate>=1.6、peft>=0.11。OPI 的 Linux 导出环境则固定 Python 3.9.19、torch 2.3.1、CUDA 12.1 相关库、transformers 4.42.0、peft 0.11.1、bitsandbytes 0.43.1。这两份声明不能原样合并，旧 GPU 栈也不能直接视为 RTX 50 系列可用。

在真实 Linux/WSL GPU 主机新建 Python 3.11 隔离环境，以官方提供的 CUDA 12.8 PyTorch wheel 为兼容候选，先执行 CUDA tensor 与 NF4 小模型检查，再安装 LongPIBench 与 OPI 所需包。候选例：

```bash
python3.11 -m venv .venv-r0
source .venv-r0/bin/activate
python -m pip install --upgrade pip
python -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -e './upstream/LongPIBench[hf,dev]'
# 以下依赖先做兼容性验证，随后锁定实际版本，不能称为已验证环境。
python -m pip install bitsandbytes spacy
python -m spacy download en_core_web_sm
python -m pip freeze > environment.resolved.txt
```

OPI 顶层 import 会连带导入 Google SDK、OpenAI、fastchat、datasets 等模块；只安装上面这些包不保证 `import OpenPromptInjection` 成功。需要根据实际 import 结果做最小依赖补齐，或采用记录差异的延迟导入适配；不要强行升级到不兼容的 datasets 大版本（存在 `datasets.tasks` 老接口）。本轮没有安装或验证该候选栈。

官方兼容性依据：[PyTorch wheel 列表](https://pytorch.org/get-started/previous-versions/)、[bitsandbytes 安装文档](https://huggingface.co/docs/bitsandbytes/main/en/installation)。安装前仍需检查所选 bitsandbytes wheel 的 GPU 架构支持；最终以本机 kernel/NF4 冒烟检查为准。

## 许可与访问边界

两份官方代码为 MIT；数据卡为 MIT；Mistral 元信息为 Apache-2.0；GPT-2 元信息为 MIT；Llama 为 Llama 3.1 社区许可且有访问门槛。这是资源元数据核对，不是对具体用途的法律结论。独立 Drive 适配器包的使用／再分发条款仍需查包内说明，不能由代码 MIT 自动推定所有权重都是 MIT。

来源：[Llama 模型卡](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct)、[Mistral 模型卡](https://huggingface.co/mistralai/Mistral-7B-v0.1)、[GPT-2 模型卡](https://huggingface.co/openai-community/gpt2)、本地两仓库 LICENSE、`evidence/*model_info.json`。
