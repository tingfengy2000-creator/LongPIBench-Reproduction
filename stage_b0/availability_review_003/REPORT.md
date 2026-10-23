# B0-5090-003协调端验收

状态：`B0_003_PARTIAL_AVAILABILITY_ACCEPTED_PG2_BLOCKED`。原提交`04cc5a879ed9e54800886ae4fc978e7020d71cbc`已按祖先关系快进纳入审核分支，不改main。检查原Git blob和工作区字节一致，提交仅新增4个本次回执文件，父提交为`514949d`。

| 角色 | 验收 | 实际证据及边界 |
| --- | --- | --- |
| PG2 | BLOCKED | 固定revision为原定a8ded8e，HTTP403，未下载权重、未加载、未执行短控制；不得填入性能表或用替代品冒充 |
| DataSentinel | 工程可用 | 原Mistral+large/checkpoint-5000配置、实际文件核验清单及generation defaults与G0一致；加载62.388秒、32768配置上下文；三条短控制0/0/0 |
| Llama | 工程可用 | 原固定revision，BF16不量化，真实5090/CUDA、有限前向与短生成通过；加载71.860秒、131072配置上下文。当前文件复核范围是既有完整摘要加当前大小，不夸大为再次全量hash |

DataSentinel对显式“ignore task”短控制也返回0。这是保留的控制漏检，不是B0完整数据的漏检率，不据此换checkpoint或调规则。Llama短输出为“Model loaded successfully.”，并非system要求的单词READY；本次短探针的验收谓词仅为加载、有限前向与生成完成，不证明B4/B5指令遵循或检测有效。

首次Llama启动外壳退出127、/tmp脚本缺失、没有加载模型，仅有执行端汇总文字声明，没有独立shell日志。另一次真实进程的完整JSON验收通过。二者不可合并成“首次无失败”；声明本身不升级为协调端独立核验。原汇总和所有成功/失败记录保持不变。

三个JSON内部task_id仍为001，外层003明确说明兼容shim；未篡改旧身份。DataSentinel的CUDA使用由固定程序中的加载/显存断言及本机执行声明支持，本角色JSON没有单独保存完整CUDA盘点，不借用Llama的CUDA字典冒充它自己的原始记录。新的评分程序会直接保存各角色GPU身份和依赖检查。

本验收只独立复核提交、配置和已保存证据，没有协调端重跑GPU。短控制不等于2000条非PG2评分，也不等于B0完成。PG1/PIGuard仍只有5060侧CPU探针；须在同一5090评分程序中先核对固定文件并执行原生单窗口等价控制。若无法访问固定PG1，则如实增加缺失，不换模型。

标签门已完成，允许准备并派发不含PG2的既定探索性原始收集。原数据、提示、精度、窗口、Max及阈值规则不变。Q1中PG2部分仍无法回答，其他结论须等待真实评分及后续统计。

只读复核：`D:\anocanda\python.exe stage_b0/availability_review_003/verify.py --check-only`。
