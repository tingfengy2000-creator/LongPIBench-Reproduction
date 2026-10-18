# INGRESS-5060-002 本机扩大验证回执

Run ID: `20261018T113433Z-ingress-5060-002-edbc626d`

状态：EXPANDED_REAL_VALIDATION_REVIEWED_WITH_CAVEATS。三套固定检测器各320真实文档评分，160个新增源，不与旧烟测40源重叠；不是独立论文测试。原R0–R4保持不变。

推理：pilot CPU独立环境运行validation_v2/run.py --detector {deberta,distilbert,prompt-guard}。统计：本机分析Python运行validation_v2/analyze.py、review.py。完整输入commit、模型revision、配置和得分hash见本目录JSON及各模型manifest/completion。

逐块softmax/坐标、默认官方判定共960条一致；原scorer阈值与总体/分域混淆矩阵独立重算通过。旧65份受约束产物hash不变。PNG图已由协调端图像检查；PDF未单独栅格化复检。

DeBERTa局部总体TPR+10个百分点（观察FPR同为10%），配对检验p=.1516，且存在域间收益/误报重新分配；不声称新算法已有效。Prompt Guard仅Resume长度关联复现，跨域H1三模型均未通过。DistilBERT标签语义未确定。当前工程GO、复杂方法开发NO-GO。

Prompt Guard第一次启动在模型加载前因UTF-8元数据被GBK读取失败，原失败和兼容diff已保存；没有覆盖模型分数或重试已评分案例。无新增运行阻碍。

结果入口：ingress_detection_pilot/validation_v2/review_summary.md。完整逐块数值不足1MiB/文件，可随Git复核；没有权重、缓存、token或源文档全文入Git。
