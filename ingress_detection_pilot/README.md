# 独立文档级检测工程试跑

已完成DeBERTa与DistilBERT各80份真实输入评分（两模型使用同40独立源文档）；Prompt Guard按Owner指示暂缓，权限未确认。本轮只诊断H1，不训练、不实现多尺度或复核方案，不改变R0–R4。

结论入口：[go_no_go.md](go_no_go.md)；方法表、分域混淆矩阵、长度桶分数与曲线：[length_diagnostics.md](length_diagnostics.md)。当前未观察到长度条件Max胜过公平校准Max；领域混杂和小样本限制明显，不能写“LCMD有效”。

## 交付文件

- environment_audit.md：官方路径/模型/tokenizer/最大长度/标签语义/CPU环境与未验范围。
- score_schema.md：字段、坐标、原predict早停与额外后缀评分、统计审查和阈值口径。
- pilot_real_scores.jsonl：预声明主条件DeBERTa80行真实分数，完整logits/softmax/分块坐标；不是混合模型文件。
- pilot_results.json：两模型独立评分及审查汇总，不是正式论文性能。
- length_diagnostics.md、go_no_go.md：统计、置信限制、失败模式与当前不推进方法开发的决定。
- results/<detector>/：原始评分、原score_pilot.py原样输出、独立审查、运行manifest与completion；不得覆盖。输入commit见各manifest。
- method_metrics.csv：8种模型/方法组合的总体与分域TP/FP/TN/FN/TPR/FPR，共24行。
- figures/：可分享的PNG与PDF；ROC仅为开发留出的描述性排序，不从图上重新挑部署阈值。
- sample_manifest.jsonl、pilot_plan.json：推理前固定的40源/80变体、12/8源分割及原R0–R4公开数据重叠声明。

## 运行记录与复核

数据准备：`python ingress_detection_pilot/prepare_samples.py`，只读原数据/官方构造；现有manifest拒绝覆盖。

实际模型采集（已执行，输出目录存在时拒绝覆盖）：

```powershell
ingress_detection_pilot/.venv/Scripts/python.exe ingress_detection_pilot/collect_scores.py --detector distilbert
ingress_detection_pilot/.venv/Scripts/python.exe ingress_detection_pilot/collect_scores.py --detector deberta
```

正式采集前独立CPU环境pip check通过。其requirements_cpu_freeze.txt记录完整依赖，torch2.7.1+cpu需使用官方CPU wheel源安装；不要把此环境装进R0/5090环境。Windows和WSL路径不可直接互换。

实际离线评估由`python ingress_detection_pilot/analyze_scores.py`分别调用未修改的score_pilot.py，FPR预算0.10，并独立重算。已有结果拒绝覆写；单独复跑原评分器请使用新输出路径。根汇总在生成报告时补充模型/分析源码hash，原评分输出仍不变。

适配器单测：`.venv/Scripts/python.exe -m unittest discover -s ingress_detection_pilot/tests -p test_capture.py -v`。统计单测：`python -m unittest discover -s ingress_detection_pilot/tests -p test_statistics.py -v`（分析Python需NumPy/SciPy）。玩具数值只在单测内存中，未混入真实结果。

本目录局部.gitattributes保存证据原始字节，.gitignore排除模型/venv/cache。所有推理权重只在models/，没有GitHub/HF凭据、原数据全文或训练状态入Git。源文档公开，但本轮未把源码文档内容批量复制到Git，只保存ID、hash及真实数值。
