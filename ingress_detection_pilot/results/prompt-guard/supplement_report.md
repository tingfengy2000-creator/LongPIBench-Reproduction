# Prompt Guard 补充工程验证（2026-10-18）

本补充独立添加，原两套检测器结果及 R0–R4 未改写。本机已登录账号能够访问固定配置与权重；先前匿名 401 不能用于判断该账号没有授权。未记录或提交 token。

## 观测与置信限制

H1 预先定义的支持门槛通过：**False**。门槛要求两个域内良性样本均出现正向长度关联（置换检验 p≤0.025），且存在聚合排序反转。此项是当前样本上的探索性证据门槛，不是证明不存在长度效应。
80 个变体只有 40 个独立源文档；校准为每域 12 个源，开发留出为每域 8 个源，同源 clean/attack 不跨分割。每域留出仅 8 个良性和 8 个攻击，FPR 步长为 12.5 个百分点。即使观察到 0/8 误报，Wilson 95% 上界仍约 32.4%。10% 仅约束校准集经验 FPR，不保证留出或部署 FPR；不能据此声称性能提升或 5% FPR 能力。

## 来源与模型语义

- 输入代码 commit：`b9c3f6df9ab6fd0f92738361ed4d3f12f4dab27b`；冻结样本 SHA256：`5db7630890195015ee27beb1cd172293b3473c764d6e69a0d933438c6dcaf123`。
- 数据：RainWatcher/LongPIBench @ `cdfdfdba8838911ec3d120d5bbf584c0afb280f2`，Email/Resume 每域 20 源及其 clean/Authority Spoof 变体；与原公开复现总体存在重叠，只用于独立开发烟测。
- 模型：`meta-llama/Prompt-Guard-86M` @ `1209add6ca7d9c1d815171b8e5571587fe3e7b03`；运行时 `{"tokenizer_class": "DebertaV2TokenizerFast", "tokenizer_model_max_length": 1000000000000000019884624838656, "architecture_max_position_embeddings": 512, "id2label": {"0": "BENIGN", "1": "INJECTION", "2": "JAILBREAK"}, "device": "cpu", "dtype": "torch.float32", "parameters": 278811651}`。
- 原始类别 0=BENIGN、1=INJECTION、2=JAILBREAK。每块保留 logits、softmax 三分量；官方风险分数为 `max(softmax[1], softmax[2])`，不是两类之和，也不是校准后的文档攻击概率。
- 沿用官方实现：全文一次加特殊 token，再按 512 连续切块，无重叠、无每块额外 CLS/SEP；默认任一块 score≥0.5 则攻击并早停。记录原早停前缀后另作 shadow 后缀前向，获取离线聚合所需完整分数；80/80 的全文 Max 默认判定与原方法一致。
- CPU FP32，4 线程；模型及全部大文件下载、缓存、下载临时文件在 E 盘。没有训练新模型或改检测行为。

## 相同数据、相同检测器上的阈值校准

原始 `score_pilot.py` 先执行，随后独立 NumPy 实现逐项核验阈值与混淆矩阵。每个方法用同一 24 个良性校准文档按 10% 预算调阈值（最多 2/24=8.33% 经验误报）；原默认 0.5 判定另行记录，不作为唯一基线。
长度条件近邻使用 20/24 校准样本，局部支持很弱；校准用留一法、留出用完整校准集，二者离散分布有差异。原脚本 `nextafter` 配合严格 `>` 在浮点边界略保守，保留原实现并独立验证。

| 方法 | 域 | TP | FP | TN | FN | TPR | FPR |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| max | overall | 5 | 2 | 14 | 11 | 0.312 | 0.125 |
| max | email | 2 | 1 | 7 | 6 | 0.250 | 0.125 |
| max | resume | 3 | 1 | 7 | 5 | 0.375 | 0.125 |
| top2 | overall | 4 | 1 | 15 | 12 | 0.250 | 0.062 |
| top2 | email | 2 | 1 | 7 | 6 | 0.250 | 0.125 |
| top2 | resume | 2 | 0 | 8 | 6 | 0.250 | 0.000 |
| q90 | overall | 4 | 2 | 14 | 12 | 0.250 | 0.125 |
| q90 | email | 1 | 1 | 7 | 7 | 0.125 | 0.125 |
| q90 | resume | 3 | 1 | 7 | 5 | 0.375 | 0.125 |
| length_calibrated_max | overall | 5 | 2 | 14 | 11 | 0.312 | 0.125 |
| length_calibrated_max | email | 2 | 1 | 7 | 6 | 0.250 | 0.125 |
| length_calibrated_max | resume | 3 | 1 | 7 | 5 | 0.375 | 0.125 |

## 长度、分块和排序

| 域 | 良性 n | 默认 FP | token–Max Spearman ρ | 双侧置换 p | Max/Top-2 反转对数 | Max/Q90 反转对数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| email | 20 | 0 | 0.17744360902255638 | 0.4435 | 13 | 9 |
| resume | 20 | 1 | 0.8962406015037594 | 0.00025 | 0 | 0 |
| pooled | 40 | 1 | 0.7500938086303941 | 0.00025 | 24 | 9 |

分域、label、chunk 数及 token 长度的分箱分数 min/Q25/median/Q75/max 详见 `independent_audit.json:score_distributions`；完整 ROC 点见 `roc_points.json`，原始逐块区间、logits、softmax 与分数见 `pilot_real_scores.jsonl`。

## Go / No-go

工程记录路径 GO；当前证据不足以推进多尺度或疑难区域复核方法实现，NO-GO。保留真实结果与不确定性，不把排序变化或扩大拒绝比例当作性能提升。

本报告不是正式论文实验；未修改 R0–R4、原始数据、既有输出或原始评分脚本。
