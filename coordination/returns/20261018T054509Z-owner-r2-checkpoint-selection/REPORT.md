# R2 checkpoint Owner选择记录

- 决策ID：R2-CHECKPOINT-SELECTION-001
- 记录时间：2026-10-18T05:45:09Z；来源：当前会话用户明确文字回复。
- 用户原文：“固定 large/checkpoint-5000 为主条件，不按 ASR 换权重（建议）”。
- 状态：OWNER_CONFIRMED_PRIMARY_CHECKPOINT；仅记录配置选择，未执行GPU任务。

正式R2全文检测器固定为detector_large/checkpoint-5000；不按debug或正式ASR换权重。机器可读选择及已验收007的config/权重文件hash见configs/formal_r2_checkpoint_selection_v1.json。oracle保持原公开包checkpoint-500。hash为已观察传输身份，不是作者独立公布摘要。

论文实际DataSentinel checkpoint仍为unknown，原upstream_lock作者未知字段不改。R1配置、代码、任务与输入不改，不要求中断或重跑R1；本次没有新的5090执行命令。R2全量runner、轨迹/有效性与资源策略还须准备，不据此宣称R2已就绪或已运行。

验证：选择JSON可解析；large/oracle共4个文件身份与007原始回执逐项一致；R1配置canonical SHA256仍为efe2a0665ba627cf9a72b5d465690a3fc6fd62b8922cf3ed7fd902d871bf15b1；git diff --check通过。未运行模型或重新执行测试。
