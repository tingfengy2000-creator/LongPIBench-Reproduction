# M1 环境与不变项

Run `20261018T134643Z-m1-boundary-efd3eb5b`，输入提交`e43a80b21ae9e9b5142cb2097b10df1435c2556c`，本机`DESKTOP-0JKLMO4`，仅CPU推理。Python3.13.9；torch2.7.1+cpu、transformers4.51.3、tokenizers0.21.1、numpy2.2.6、safetensors0.5.3。分析另用现有D盘Python、numpy/scipy/matplotlib，不安装依赖。

Prompt Guard固定`meta-llama/Prompt-Guard-86M@1209add6ca7d9c1d815171b8e5571587fe3e7b03`，文件在`E:\LongPIBench\ingress_detection_pilot\models\prompt-guard`，沿用原download receipt逐文件SHA256检查。别名86M不代表本次实际参数量（既有运行审计为278,811,651参数）。架构DebertaV2ForSequenceClassification，最大位置512；FP32 eval，无量化，无训练，无attention_mask，原始input_ids前向。

DebertaV2TokenizerFast；CLS/BOS=1，SEP/EOS=2，PAD=0。tokenizer的巨大model_max_length占位值不能当作模型支持长度。官方整文加CLS/SEP后直接512切片，不给每个块重新包特殊token。风险取INJECTION/JAILBREAK两个softmax值的最大，原阈值>=0.5，非校准概率。

本轮216条格式记录和72条官方文档记录共336次前向，循环83.6968秒；未复用历史得分代替新推理。原predict由只记录hook观察，提前退出后的影子后缀明确标记；full Max判定与原predict72/72一致。本轮自然文档误报的尾块实际参与原predict。

所有模型、缓存、临时文件在E盘；未下载新权重。40条候选资料仅tokenize/查重，无检测器前向；大于512的tokenizer提示不是本轮模型截断或超长前向。候选预览含个人资料原文，只留E盘缓存，不提交Git。

405个历史tracked文件在评分前后与交付前SHA256一致，范围包括旧960评分/校准/结果和既有源码配置。模型文件另对既有receipt验hash。5090无连接或任务派发，R2工作区完全不接触。独立分支`codex/stage-m1-boundary-mechanism`，没有兼容性补丁或方法行为修改。

核验：`verification.json`独立用Python64 exp/归一化重算风险，与FP32记录最大差2.254e-8；输入ID/hash、固定核心覆盖、原Max判定、配对中位数及组合数符号检验均通过。图`mechanism_panel.png`已目视检查，标明阈值、24源配对和构造数据限制。
