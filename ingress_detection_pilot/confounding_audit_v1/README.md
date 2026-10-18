# 独立混杂诊断 INGRESS-5060-003

入口：[diagnostic_report.md](diagnostic_report.md)。方法辨析：[confounding_analysis.md](confounding_analysis.md)。下一轮仅设计：[next_independent_validation_plan.md](next_independent_validation_plan.md)。
输入是只读的960条历史真实评分；仅原calibration良性数据用于四策略参数。独立32条标签控制单独保存，未翻转历史标签。所有结论为探索性；LCMD开发NO-GO。

执行顺序：freeze.py事前封存→独立CPU环境controls.py / features.py→分析Python analyze.py→report.py。输出存在时拒绝覆盖；不能在现有目录直接重跑。原评分与R2不修改。
重要文件：calibration_parameters.json、stratified_comparisons.csv、document_decisions.csv、audit_results.json、chunk_position_strata.csv、resume_tail_cases.csv、distilbert_label_audit.json、figures/、completion_receipt.json。
