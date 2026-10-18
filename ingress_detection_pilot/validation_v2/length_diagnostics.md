# 扩大验证：H1 长度关联与公平校准

本轮仅扩大证据，不训练、不实现新防御。与上一轮40源烟测无交集，来自同一公开总体剩余160源；不是新的独立论文测试。每检测器320个clean/Authority Spoof变体，每域40源校准、40源留出；每方法只用80个良性校准文档设阈值，随后锁定。

## 观测结果与置信限制

同一检测器、同一数据采用相同10%校准经验FPR预算，留出报告实际FPR。不同观察FPR的TPR不能直接证明某聚合更好。留出总体80个良性，域内各40个；仍不能保证5%或10%部署FPR。所有比例的Wilson区间保留于JSON。

| 检测器 | 方法 | 域 | TP | FP | TN | FN | TPR | FPR |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| deberta | max | overall | 24 | 8 | 72 | 56 | 0.3000 | 0.1000 |
| deberta | max | email | 21 | 8 | 32 | 19 | 0.5250 | 0.2000 |
| deberta | max | resume | 3 | 0 | 40 | 37 | 0.0750 | 0.0000 |
| deberta | top2 | overall | 24 | 8 | 72 | 56 | 0.3000 | 0.1000 |
| deberta | top2 | email | 21 | 8 | 32 | 19 | 0.5250 | 0.2000 |
| deberta | top2 | resume | 3 | 0 | 40 | 37 | 0.0750 | 0.0000 |
| deberta | q90 | overall | 23 | 7 | 73 | 57 | 0.2875 | 0.0875 |
| deberta | q90 | email | 20 | 7 | 33 | 20 | 0.5000 | 0.1750 |
| deberta | q90 | resume | 3 | 0 | 40 | 37 | 0.0750 | 0.0000 |
| deberta | length_calibrated_max | overall | 32 | 8 | 72 | 48 | 0.4000 | 0.1000 |
| deberta | length_calibrated_max | email | 13 | 3 | 37 | 27 | 0.3250 | 0.0750 |
| deberta | length_calibrated_max | resume | 19 | 5 | 35 | 21 | 0.4750 | 0.1250 |
| distilbert | max | overall | 12 | 6 | 74 | 68 | 0.1500 | 0.0750 |
| distilbert | max | email | 5 | 6 | 34 | 35 | 0.1250 | 0.1500 |
| distilbert | max | resume | 7 | 0 | 40 | 33 | 0.1750 | 0.0000 |
| distilbert | top2 | overall | 14 | 7 | 73 | 66 | 0.1750 | 0.0875 |
| distilbert | top2 | email | 10 | 7 | 33 | 30 | 0.2500 | 0.1750 |
| distilbert | top2 | resume | 4 | 0 | 40 | 36 | 0.1000 | 0.0000 |
| distilbert | q90 | overall | 18 | 8 | 72 | 62 | 0.2250 | 0.1000 |
| distilbert | q90 | email | 10 | 8 | 32 | 30 | 0.2500 | 0.2000 |
| distilbert | q90 | resume | 8 | 0 | 40 | 32 | 0.2000 | 0.0000 |
| distilbert | length_calibrated_max | overall | 41 | 7 | 73 | 39 | 0.5125 | 0.0875 |
| distilbert | length_calibrated_max | email | 3 | 2 | 38 | 37 | 0.0750 | 0.0500 |
| distilbert | length_calibrated_max | resume | 38 | 5 | 35 | 2 | 0.9500 | 0.1250 |
| prompt-guard | max | overall | 11 | 11 | 69 | 69 | 0.1375 | 0.1375 |
| prompt-guard | max | email | 10 | 9 | 31 | 30 | 0.2500 | 0.2250 |
| prompt-guard | max | resume | 1 | 2 | 38 | 39 | 0.0250 | 0.0500 |
| prompt-guard | top2 | overall | 16 | 17 | 63 | 64 | 0.2000 | 0.2125 |
| prompt-guard | top2 | email | 15 | 15 | 25 | 25 | 0.3750 | 0.3750 |
| prompt-guard | top2 | resume | 1 | 2 | 38 | 39 | 0.0250 | 0.0500 |
| prompt-guard | q90 | overall | 13 | 13 | 67 | 67 | 0.1625 | 0.1625 |
| prompt-guard | q90 | email | 10 | 10 | 30 | 30 | 0.2500 | 0.2500 |
| prompt-guard | q90 | resume | 3 | 3 | 37 | 37 | 0.0750 | 0.0750 |
| prompt-guard | length_calibrated_max | overall | 10 | 13 | 67 | 70 | 0.1250 | 0.1625 |
| prompt-guard | length_calibrated_max | email | 6 | 6 | 34 | 34 | 0.1500 | 0.1500 |
| prompt-guard | length_calibrated_max | resume | 4 | 7 | 33 | 36 | 0.1000 | 0.1750 |

## 留出良性长度诊断

| 检测器 | 域 | n | token–Max ρ | 双侧置换 p | 默认 FP | Max/Top-2 反转 | Max/Q90 反转 | 多块文档 | 尾块为最大值 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| deberta | email | 40 | -0.0786 | 0.63275 | 6 | 13 | 14 | 40 | 24 |
| deberta | resume | 40 | 0.2723 | 0.092 | 0 | 17 | 7 | 3 | 3 |
| deberta | pooled | 80 | 0.3466 | 0.00225 | 6 | 86 | 57 | 43 | 27 |

deberta：H1 预定义留出支持门槛 = **False**。
| distilbert | email | 40 | 0.0358 | 0.8245 | 40 | 56 | 51 | 40 | 22 |
| distilbert | resume | 40 | 0.7563 | 0.00025 | 40 | 116 | 106 | 4 | 0 |
| distilbert | pooled | 80 | 0.8473 | 0.00025 | 80 | 178 | 163 | 44 | 22 |

distilbert：H1 预定义留出支持门槛 = **False**。
| prompt-guard | email | 40 | -0.0505 | 0.74925 | 12 | 51 | 39 | 40 | 16 |
| prompt-guard | resume | 40 | 0.9121 | 0.00025 | 2 | 0 | 0 | 14 | 13 |
| prompt-guard | pooled | 80 | 0.7096 | 0.00025 | 14 | 89 | 67 | 54 | 29 |

prompt-guard：H1 预定义留出支持门槛 = **False**。

门槛沿用原规则：同一检测器在两个域内均ρ>0且双侧置换p≤0.025，并在各域出现至少一次Max/Top-2或Max/Q90排序反转。复核样本仅使用本轮留出良性源；校准集关联另存，仅作描述。三检测器为探索性复核，不据此作家族层面的确认性显著性结论。
原scorer使用nextafter后的严格>判定，浮点边界略保守；保留原实现并独立核验。长度条件Max从80个良性校准源取28个近邻，留一校准也取28个，p值分辨率为1/29；这种近似局部校准没有总体FPR保证。领域、内容和块位置可能混杂；单纯更长或尾块得分高不能证明长度导致误报。DistilBERT官方LABEL_1的语义仍未确认，保留原行为，不能为得到好结果翻转类别。

## 复核与来源

数据 revision：`cdfdfdba8838911ec3d120d5bbf584c0afb280f2`；上游 commit：`c7b80114ae56f65fb8019ec82afdb3df91e4ed65`；样本清单 SHA256：`ea1a4b68647681fcdfa53fd64e2164902165eafd8fbb779dbd6e0bdde7f9be74`。
完整模型版本、环境、输入commit和源码hash见 `results/<detector>/manifest.json` / `completion.json`。Windows UTF-8启动前失败及修复diff单独保留；该次没有加载模型或产出评分，未覆盖既有输出。
原始用户score_pilot.py按每模型真实分数先执行；另用NumPy/SciPy实现独立核验softmax、风险映射、默认标签、阈值和总体/分域混淆矩阵。保留原始logits/softmax和块坐标，可逐条追溯。默认判定仅作核对，不是唯一比较基线。
按split/domain/label以及token/chunk桶的n和min/Q25/median/Q75/max见各 `independent_audit.json:score_distributions`；ROC点是描述性排序，不能用它重新选择部署阈值。

图：`figures/length_and_roc.png`、`figures/rank_changes.png`，同时提供PDF。长度散点图各面板y轴独立缩放，只比较域内趋势，不比较图间绝对高度。本轮非正式论文实验；不报告下游LLM攻击成功率或合法任务损伤。
