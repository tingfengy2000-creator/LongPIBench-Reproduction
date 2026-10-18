# 013只读轨迹审查与014独立条件

来源777f19419a0e9be6db36973ca453b4173265e2f1，输入fd474a3f98f6d2f02bead7b7d0580446aca504be，运行20261018T044320Z-trace-audit-65b8d1bb。两新增文件trace_audit.json/REPORT.md经Git审查，凭据模式扫描未命中；原blob见source_blobs.json。正常merge保留祖先，012/013证据不改写。

接受TRACE_SUMMARIES_CREATED_NOT_RERUN。source_receipt_sha256与原012 defense JSON的Git字节一致，4个source_raw_sha256与原012 case evidence_sha256逐一一致；计数按functions总和及generate角色汇总交叉核验。model_executed/gpu_runtime_imported/asr_computed/formal_checkpoint_selected/original_evidence_modified均false。

| Email条件 | 实际generate | oracle完成/唯一文本 | 完成二分搜索 | 首/末剩余段数 | 已完成helper | 原case秒数 |
| --- | --- | --- | --- | --- | --- | --- |
| clean | 220=whole1+oracle219 | 219/219 | 26 | 214→131 | 206，均有限 | 199.96 |
| attack | 219=whole1+oracle218 | 218/217 | 27 | 221→100 | 208，均有限 | 195.32 |

每相邻完成搜索的段数严格递减，无重复完成搜索状态。当前证据支持搜索在推进且观察预算截断了推进过程，不支持宣判死循环；也没有证明余下搜索/恢复必然正常。攻击case一个查询文本重复两次，不能单独视为无限循环。两个Email的原始分段映射均EXACT_ORDERED_NONWHITESPACE_COVERAGE。

已完成helper的条件长度超出裁剪长度计数为0，非有限值计数0；这仅覆盖012已运行部分，未排除后段裁剪/NaN。两Resume各whole generate1、无oracle/搜索/helper，不能据此验收定位。

## 下一步

014为明确独立的debug条件：同一两条Email、同模型/adapter/阈值/seed/精度/query；观察调用8192、墙钟3600秒/条。依据当前约200秒/1024观察事件及已证实搜索推进设置工程上限，不依据目标成功率，不自动调整。原012预算中断保留，新条件不能补写旧结果。若仍中断，按新条件记录，不继续放宽。

014复用既有执行函数和完整构造，仅独立plan加载器声明新budget与Email子集；读取012原输入/计划/raw及013 hash引用，禁止未声明的模型/方法参数变化。自动核对旧已完成逻辑事件前缀，排除耗时/浮点逐位值，差异时保存raw并停止下游。完成有效恢复后才独立加载Llama；无防御和Resume不重跑；自动附本轮轨迹摘要，避免重复导出轮次。

本轮离线验证：python -m pytest tests/test_email_continuation.py tests/test_debug_pilot.py tests/test_locator_trace.py tests/test_trace_audit.py -q --basetemp .pytest-local-email-cont-20261018-a -p no:cacheprovider，17 passed；新脚本编译与git diff --check通过。覆盖逻辑前缀一致/实际tokens变化/较短轨迹拒绝、错误主机、父方法参数更改拒绝、既有raw不可覆盖/轨迹观察/只读摘要契约。没有在协调端重新加载模型或执行014。
