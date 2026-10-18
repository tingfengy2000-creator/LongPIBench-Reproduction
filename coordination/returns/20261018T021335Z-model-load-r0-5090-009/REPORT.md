# R0-5090-009 回执

- 输入 commit：e2cd56a58ed8386fd20a7fbb5db10e486423e936
- 主机：DESKTOP-B5PNBNC / Ubuntu-24.04 / longpibench-r0
- 命令：依次独立进程 conda run --no-capture-output -n longpibench-r0 python scripts/local_model_probe.py --role {helper,detector_base,target}
- 总体：三个 role 均为 MODEL_LOAD_AND_SYNTHETIC_CHECK_PASSED
- 仅本地文件，HF_HUB_OFFLINE=1；未下载、未加载 adapter、未跑正式样本、未验证 20k/长上下文。
- 模型、缓存和 E: 链接保持原状。007 未重跑。阻碍：无。

| role | Run ID | 加载条件 | 路径 | 结果 |
| --- | --- | --- | --- | --- |
| helper | 20261018T020943Z-model-load-helper-843313ce | GPT-2 FP32, output_attentions=True | /mnt/e/LongPIBench-Reproduction/models/hf-cache/models--openai-community--gpt2/snapshots/607a30d783dfa663caf39e06633721c8d4cfcd7e | PASSED；model_load/synthetic_forward/short_generation 均为 true |
| detector_base | 20261018T021017Z-model-load-detector_base-fcc4e523 | Mistral NF4 + double_quant + BF16 compute，未加载 LoRA | /mnt/e/LongPIBench-Reproduction/models/hf-cache/models--mistralai--Mistral-7B-v0.1/snapshots/27d67f1b5f57dc0953326b2601d68371d40ea8da | PASSED；nf4_linear_count=224，quant_state 齐全 |
| target | 20261018T021159Z-model-load-target-0178cdd9 | Llama BF16，不量化 | /mnt/e/LongPIBench-Reproduction/models/direct-hf/hf/target | PASSED；embedding_dtype=torch.bfloat16；短生成 READY |

helper 进程有 transformers 关于 output_attentions / eager attention 的警告，未改依赖或精度。本次 8 token 短生成不是正式推理。
