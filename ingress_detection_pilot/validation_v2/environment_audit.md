# 环境与版本

复用E盘独立CPU环境，torch 2.7.1+cpu、transformers 4.51.3、Python 3.13.9、FP32，每检测器4线程；未下载、安装或修改依赖。权重来自上轮固定hash文件；每次加载前再校验。完整版本见原requirements_cpu_freeze.txt和本轮manifest/completion。

官方检测路径及512切块语义沿用既有审计；记录适配器源码hash不变。新增执行脚本只选择预冻结新源、记录日志并拒绝覆盖。启动前遇到Windows GBK读取UTF-8元数据失败，修复及失败记录位于patches/及execution_attempts/，不修改模型行为。

分析Python使用本机已有NumPy/SciPy/Matplotlib，版本见validation_receipt.json；真实得分来自独立推理环境。所有大文件、缓存及下载临时目录均在E盘，模型评分过程完全离线；另仅获取固定revision的官方模型卡小文件到E盘核查标签，见distilbert_card_audit.json。R0–R4及主分支不改。
