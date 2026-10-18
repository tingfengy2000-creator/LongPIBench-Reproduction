# 扩大文档检测验证 INGRESS-5060-002

结果入口：[length_diagnostics.md](length_diagnostics.md)、[go_no_go.md](go_no_go.md)。真实分数按检测器分别保存在results/，不混合重复sample_id；原score_pilot输出pilot_results.json及独立审计均在各模型目录。顶层pilot_results.json汇总全部三模型。

每模型320变体/160源，排除上一轮40源；80源校准、80源留出，同源不泄漏。不是独立论文测试或新算法验证。方法表见method_metrics.csv，环境、schema、曲线及不可覆盖运行证据随附。

执行：独立CPU环境运行run.py --detector {deberta,distilbert,prompt-guard}；本机分析Python运行analyze.py。输出存在则拒绝覆盖，不可直接重复执行。
