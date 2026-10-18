# 006/008模型文件回执集成审查

日期：2026-10-18（Asia/Tokyo）。来源commit 5f0213394130c19b1a76f95adfa5020a62c18f8d，分叉点cb57b9b321c1549f61fe3734420b613049f2455f。相对分叉点仅新增两组回执的4份小文件，无代码、方法或权重变更。常见令牌及私钥标记扫描未检出。

## 原始文件保留

| 来源路径 | Git blob |
| --- | --- |
| 20261017T152919Z-public-models-f7e08811/REPORT.md | a0bf37d0d9ff28d4a423fa5a317e8f52d82b4f21 |
| 20261017T152919Z-public-models-f7e08811/public_models.json | f194ce15c4c997371e607c4250120893bf23eb11 |
| 20261017T160020Z-offline-hf-0a7c5a5d/REPORT.md | c9ce35f1f261fb15f3b7e89b3bfc9b87e9b88269 |
| 20261017T160020Z-offline-hf-0a7c5a5d/hf_files.json | 6aa8f0e9de399610d7ac13fb088daf2e664010f1 |

均位于coordination/returns/下，合并不改写原文。

## 核对结果

- 006输入commit 7cf3b28160eda139582fba03ea67547bb25b7793，helper 8/8、550,967,953字节；detector_base 10/10、14,485,815,439字节。
- 008输入commit cb57b9b321c1549f61fe3734420b613049f2455f，target 13/13、16,069,779,031字节。
- 三个repo_id/revision均与upstream_lock一致，31个文件名/大小及校验方法与offline_transfer_manifest一致。所有LFS文件回执SHA256直接与官方元数据一致；普通Git小文件的SHA1验证由下载工具执行，回执记录该方法及内容SHA256。
- 两组状态均FILES_VERIFIED_NOT_MODEL_LOADED，model_load_verified/formal_inference_executed=false。接受006与008在文件准备范围COMPLETED，不宣称GPU模型已加载。

协调端审查的是实际执行端JSON与锁定元数据，并未直接读取远端31GB模型。路径迁移说明也已保留：models/hf-cache及models/direct-hf为指向E盘的链接；后续以真实WSL当前链接解析路径，不假设本机E:\LongPIBench与5090路径相同。

## 后续

以正常merge保留5f02133祖先，推送后再验证。任务009逐模型、逐进程进行实际本地GPU加载/合成短推理；007未收到完成回执，仍有效。LoRA加载、DataSentinel checkpoint、原方法完整初始化及正式轨迹/长上下文配置仍未验收，不启动正式R1/R2或R3失败归因。
