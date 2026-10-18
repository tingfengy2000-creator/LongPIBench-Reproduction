# 009协调端审查：三模型GPU工程检查

来源提交：101c124898f3b0c2600e4b755e338bfb2b436586；执行输入：e2cd56a58ed8386fd20a7fbb5db10e486423e936。结论：COMPLETED_MODEL_LOAD_AND_SYNTHETIC_CHECK_ONLY。通过Git获取并审查原始JSON，不声称协调端远程执行或直接读取远端权重。

三个JSON均记录DESKTOP-B5PNBNC/Linux、5090/32607MiB、候选版本和固定模型revision。model_load_verified、synthetic_forward_verified、short_generation_verified及finite_logits为true；formal_samples_used、formal_inference_executed、adapter_loaded、download_executed及long_context_or_20000_token_budget_verified为false。源006/008回执SHA256与仓库原始字节一致，生成均不超过8 tokens。检查仅复用已验收完整文件hash并复查当前大小，不重读31GB全量hash。

| role | Run ID | 核验结果 | 峰值已分配GiB |
| --- | --- | --- | --- |
| helper | 20261018T020943Z-model-load-helper-843313ce | FP32；attentions_returned=true；CUDA有限logits及8 tokens | 0.488 |
| detector_base | 20261018T021017Z-model-load-detector_base-fcc4e523 | 224个NF4层、quant_state齐全；BF16 compute；非量化embedding实际FP16；8 tokens | 6.744 |
| target | 20261018T021159Z-model-load-target-0178cdd9 | BF16无量化；CUDA有限logits；生成READY和eot共2 tokens | 15.014 |

显存为该短合成输入的torch peak_allocated；不是总进程显存或长上下文容量。加载时间包含E盘读取，不是定位算法延迟。helper报告attention警告且实际返回attention；保持原状，不自动改eager或依赖。完整stderr未随本次四个文件提交，当前不能逐字核验警告全文。

## 输入格式发现与修正边界

原target synthetic_prompt只有一个模板BOS，但input_token_ids以128000、128000开头。协调端检查代码确认apply_chat_template(tokenize=False)后tokenizer再次添加默认special tokens。检查脚本已改为target显式add_special_tokens=False并记录tokenization参数，保留helper/Mistral普通文本默认行为。依据：[Transformers 4.51.3聊天模板说明](https://huggingface.co/docs/transformers/v4.51.3/chat_templating#model-training)。这项修正只涉及协调端debug检查工具，不改固定上游、原始回执或正式实验条件。离线回归验证单BOS及普通文本默认行为；尚无修正后真实Llama tokenizer/GPU回执，009不自动重跑。

因此原009仍接受模型GPU加载、有限logits及短生成，不能当作正式target消息格式验收。完整接线时需对照实际chat-template token IDs、角色边界和stop reason另验。没有据此计算ASR或选择模型/adapter。

本轮协调端验证：`python -m pytest tests/test_local_model_probe.py -q --basetemp .pytest-local-model-bos-20261018-unique -p no:cacheprovider`，4 passed。新增用例用tokenizer替身重现重复BOS并验证修正；这不是实际HF tokenizer或GPU通过证据。原有硬件拒绝与移动缓存路径保护测试也通过。

## 原始Git blob保留

- coordination/returns/20261018T020943Z-model-load-helper-843313ce/model_load.json：b8a3ce1f8f9fa5b4ced2439e2b19e42d467079d9
- coordination/returns/20261018T021017Z-model-load-detector_base-fcc4e523/model_load.json：ac15192521c87bc867320ab9f2f239d17d04adcc
- coordination/returns/20261018T021159Z-model-load-target-0178cdd9/model_load.json：318060e1da8957793a7bced2f4b1b4fb3515a10a
- coordination/returns/20261018T021335Z-model-load-r0-5090-009/REPORT.md：938ea7f9cf36b56ce0e251f9856a4fd08ca2e148

来源只新增上述四个小文件，无代码/配置变更，凭据模式扫描未命中。正常merge保留101c124祖先关系，执行端可快进main；不重写回执历史。

下一步为现有007资源准备，复用已有下载。之后另行派发adapter提取/加载及spaCy安装/原初始化检查。DataSentinel large/small继续unknown，禁止根据正式ASR挑选。R0整体、R1/R2及R3/R4均不由本检查自动验收。
