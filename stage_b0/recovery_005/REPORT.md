# B0-5090-004部分结果接收与005接续准备

状态：`PARTIAL_RECEIPT_ACCEPTED_CACHED800_RAW_VERIFICATION_REQUIRED`。原004提交204867e已快进接入，实际仅新增5个回执，不覆盖原数据、程序、计划或模型。PIGuard/PG1各400条VALID、DataSentinel0、Llama未启动，与监督汇总及逐文件摘要清单一致。协调端目前没有读取5090完整800条raw，不将清单核验写成已独立核验全部分数。

## 失败判断及责任范围

004新增的工程结构检查使用`type(m).__name__ == 'Linear4bit'`。固定PEFT0.15.2的LoRA包装类与bitsandbytes0.46.1的原生量化类同名，按短类名判断不能区分二者，会将包装与其base_layer重复计算。这是协调端新增检查中的缺陷，不是PromptLocate算法修改或已确认的模型检测失效。

原生类身份应使用`isinstance(m, bnb.nn.Linear4bit)`；历史已通过的aux_runtime_probe.py就是这个标准。新增回归用例表明224个原生层加224个同名包装可让旧选择器数出448，而真实类型筛选得到224。固定源码依据：[PEFT v0.15.2](https://raw.githubusercontent.com/huggingface/peft/v0.15.2/src/peft/tuners/lora/bnb.py)、[bitsandbytes 0.46.1](https://raw.githubusercontent.com/bitsandbytes-foundation/bitsandbytes/0.46.1/bitsandbytes/nn/modules.py)。

但004没有保存实际层计数、generation diff或断言行号，不能将静态缺陷当作旧进程唯一根因已证实。其余候选包括适配器或generation检查。005会在任何断言及候选前向之前保存完整结构审计，并为失败记录文件/行号/函数；只有实际新证据能确认是否为同名重复计数。

## 最小接续范围

- 原scoring_v2/collect.py和execution_plan.json完全不改；在本独立分支增加collect_005.py及显式diff，derivation.json记录基线与新增源摘要。
- DataSentinel仅替换前向前结构识别检查、保存断言证据；原构造、权重、NF4/BF16、query/generate、预热、文本、评分、种子与记录代码不变。原生层数量仍要求224，quant_state、CUDA及BF16仍严格检查，不放宽为任意数量。
- Llama的实际collect_llama函数AST与004相同，B4/B5提示、192预算等全部沿用。005仅接续未开始的800条。
- 在新增前向前，005先只读核验004的全部raw摘要，再对800条分类器记录重建token窗口、校验softmax/Max算数和输入标签匹配。该机器检查包含留出raw的格式/算数，不显示标签关联性能、不拟合阈值，不调用模型前向。若旧raw不完整或不一致，先停止。
- 新增只运行DataSentinel400及Llama800，使用全新Run ID、E盘raw目录与小型回执。原800不重跑，旧失败不改为成功，PG2不重试。

004的800与005的1200在后续只能按明确来源和共享配置拼接，不冒充同一次原进程。跨运行耗时、代码检查差异单列。B0指标仍待完整raw核验、开发阈值冻结及独立留出汇总；没有算法收益结论。

与论文Resume干净7%/本地82%的溯源问题独立：本次空断言修复不是对那75个百分点差异的解释，也不修改历史R1/R2。
