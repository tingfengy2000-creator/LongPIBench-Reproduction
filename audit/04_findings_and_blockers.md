# R0 结论与阻碍清单

最新（2026-10-18）：正式R1的400次生成已有回执b90b150；399 VALID、1个Email解析F6。协调端已验配置/输入指纹、唯一清单、计数和Git原始blob，未读取5090上的400份完整raw。R2-5090-001先只读核验R1 raw，再按固定large条件执行全量防御及有效配对目标。formal_r2_v1已冻结8192观察调用/3600秒软保护和F6/中断单列，不将资源截断或上游吞错当作防御成功。下列尚无正式运行等均为历史状态，论文checkpoint身份仍unknown。

最新（2026-10-18）：Owner已明确固定R2全文检测器detector_large/checkpoint-5000，不按ASR换权重，见configs/formal_r2_checkpoint_selection_v1.json。B05的本研究执行选择已解决，论文实际checkpoint仍unknown。014两Email完整定位及恢复后目标生成有效，逻辑前缀与012已完成部分一致，无F6/观察中断，调试阶段收口。R1-5090-001冻结公开快照单BOS条件、400输入和20000上限，正式无防御基线可独立执行且配置未变；R2轨迹/有效性及资源策略仍须冻结。见audit/10_formal_configuration_freeze.md，不从debug推整体ASR/内容无损。下列未选权重等描述为历史状态。

最新（2026-10-18）：013四raw hash通过，Email真实generate220/219、完成搜索段数214→131/221→100严格递减，无重复完成搜索状态；012停止由观察预算触发，当前无死循环证据。已完成helper206/208均有限仅覆盖预算前范围。014独立条件将观察预算8192/3600秒，仅两条Email定位及有效恢复后的目标生成，保留原条件，不改算法或正式配置、不报ASR。

当前更新（2026-10-18）：012已经完成真实ID0试跑，完整PromptLocate构造及6次目标生成通过；两个Email定位受调试观察预算中断，Resume未调用定位。013只分析既有raw，不重测环境、不更改预算。预算截断前nonfinite_helper=false不能证明未执行部分无NaN；正式ASR、large/small选择及全量失败归因仍未完成。下列初始判定/历史进展按其原时间范围理解。

**当前判定：代码与数据具备继续做工程复现的基础；严格复现 Table 4 仍有配置溯源和环境阻碍。尚无本地性能结果，不能进入针对某类失败的新方法设计。**

2026-10-18接续：011来源0476ab8的large/small/oracle独立适配器张量和短query验收均通过。010工具误判已由新运行解决，原始失败仍保留；基础环境阶段结束。012开始真实ID0样本的完整接线debug，完整PromptLocate/定位实际触发、长输入helper有效性及目标配对输出以新回执为准。B05正式checkpoint仍unknown，不从debug选优；正式生成预算/配置与全量日志仍待冻结。

2026-10-18最新：010原分句初始化实际通过，禁用parser/senter且在parser前插入组件在当前spaCy3.8.7/模型3.8.0上可运行；此前静态疑点不再作为已确认初始化阻碍。真实Llama tokenizer单BOS修复通过。large停在协调端工具集合检查，PEFT强制导出额外底座输入embedding导致过严误判；不归为防御算法失败或正式F6发生率。修正工具后的适配器逐值检查与query待011，small/oracle尚未运行；B05仍unknown，完整PromptLocate与B08/B09/B11等待处理。

2026-10-18后续：007的两个ZIP/6个推理成员及spaCy wheel文件范围验收完成，来源8657879。首次观察hash不代表作者公开摘要；未安装/加载。010将独立验证原版spaCy初始化和三个适配器；B05 large/small仍unknown，B13分句初始化实际兼容性尚待回执。详见coordination/returns/20261018T024358Z-coordinator-aux-files-review/REVIEW.md；下文“007待回执”为历史状态。

2026-10-18进展：实际5090身份、候选依赖、HF访问及三套固定模型文件、逐进程GPU加载/有限logits/短合成生成均已有回执。B01—B03的设备/环境/访问阻碍在上述工程范围解除，以下表格为最初审计发现。007适配器/spaCy文件尚待回执，完整加载和长上下文未验收；B04—B15相关方法问题不据此消除。009另发现Llama合成输入重复BOS，协调端已修复检查脚本并做离线回归，实际修正输入仍待后续验证，原009保留不改。详见coordination/returns/20261018T022045Z-coordinator-model-load-review/REVIEW.md。

## 已确认的发现

| ID | 优先级 | 证据与影响 | 处理 |
| --- | --- | --- | --- |
| B01 | 高 | 本机是 5060 8GB，目标5090未在本机确认；environment.json | 在实际运行主机重做GPU/NF4预检；5090方案标估算 |
| B02 | 高 | 当前Python缺全部推理核心包，WSL查询拒绝；environment.json | 新建Linux隔离环境；不能将旧OPI yml原样视为50系列环境 |
| B03 | 高 | Llama未认证请求401；model_link_probes.json | 用户已有授权账号在目标主机本地登录；不索要或输出token |
| B04 | 高 | 两仓库未集成Table4 PromptLocate入口；cli.py及README | 最小wrapper接线，保留原构造、原评分与所有轨迹 |
| B05 | 高 | DataSentinel包有large/small两checkpoint，公开LongPIBench未指定；adapter_metadata.json | 寻找原配置；未知则冻结并声明选择，禁止按ASR挑权重 |
| B06 | 高 | 论文Email无防御Table1=0.70、Table4=0.97，正文称相同设置 | 登记原文内部差异；不自行更换目标模型解释 |
| B07 | 高 | 论文max生成20000，CLI默认4096；Appendix C、models.py | 显式预算；保存实际生成config和stop reason |
| B08 | 高 | 定位helper裁剪至1024后condition_len未同步，可能NaN；contract_probes.json | 首先加非有限值日志；行为修复独立分支，不混原基线 |
| B09 | 高 | 定位except Exception返回原文空定位；PromptLocate.py:313 | 透出异常标签，否则F6会伪装F2或普通原文传递 |
| B10 | 高 | Resume评分将Not qualified判成功，解析错误被计success=false；离线探针 | 官方判定与人工审计并存；错误不当作防御成功 |
| B11 | 中 | 定位API无坐标，归一化与空格重拼；PromptLocate.py | 添加原始字符映射和独立格式差异；不能first-match伪定位 |
| B12 | 中 | Resume公开构造是JSON转文本、无具体岗位要求 | 记录论文输入链路差异；无资格真值不报任务准确率 |
| B13 | 中 | OPI缺spaCy声明，顶层导入多个不相关SDK，硬编码CUDA和示例GPU5/6 | 明确单GPU配置；依赖/延迟导入兼容修复单列；初始化前设CUDA_VISIBLE_DEVICES |
| B14 | 中 | runner覆盖写入且删除prompt；runner.py:31/36/37 | 唯一Run ID、拒绝覆盖、保留输入、完整attempt和manifest |
| B15 | 中 | 代码公开快照不等于作者实验commit；模型API sha是当前快照 | 单列“公开版本执行”与“严格论文配置对齐” |

## 直接可运行与需要适配的边界

- **本轮已执行**：官方仓库克隆与commit记录；两篇论文下载；Table4视觉核对；200原始样本哈希与结构检查；400输入构造；官方评分／异常统计探针；helper索引探针；ZIP目录与adapter_config读取。
- **本轮验证通过**：所选16项官方纯函数／边界测试；两个仓库与审计脚本Python编译；两上游仓库Git tracked files无修改。
- **尚未运行**：Llama/Mistral/GPT-2实际加载、CUDA/NF4验证、检测、定位或目标推理、正式ASR、逐例失败归因。
- **必须适配**：LongPIBench与OPI接线、坐标和轨迹、异常有效性、完整运行元信息、不可覆盖的结果管理。
- **不能悄悄适配**：改阈值、换目标模型、换payload、改分段/搜索/恢复、改helper截断算法、改评分语义后只报单一“复现结果”。

完整权重包已确认可分段读取，但本轮没有下载模型张量或运行加载，不能把ZIP元数据验证写成权重完整性验证。

## 验证记录与局限

`evidence/pytest_selected.txt`：16 passed, 6 deselected。其余涉及完整四套数据或数据加载的测试没有作为全套运行；本轮另对两个任务全部200条执行构造检查，不宣称整仓库全测试通过。

首次pytest在系统临时目录创建fixture失败；改用工作区内专用basetemp后16项全部通过。这是审计执行环境问题，不是模型／方法实验失败。首次下载的证书链错误也保留为采集记录，后续通过系统证书栈取得原文。

helper探针使用token shape替身执行原函数，证实空均值路径；它没有调用真实GPT-2，不能提供真实样本发生率或证明该问题解释论文结果。spaCy自定义组件注册、CUDA硬编码及现代PEFT兼容性仍需真实依赖栈运行验证，不把静态疑点报告为已复现报错。

## 下一步优先级

先完成实际5090主机与授权权重预检，明确DataSentinel checkpoint，再做最小接线和证据记录。冻结配置后运行R1；配对完成R2；取得真实成功残留案例后再进行R3/R4。当前不应依据上述静态问题直接断言检测或定位是主导失败模块。
