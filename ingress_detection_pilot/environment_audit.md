# 官方检测路径、版本与运行环境审计

日期：2026-10-18。范围：独立H1工程试跑，非正式论文实验；不训练、不开发新防御。R0–R4源码、原数据、既有输出、main及已派发R2任务均未修改。本分支codex/ingress-detection-pilot的新增/变更仅在本目录。

## 当前官方代码

官方main在本轮GitHub API读取中为c7b80114ae56f65fb8019ec82afdb3df91e4ed65，与本机固定上游一致；时间敏感证据保存在source_audit/upstream_current.json。对应[固定detectors.py](https://github.com/liu00222/LongPIBench/blob/c7b80114ae56f65fb8019ec82afdb3df91e4ed65/longpibench/detectors.py)、[cli.py](https://github.com/liu00222/LongPIBench/blob/c7b80114ae56f65fb8019ec82afdb3df91e4ed65/longpibench/cli.py)、[runner.py](https://github.com/liu00222/LongPIBench/blob/c7b80114ae56f65fb8019ec82afdb3df91e4ed65/longpibench/runner.py)。

`longpibench detect`接受alias/model ID、threshold默认0.5、chunk-tokens默认512、start/count，默认100个ID。原构造器直接from_pretrained(model_name)，**没有固定模型revision**；本轮将观察到的HF revision下载为本地目录，再原样调用官方TransformerDetector构造器，版本明确但不反推论文作者当时版本。

原predict只检测data_prompt，不含可信system_prompt。全文tokenizer(add_special_tokens=True,truncation=False)，按512切连续不重叠块，无stride、无每块额外特殊token、无padding/attention_mask补充；原model只收input_ids。每块取logits后按类别softmax，选出id2label名称不属于BENIGN/SAFE/LABEL_0的分量最大值；若没有匹配标签，退回最后一类分量。任一块score>=threshold立即返回1，否则完整遍历后返回0。原CLI只保存文档标签/元数据，不保存全块分数；clean打印FPR，attack打印FNR。

softmax是按类别归一化分数，不等于经过真实文档分布校准的恶意概率。多风险类时取max而非sum：Prompt Guard的Injection和Jailbreak合计分量不能替换官方max。本轮不改这一行为。

## 模型与tokenizer

| alias | 官方repo / 本轮固定revision | 实际tokenizer | 最大长度证据 | 标签/风险分量 | 实际运行 |
| --- | --- | --- | --- | --- | --- |
| prompt-guard | meta-llama/Prompt-Guard-86M @1209add6ca7d9c1d815171b8e5571587fe3e7b03 | API显示DeBERTa-v2家族；tokenizer类/运行实例未验证 | 官方模型卡写512；受保护config未取得，不能声称已核验模型内部配置 | 模型卡描述benign/injection/jailbreak；实际id2label未加载验证 | 匿名config与tokenizer config请求401。Owner要求先完成两公开模型，已暂缓；无分数 |
| deberta | ProtectAI/deberta-v3-base-prompt-injection-v2 @90c9989b1a342275dd0d1a95aad283c04e075671 | DebertaV2TokenizerFast | config max_position_embeddings=512；tokenizer model_max_length为约1e30占位值，**不是支持超长上下文的证据** | 0 SAFE / 1 INJECTION，取class1 softmax | CPU FP32，80份输入，184,423,682参数 |
| distilbert | fmops/distilbert-prompt-injection @c5da1fefd33c98c447b50dd806fe86aeb9e8c26c | DistilBertTokenizerFast | config max_position_embeddings=512；tokenizer model_max_length=512 | config未显式给语义标签，运行时LABEL_0/LABEL_1；按官方启发式取class1，**语义极性没有独立训练标注证明** | CPU FP32，80份输入，66,955,010参数 |

来源：[Prompt Guard固定模型卡](https://huggingface.co/meta-llama/Prompt-Guard-86M/blob/1209add6ca7d9c1d815171b8e5571587fe3e7b03/README.md)、[DeBERTa固定config](https://huggingface.co/ProtectAI/deberta-v3-base-prompt-injection-v2/blob/90c9989b1a342275dd0d1a95aad283c04e075671/config.json)、[DistilBERT固定config](https://huggingface.co/fmops/distilbert-prompt-injection/blob/c5da1fefd33c98c447b50dd806fe86aeb9e8c26c/config.json)。原始API/config/tokenizer文件保存在source_audit；两套公开权重的LFS SHA256、大小和本地实际hash见*-files.json及*-download.json。权重不提交Git。

## 记录适配器边界

collect_scores.py在原model forward加返回None的hook，记录实际input_ids摘要/logits/softmax，不替换原predict。原predict早停后，使用同模型、同切块与同forward另算未访问后缀，明确标shadow_suffix_same_forward，供Max/Top-2/Q90使用；不能说原CLI本来计算了这些后缀。原文档标签与完整Max >=0.5在160/160份记录上一致。DeBERTa完整231次forward=原prefix215+shadow16；DistilBERT237=原prefix80+shadow157。完整风险聚合的额外成本不能冒充原CLI成本。

所有token范围是完整编码序列索引，包括全文特殊token。因为官方只在全文首尾添加特殊token，中间块首部不一定是CLS、尾部不一定是SEP；这是可能影响分类语境的结构因素，未改成“更正确”的分块，也未用本轮结果证明其因果影响。tokenizer的长序列warning不表示模型真的接收了>512块；实际每块最长512，记录已经核验。

## 本机环境与兼容性记录

- 实际执行主机DESKTOP-0JKLMO4 / Windows，Python3.13.9；另有RTX5060 8GB，但本轮安装CPU版torch，未用其GPU，也未占5090。
- 独立ingress_detection_pilot/.venv：torch2.7.1+cpu、transformers4.51.3、tokenizers0.21.1、numpy2.2.6、safetensors0.5.3、sentencepiece0.2.1；完整pip freeze在requirements_cpu_freeze.txt。模型原默认FP32，4个CPU线程，eval/inference_mode，无训练/量化/文本截断。
- 初次venv继承Anaconda system-site-packages，导入时发生重复OpenMP库Error #15，尚未运行检测模型。已关闭venv继承并独立安装依赖，pip check通过；未设置KMP_DUPLICATE_LIB_OK，未改全局环境或R0环境。安装是本轮独立环境兼容准备，不是研究结果。
- 推理前样本/计划/原脚本/适配器提交06c0f476dc1771864773d6aad2d3ed50fa5b8f4f。两个模型completion.json保存实际input_commit、源码/适配器摘要、版本、开始结束时间、原始score文件hash。后来补充本目录.gitattributes保留跨Windows/WSL证据原始字节；不改样本选择、分组或分数。
- 源数据：RainWatcher/LongPIBench @cdfdfdba8838911ec3d120d5bbf584c0afb280f2，Email/Resume原始JSON只读。40独立源文档与原R0–R4全集重叠，不能当新论文测试集；详见sample_manifest.jsonl及pilot_plan.json。

## 当前验收范围

两套公开检测器真实工程跑测完成，原logit/softmax/完整chunk分数和官方判定均保留。Prompt Guard未运行；低FPR部署保证、性能提升、下游LLM的ASR或合法任务质量均未验证。没有实施多尺度覆盖、疑难区域复核或训练。
