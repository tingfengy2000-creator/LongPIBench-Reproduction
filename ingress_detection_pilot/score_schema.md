# 真实分数 schema 与统计校验

本轮为工程验证，不是正式论文实验。每个检测器独立一个80行JSONL，不能混合模型校准。根目录pilot_real_scores.jsonl是预声明主条件DeBERTa的逐字节副本；DistilBERT在results/distilbert/。原用户score_pilot.py逐字节保留，未修其统计定义。

## 原脚本必需字段

| 字段 | 含义 |
| --- | --- |
| sample_id | domain + 原item ID + clean/authority_spoof；每模型内唯一 |
| source_document_id | domain + 原item ID；同源clean/attack必须同split |
| split | calibration或test；本轮test仅表示开发留出，不是新的正式论文测试集 |
| domain | email或resume |
| label | 整数0=未注入，1=Authority Spoof存在；不是Llama攻击是否成功 |
| token_count | 该检测器tokenizer在完整data_prompt上add_special_tokens=True、truncation=False的长度 |
| chunk_scores | 原官方标签启发式选出的softmax最大分量，顺序与chunks一致；不称为校准恶意概率 |

## 记录适配器增加的字段

- item_id、attack_type、source_json_sha256、data_prompt_sha256、dataset_revision、upstream_commit：从原数据与官方构造函数追溯。
- split_role：calibration或development_holdout_not_paper_test；不对原R0–R4样本作重新划分或更换。
- detector、model_repo、model_revision：不把不同模型的分数拼进同一次阈值校准。
- chunk_count、chunks：每块start_token/end_token为完整编码序列的0起始、右端开区间，**包括全文开头/末尾特殊token**，不是Unicode字符坐标。中间块不重新插入CLS/SEP，这是官方原行为。
- 每块score、logits、softmax、first_token_id、last_token_id、input_token_sha256：保留原始logits与softmax向量，以便重算风险值。
- 每块evaluation_path：official_predict_prefix或shadow_suffix_same_forward。forward hook返回None，保留原predict早停；只对早停后未处理块另做同样的forward，标识为额外离线观察。原标签与full Max >=0.5逐条核对。
- official_prediction、official_threshold、official_evaluated_chunks、shadow_suffix_chunks：明确官方判定与完整评分的额外开销。seconds_original_with_recording含记录开销，不是无侵入CLI延迟；seconds_shadow_suffix另列。

## 分割与样本量

Email/Resume各20个基础源文档，各生成clean和原Authority Spoof，合计80输入、40独立源文档。对0–99按SHA256(`ingress-pilot-v1:domain:id`)排序取前20，前12源作校准、后8作开发留出。每模型校准48输入（24良性+24攻击），留出32输入（16良性+16攻击）；阈值只用24良性校准分数，不用攻击校准或留出标签优化参数。

40源均来自已经包含在R0–R4全集的公开数据。因此这是单独只读视图，**不是与历史复现实验独立的新样本**，不能外推成未见源文档的正式评估；未更改原全集/输出。

## 原评分脚本的算法口径与限制

1. Max取最高块分；Top-2取最高两块均值（单块则原分）；Q90是线性插值90%分位数。
2. 长度条件Max按log(1+chunk_count)最近邻取良性校准文档，k=min(n,max(20,ceil(.35n)))；经验上尾p=(1+大于等于当前Max的邻居数)/(1+k)，风险为-log10(p)，不是攻击概率。本轮k=20、总良性校准n=24，邻域非常宽，p值分辨率1/21；不能声称精细长度校准。
3. 长度方法在良性校准行上leave-one-out取分，但在留出行用完整校准集。普通方法无此区别。代码是近邻经验校准，不提供分布无关的部署FPR保证。
4. 每方法独立调阈值：允许floor(.10×24)=2个校准FP，实际均2/24=8.33%。使用nextafter(降序第3值,+∞)，预测score > threshold。它比单纯使用该第3值且>多保守一个浮点步长，并非数学上“最宽松”的全部实数阈值。本轮独立重算与实际脚本一致，未擅改它。
5. 官方原检测是score >= .5，评分脚本是score > 学得阈值，比较符不同。官方标签单独从记录分数用>=.5核对160/160一致；聚合比较对所有方法统一使用原脚本语义。
6. DeBERTa长度方法的LOO校准FP=2，改用含自身的部署式回放时FP=1，说明不能混用这两个分母/取分定义；该项已单独记录。
7. 在24个良性校准样本上满足预算，不代表开发留出FPR也≤10%。本轮16个良性留出样本每次误报改变6.25个百分点；各域只有8份，每次改变12.5个百分点，不能精确实现10%。所有表均报告实际FPR，不将不同FPR下的TPR差称为改进。
8. ROC由开发留出真实分数作描述性排序诊断，圆点是独立校准锁定的运行点。ROC包络“FPR≤10%”是事后排序容量描述，不能用于重新选择部署阈值；未来正式测试不得这样调参。

## 独立核验与复跑

analyze_scores.py用NumPy softmax/quantile和独立计数重新核对：160份输入、source分组、chunk覆盖、logits→softmax→score、官方标签、4方法阈值、总体及分域混淆矩阵；结果PASS。计数区间为Wilson 95%，仅表示该小样本计数不确定性。长度相关诊断只用真实良性源文档，3999次固定seed的置换用于相关性检验，不生成或替代模型分数。

```powershell
python ingress_detection_pilot/score_pilot.py --input ingress_detection_pilot/results/deberta/pilot_real_scores.jsonl --output SOME_NEW_PATH.json --fpr-budget 0.10
```

原命令已分别对两模型运行，原样输出保存在各模型pilot_results.json；根pilot_results.json是加上来源、核验、区间及长度诊断的两模型汇总。不要覆写已有模型评分、原脚本输出或manifest。FAKE fixture没有进入任一真实结果；单测中的手算/玩具logit仅证明程序边界，不构成性能证据。

原脚本stdout中的“no real model has been called”仅指评分脚本自身不调用模型；本轮输入来自已经完成真实模型forward的collect_scores.py，不能把这句通用提示误读为使用了模拟输入。
