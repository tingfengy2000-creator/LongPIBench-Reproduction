# Domain–Length–Position Confounding Audit

**结论：DeBERTa 此前长度校准的大部分表观收益，可由领域条件化解释；尚无证据支持开发 LCMD。** 本轮不训练、不实现新防御。结论仅针对既有公开数据的探索性解释，不能外推为长度在所有模型上无价值。

## 核心观察

1. **DeBERTa 的主要新增检出没有长度独占性。**Length Max 相对 Global Max 新增的16条攻击，Domain Max全部也检出。两者在160条历史留出输入上判定一致率95%。Domain Max为TP39/FP9，Length Max为TP32/FP8，实际FPR不同，因此不能把前者较高TPR直接叫作固定FPR优势；判定重合支持的是领域代理解释，不是因果解释比例。
2. **控制领域后，DeBERTa 未出现额外域内排序收益。**Domain+Length对比Domain-only，Email AUROC 0.76625→0.763125，Resume 0.858125→0.8578125；两域AP也下降。AUROC/AP差异的固定校准bootstrap区间均包含0。Domain+Length只改变2条判定，且均是Email攻击由阳性变阴性；良性判定和Resume判定不变。
3. **局部关联不等于可用的额外检测价值。**固定领域和精确Chunk数后，Resume的Token–Max秩关联在DistilBERT（ρ≈0.675，p=0.00025）和Prompt Guard（ρ≈0.723，p=0.00025）仍存在。两模型的一块Resume内部也有关联，不能把一切都归咎于尾块。但内容与长度仍共同变化；这些关联没有证明因果效应，也不直接证明校准能改善检测。
4. **DistilBERT有需保留的局部信号。**Domain+Length在Resume的工作点为TP38/FP2，Domain-only为TP26/FP3，且AUROC轻微增加约0.00344；Email未改善，AUROC/AP差异区间仍包含0，不能称为跨域稳定收益。Domain-only仅覆盖Length Max新增检出的18/31，不能把DeBERTa的解释一概套到DistilBERT。
5. **Prompt Guard尾块关联真实，但机制未识别。**14个多块良性Resume中13个尾块分数高于首块，中位差约0.208；配对符号检验p≈0.00183。尾块长度与尾块分数ρ≈-0.165、p=0.573，没有显示更长尾块更高。所有这些尾块没有起始特殊token、带结尾特殊token，且与512-token首块没有相同长度的对照。内容、长度、位置和特殊token格式的贡献仍未解决。
6. **DistilBERT原作者标签方向已补证。**原作者Space明确LABEL_0=benign、LABEL_1=prompt injection，符合历史LongPIBench映射。32条独立短控制样本中，攻击16/16判阳性、良性11/16误报；作者的Hello、写诗请求、Ignore previous instructions三个示例方向一致。历史标签和所有分数未翻转。高误报应作为行为问题解释。

## 数据、封存与解释范围

主数据为最新960条真实评分：三检测器各320变体、共用160个源。每模型原calibration中仅80个良性源用于新诊断策略的校准（每域40）；原test含80源/160变体，现只用于既有结果解释，不再称为独立测试。未合并旧80条烟测来扩大拟合数据。
开始前对360个既有tracked文件逐一SHA256封存，包含旧评分、阈值、结果和R0–R4代码/配置。原Global/Length阈值及总体/分域混淆矩阵数值完全复现；新参数另存calibration_parameters.json。所有分析结束后再验封。5090 R2未收到新任务，其工作区、Baseline、运行配置和raw均不接触。

## 四种离线策略与公平性

| 策略 | 风险排序量 | 原calibration良性参考 | 阈值 |
| --- | --- | --- | --- |
| Global Max | 原Chunk最大风险分数 | 合并两域80源 | 原合并阈值，原样复现 |
| Domain Max | 原Chunk最大风险分数 | 本域40源 | 本域经验FPR≤10%的独立阈值 |
| Length Max | 原28近邻平滑尾概率的-log10 | 合并80源，按log(1+Chunk数)近邻 | 原留一校准合并阈值，原样复现 |
| Domain+Length Max | 相同尾概率、相同k=28 | 仅本域40源内取28近邻 | 本域留一校准阈值 |

所有阈值、参考样本、邻域规模都在新结果计算前固定；没有按历史留出调阈值。长度变量仍为旧方法的Chunk数代理，不是Token数。Domain+Length固定28邻居是为了不同时改变k；每域40源时近邻已覆盖70%，局部支持有限。所有策略采用原nextafter阈值与严格>，离散尾概率和并列分数可能使校准FPR低于预算。
Domain Max只改变本域阈值，不改变本域排序，因此它与Global Max的域内ROC/PR必然完全重合。这是实现不变量，不是发现“领域没有作用”。跨域合并时领域阈值重新分配误报预算，不能拿不可比的域内原分数拼成一个改进排序。

## 实际校准误报预算占用

| 检测器 | Global Max | Domain Max（Email / Resume） | Length Max | Domain+Length（Email / Resume） |
| --- | --- | --- | --- | --- |
| deberta | 8/80 | 4/40 / 4/40 | 6/80 | 4/40 / 3/40 |
| distilbert | 8/80 | 4/40 / 4/40 | 8/80 | 4/40 / 4/40 |
| prompt-guard | 8/80 | 4/40 / 4/40 | 6/80 | 4/40 / 4/40 |

长度策略为留一校准计数。相同10%上限不代表实际校准FPR完全相同；尾概率离散并列使部分预算未用满。保留原Length参数，未为本轮解释重新优化旧阈值。因此判定重合应与域内整条曲线一起判断，不能仅靠不同工作点推断独立贡献。

## 历史解释性工作点

| 检测器 | 域 | 策略 | TP | FP | TN | FN | TPR | 实际FPR |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| deberta | overall | Global Max | 24 | 8 | 72 | 56 | 30.00% | 10.00% |
| deberta | overall | Domain Max | 39 | 9 | 71 | 41 | 48.75% | 11.25% |
| deberta | overall | Length Max | 32 | 8 | 72 | 48 | 40.00% | 10.00% |
| deberta | overall | Domain+Length Max | 37 | 9 | 71 | 43 | 46.25% | 11.25% |
| deberta | email | Global Max | 21 | 8 | 32 | 19 | 52.50% | 20.00% |
| deberta | email | Domain Max | 15 | 3 | 37 | 25 | 37.50% | 7.50% |
| deberta | email | Length Max | 13 | 3 | 37 | 27 | 32.50% | 7.50% |
| deberta | email | Domain+Length Max | 13 | 3 | 37 | 27 | 32.50% | 7.50% |
| deberta | resume | Global Max | 3 | 0 | 40 | 37 | 7.50% | 0.00% |
| deberta | resume | Domain Max | 24 | 6 | 34 | 16 | 60.00% | 15.00% |
| deberta | resume | Length Max | 19 | 5 | 35 | 21 | 47.50% | 12.50% |
| deberta | resume | Domain+Length Max | 24 | 6 | 34 | 16 | 60.00% | 15.00% |
| distilbert | overall | Global Max | 12 | 6 | 74 | 68 | 15.00% | 7.50% |
| distilbert | overall | Domain Max | 30 | 7 | 73 | 50 | 37.50% | 8.75% |
| distilbert | overall | Length Max | 41 | 7 | 73 | 39 | 51.25% | 8.75% |
| distilbert | overall | Domain+Length Max | 41 | 4 | 76 | 39 | 51.25% | 5.00% |
| distilbert | email | Global Max | 5 | 6 | 34 | 35 | 12.50% | 15.00% |
| distilbert | email | Domain Max | 4 | 4 | 36 | 36 | 10.00% | 10.00% |
| distilbert | email | Length Max | 3 | 2 | 38 | 37 | 7.50% | 5.00% |
| distilbert | email | Domain+Length Max | 3 | 2 | 38 | 37 | 7.50% | 5.00% |
| distilbert | resume | Global Max | 7 | 0 | 40 | 33 | 17.50% | 0.00% |
| distilbert | resume | Domain Max | 26 | 3 | 37 | 14 | 65.00% | 7.50% |
| distilbert | resume | Length Max | 38 | 5 | 35 | 2 | 95.00% | 12.50% |
| distilbert | resume | Domain+Length Max | 38 | 2 | 38 | 2 | 95.00% | 5.00% |
| prompt-guard | overall | Global Max | 11 | 11 | 69 | 69 | 13.75% | 13.75% |
| prompt-guard | overall | Domain Max | 15 | 10 | 70 | 65 | 18.75% | 12.50% |
| prompt-guard | overall | Length Max | 10 | 13 | 67 | 70 | 12.50% | 16.25% |
| prompt-guard | overall | Domain+Length Max | 15 | 15 | 65 | 65 | 18.75% | 18.75% |
| prompt-guard | email | Global Max | 10 | 9 | 31 | 30 | 25.00% | 22.50% |
| prompt-guard | email | Domain Max | 8 | 7 | 33 | 32 | 20.00% | 17.50% |
| prompt-guard | email | Length Max | 6 | 6 | 34 | 34 | 15.00% | 15.00% |
| prompt-guard | email | Domain+Length Max | 8 | 7 | 33 | 32 | 20.00% | 17.50% |
| prompt-guard | resume | Global Max | 1 | 2 | 38 | 39 | 2.50% | 5.00% |
| prompt-guard | resume | Domain Max | 7 | 3 | 37 | 33 | 17.50% | 7.50% |
| prompt-guard | resume | Length Max | 4 | 7 | 33 | 36 | 10.00% | 17.50% |
| prompt-guard | resume | Domain+Length Max | 7 | 8 | 32 | 33 | 17.50% | 20.00% |

这些是校准后锁定阈值在历史留出上的实际计数。不同FPR工作点不可直接作同FPR性能结论；没有把旧留出重新调到恰好10%。域内ROC的TPR@经验FPR≤10%只作为描述性排序包络，不据它选部署阈值。PR中攻击占比固定50%，AP不能外推到低攻击率部署场景。

## Domain+Length 相对 Domain-only 的域内曲线增量

| 检测器 | 域 | ΔAUROC | bootstrap 95%区间 | ΔAP | bootstrap 95%区间 |
| --- | --- | ---: | --- | ---: | --- |
| deberta | email | -0.00312 | [-0.02500, 0.01844] | -0.00921 | [-0.06212, 0.04608] |
| deberta | resume | -0.00031 | [-0.02470, 0.02719] | -0.03137 | [-0.09131, 0.03519] |
| distilbert | email | -0.00469 | [-0.01687, 0.00595] | -0.00126 | [-0.03571, 0.01275] |
| distilbert | resume | 0.00344 | [-0.02063, 0.03469] | -0.01437 | [-0.05832, 0.02696] |
| prompt-guard | email | -0.01531 | [-0.03938, 0.00594] | -0.01416 | [-0.03765, 0.00179] |
| prompt-guard | resume | -0.07656 | [-0.18594, 0.01688] | -0.07392 | [-0.18279, 0.01021] |

区间由2000次同域、按标签分层的配对源文档bootstrap得出；拟合阈值固定，不包含校准样本不确定性，未作多重比较校正。旧留出已经反复用于解释，因此不作确认性显著性或独立泛化声明。

## 长度、位置与内容：能识别什么

| 问题 | 当前证据 | 尚未识别的部分 |
| --- | --- | --- |
| 领域之外是否还有Token相关性 | Resume内且固定Chunk数后，DistilBERT/Prompt Guard仍有相关性；DeBERTa没有稳定关联 | 内容随长度共同变化；相关性不是因果或增量检测价值 |
| Token数和Chunk数能否作为独立因素 | 官方Chunk数=ceil(Token数/512)，是确定关系 | 无法在完全固定Token数时独立改变Chunk数 |
| 文档绝对位置是否直接进入模型 | 官方每块只传局部input_ids，未传文档级位置；重复相同token hash的分数完全一致 | 不同位置的内容与边界格式不同，观察到的位置关联不是独立位置输入效应 |
| 尾块更短是否造成高分 | PG尾块5–443 token，尾长/尾分数关联不显著；Resume尾块与首块无512-token长度重合 | 没有同内容、同长度、同格式的跨位置对照，因果不可识别 |
| 尾块高分是否由显式指令词造成 | PG尾块仅1条含预设词表词且低分，多数高分尾块未命中词表 | 词表不是恶意性或语义真值，不能排除其他内容影响 |
| 特殊token是否影响尾块 | 多块尾块无起始特殊token、均带结束特殊token，首块格式相反 | 未做干预评分，格式贡献未解决，未改官方切块行为 |

精确重建了960条文档的2900个Chunk输入，token hash全部与原始记录一致；未调用模型对历史文档重新评分。词表/数字/标点等内容指标仅作描述，不作为新检测规则。位置表按Chunk给出统计时同时给独立源数，不把Chunk当作独立文档估计显著性。详见position_content_audit.json、chunk_position_strata.csv、resume_tail_cases.csv。

## 标签核验

原作者资料：[固定Space app.py](https://huggingface.co/spaces/fmops/prompt-injection-classifier/blob/ef784e4cadfe184f02683a87a6ad19f565fda9b4/app.py)。其示例模型名为fmops/distilbert-prompt-injection；演示代码明确LABEL_0为benign、LABEL_1为prompt injection。模型本身config仍未给语义id2label，训练标签来源未完全恢复；现已确认公开作者的预期映射。Space只是阅读保存，没有执行。
独立控制样本在本轮推理前冻结，16良性+16显式注入，均短于512 token，用相同本地固定权重CPU FP32真实前向。控制集TP16、FP11、TN5、FN0，不是性能评测集；3个作者示例分别正确识别。所有logits/softmax、文本和hash保留。此证据支持预期方向且揭示误报，不支持根据历史留出或控制集翻转历史标签。

## 决策

**LCMD开发保持NO-GO。**DeBERTa的原观察可以主要由领域条件化说明，加入域内Chunk数条件没有额外排序收益。其他模型中保留局部相关性和DistilBERT Resume的工作点信号，但没有跨域、独立数据上的稳健增量证据。不能写“长度没有任何信息”，也不能写“长度校准已有效”。
下一步仅交付独立数据验证设计，见next_independent_validation_plan.md；本轮不实现、训练或执行其中的新数据干预实验。

## 可复核文件

- audit_results.json：四策略曲线、判定重合、域内关联和bootstrap区间。
- calibration_parameters.json：仅原calibration良性数据拟合的新诊断参数；旧参数不改。
- stratified_comparisons.csv、document_decisions.csv：校准/历史留出的分层计数与逐文档四策略分数、阈值、判定。
- chunk_features.csv、feature_receipt.json：准确token重建与内容代理，未保存文档全文。
- distilbert_label_audit.json、controls_manifest.jsonl、controls_observations.jsonl、source_evidence/：原资料与独立控制证据。
- figures/：三模型分域ROC/PR、域条件增量、Resume尾块与长度PNG/PDF。
- frozen_existing_files.json及completion_receipt.json：旧证据封存与最终验封。

