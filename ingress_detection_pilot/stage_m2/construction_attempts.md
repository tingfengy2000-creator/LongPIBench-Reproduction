# 评分前构造失败记录

首次构造目录`E:\LongPIBench\runs\20261018T152807Z-m2-context-4972b7f6\`保留construction_start.json及已生成的部分frozen_inputs.jsonl，没有任何模型评分。

在prepare.py/witness的前缀解码重分词校验失败：`AssertionError: (434, 103)`。原实现尝试截取目标附近±8个carrier token再decode，某些截断后的重分词不能恰好命中目标offset。

评分前构造修复：前缀先decode到目标前12 token，然后依次增加0–24个普通词record；后缀同理，仍通过完整自然文本tokenization验证，不直接拼造官方全文token ID。达到精确1024和固定核心覆盖才纳入。这个修复只在新M2构造器中进行，Baseline及历史文件无变更。

成功构造Run ID `20261018T152953Z-m2-context-6e5c0c4d`，80变体，完整输入4,696,706字节，旧437文件封存。未观察分数后再修输入；若未来复核需读取原文本，两个目录均保留。
