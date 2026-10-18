# INGRESS-5060-003 回执

Run ID: `20261018T125323Z-ingress-5060-003-d263cc41`
预冻结commit: `6405ce79398ef72050b57c0edf6d709085164277`

状态：EXPLORATORY_CONFOUNDING_AUDIT_COMPLETE_WITH_CAVEATS。历史960评分只读；四个离线策略仅用原校准良性数据拟合，旧留出仅作历史解释。没有训练、LCMD、多尺度或新的运行时防御模块。5090 R2完全独立未访问。

DeBERTa：Domain覆盖Length相对Global新增16次检出的全部，判定一致率95%，但实际FPR不同；不能称作因果解释100%或固定FPR优越性。D+L未增加域内AUROC/AP，LCMD开发NO-GO。其他模型保留Resume局部关联，需新独立域长平衡验证，不强行否定所有长度信息。

标签：原作者Space明确LABEL0良性、LABEL1注入。冻结32条独立控制样本做真实CPU前向，TP16/FP11/TN5/FN0，不翻转历史标签。2900块仅重建tokenizer输入hash、没有重新跑历史模型。

命令：freeze.py（封存）→pilot独立CPU环境controls.py、features.py→现有分析Python analyze.py、report.py。render_revision仅修正派生PR阶梯方向，与AP积分一致，不修改分数、曲线点或阈值。

5单测通过；AUC/AP独立核验、旧G/L阈值及计数精确复现；360旧文件hash不变。5张PNG由协调端图像检查，PDF同图导出但未单独栅格化复检。

结果与下一轮独立数据方案均位于ingress_detection_pilot/confounding_audit_v1/。下一轮方案只设计未执行。完整数值与脚本可复核，未提交模型、缓存、凭据或文档全文。
