# G0控制冻结与兼容性说明

原`control_protocol.md`在历史G0回执前已写定4源、2固定payload、共同长度规则、26查询上限及不匹配处理；本轮不改旧文件、不看新控制输出改条件。

实现上的“正文token前缀”明确选用原DataSentinel预处理后的clean正文，再按无BOS的固定Mistral fast tokenizer取前缀、decode；payload原文不变，之后仍完整执行原检测预处理。M=323，规则给出128/320两档。8组同payload跨域配对的最终完整prompt长度差均为0，全部保留。没有为了匹配而换源或换长度。

协调端只下载约2.3MB固定tokenizer/config到E盘ignored `runs/g0_fixed_mistral_tokenizer/`，SHA与已验收下载回执一致。未下载权重、触碰C盘缓存或改变M1/M2环境。

最初本机冻结脚本要求所有tokenizer包版本相同，在发现本机sentencepiece0.2.1与原GPU环境0.2.0不同后，在输出前停止；并非数据失败。尝试在E盘隔离overlay安装0.2.0时，该旧版本无当前Windows Python3.13匹配wheel，源码构建因缺少构建工具失败。没有升级、卸载或替换既有环境；临时构建仅在E盘。

随后限定本机复核为`tokenizer.json`的fast路径：transformers4.51.3、tokenizers0.21.1均与历史一致；不使用slow SentencePiece转换。该本机限定差异保存在`history_review.json`，并以全部400个历史实际输入token摘要逐个相等作为实证验证，再冻结26个输入。没有将此本机兼容性范围扩展到模型运行。5090继续使用原完整环境，包括sentencepiece0.2.0，不改任何依赖或精度。

冻结时模型加载数=0、模型前向数=0；模型结果均待G0-5090-002。4个自然完整条件会与既有历史token输出作描述性对照，差异照实保留，不据此删除或重试控制样本。
