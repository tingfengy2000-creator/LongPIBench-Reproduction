# 00 环境与封存

本阶段为人工构造小样本机制探索；40基础源、80良性/攻击变体，每个条件共享这些源。不是自然业务分布、不是正式论文测试或算法收益证明。

输入冻结提交：ccdd523；分析及烟测提交：88356a9；真实完整运行输入提交：88356a932a74fc50e6a19fdbc3688de4c7c19ee9。
构造Run ID：20261018T152953Z-m2-context-6e5c0c4d；4源烟测Run ID：20261018T153058Z-m2-smoke-21ce25f1；完整Run ID：20261018T153419Z-m2-full-974bbbce。
所有Run ID使用UTC；用户当地日期按Asia/Tokyo为2026-10-19。

固定模型：meta-llama/Prompt-Guard-86M@1209add6ca7d9c1d815171b8e5571587fe3e7b03。权重/Tokenizer文件逐项沿既有download receipt SHA256验证；model.safetensors SHA256=1771712866662626517f2d85057de2d7078389a4c1f0bc93e461bdc4fdae4bd5。模型和Tokenizer均已在E盘，不下载新文件。

原始LongPIBench commit=c7b80114ae56f65fb8019ec82afdb3df91e4ed65，detectors.py SHA256=0f48ab6d307576096c4d07021f78c2d587261af80ca0f315af84a714607f43af。风险=max(softmax[INJECTION],softmax[JAILBREAK])，非二者之和、非校准概率。文档阈值原样>=0.5，512非重叠切分、整文一次CLS/SEP、不逐块加特殊token，仅input_ids前向。

机器DESKTOP-0JKLMO4，Python 3.13.9 | packaged by Anaconda, Inc. | (main, Oct 21 2025, 19:09:58) [MSC v.1929 64 bit (AMD64)]。运行库：{"torch": "2.7.1+cpu", "transformers": "4.51.3", "tokenizers": "0.21.1", "numpy": "2.2.6", "safetensors": "0.5.3"}。FP32 CPU、4线程、eval、inference_mode；torch CUDA=None，CUDA可用=False。本机GPU盘点：name, memory.total [MiB], driver_version
NVIDIA GeForce RTX 5060, 8151 MiB, 616.92。保留M1相同CPU/FP32路径，不声称使用5090。

4源8变体烟测176次前向；完整40源80变体1760次前向，循环耗时937.91秒。烟测只作工程门，不拼接正式面板、不按分数调条件。构造阶段一次失败保留于construction_attempts.md所列ignored目录；没有模型失败被删除。

437个既有tracked文件逐字节验封，包括M1、原960分数/参数/历史输出、R0–R4源码与配置。未访问5090、未向其发任务、未改变main或machine-5090。无训练、LCMD、多尺度或新防御模块。

完整冻结输入：E:/LongPIBench/runs/20261018T152953Z-m2-context-6e5c0c4d/frozen_inputs.jsonl（SHA256 3a489dca282189431127367a93d709535e9e325f18ed18a472e2c80e7874a255）。原始评分：E:\LongPIBench\runs\20261018T153419Z-m2-full-974bbbce\observations.jsonl（SHA256 79fe6b6a8ecd334069b98be24a67f69acec6d16b7a2d76408a9a6ed29862e176）。输入全文/token/logits较大，按协议留本机E盘ignored runs；Git保存manifest、生成代码及小型结果，不能把小型回执当成完整原始数据备份。

独立数值/ID/统计核验见verification_full.json。区间按基础源成组重采样，良性与攻击同抽；同源条件不算独立样本。Bootstrap在全0/全1情形会退化，不能据此宣称母体误差为0。共同作者、载体重复及固定攻击模板也削弱传统独立抽样解释。
