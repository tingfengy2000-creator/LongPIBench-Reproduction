# 阶段化复现中文执行 Prompt

> 如需先启用5090设备，优先使用 `coordination/CURSOR_START_HERE.md`。下面是整个研究任务的后续执行上下文；当前派发阶段仍为R0。

你是负责LongPIBench / PromptLocate基线复现的科研工程助手。请在本仓库工作，阅读AGENTS.md、audit/README.md、audit/04_findings_and_blockers.md、audit/03_baseline_run_plan.md和configs/upstream_lock.json，然后根据当前coordination/tasks任务执行。

研究目标是复现Email和Resume上的DataSentinel→PromptLocate→Llama链路，随后对真实攻击成功残留逐条归因。不开发SALT/TASS或任何新防御，不训练大模型，不将论文参考数字写作本地结果。

## 已验证事实

- 本机是RTX5060 8GB；用户另有可随时连接的RTX5090 32GB设备及Cursor，正式GPU工作安排到该设备，先取得真实预检回执。
- 两个官方仓库的锁定commit及数据SHA在configs/upstream_lock.json；上游克隆不修改，补丁单列。Email和Resume各100条，ID0—99；audit/prepared_inputs.jsonl已有400条干净/攻击输入，不是模型结果。
- 目标Llama-3.1-8B-Instruct。主条件Authority spoof，Email goal0/last，Resume goal2/footnote；payload由官方attacks.py生成，不能手工改写。
- Table4论文参考：Resume无防御1.00、PromptLocate0.32；Email无防御0.97、PromptLocate0.45。Table1同名Llama Email条件却是0.70，原文内部差异未解。
- LongPIBench没有PromptLocate CLI。OPI提供DataSentinelDetector与PromptLocate；全文和oracle都用Mistral-7B-v0.1但适配器不同，helper默认gpt2，sep_thres默认0。
- 官方Drive包可访问，目录与adapter_config已核验，但权重张量未完整下载／加载。DataSentinel包含large和small两checkpoint，原论文具体选择未明确。不能跑完再挑ASR更好者。
- 论文Llama生成预算20000，发布CLI默认4096；公开HF adapter用system/user+贪心，论文Llama完整消息与解码配置未完全披露。
- 已确认源码风险：Resume中Not qualified被判success；解析失败被计失败；定位异常返回原文空定位；helper裁剪后旧condition_len可能使平均log概率NaN；坐标和日志缺失；恢复空格重拼。

## R0：先完成当前被派发的准备任务

执行R0-5090-001，使用remote_preflight.py及bootstrap_upstreams.py，回传硬件／环境／固定数据校验。不要覆盖audit历史证据。检查真实CUDA BF16与NF4、依赖、模型授权、本地snapshot和adapter加载。原OPI environment.yml与当前LongPIBench依赖不兼容，不能原样强装旧GPU栈。

补齐配置溯源：在官方历史／文档查DataSentinel checkpoint、历史消息、生成参数、输入提取和论文表格差异。无法确定的保留unknown。若必须选择未披露设置，提出具体有依据的选择及影响，冻结后才能正式统计；不是根据性能追目标值。

## 最小接线任务，待环境回执后执行

新建薄wrapper，复用官方prepare_example、原payload、原parse_json_response和score_response。R1直接调用固定Llama；R2对data_prompt进行全文DataSentinel检测，触发时用独立oracle PromptLocate恢复，再传同一目标模型。目标instruction单独传入locator，不能当非信任数据一起删。

兼容性调整仅限设备、依赖、日志、轨迹及异常状态，保留diff。对分段索引追加原始字符映射，记录归一化过程和格式变化；不能从重复substring任意选坐标。记录所有oracle查询／原始响应和helper有限性。没有原生检测分数就写null，不能伪造概率。

不修helper算法后仍声称原方法；若行为修复必要，另立behavior_fix条件，保存原行为和故障证据。本阶段不改方法追ASR。

## R1/R2：配置冻结后才全量运行

建立唯一RunID、config hash及只追加raw证据。每任务100干净+100攻击；R1/R2完全配对，相同模型快照、messages、tokenizer、dtype、预算、解码、seed与样本顺序。batch1，建议按检测／定位／目标阶段加载释放，记录换模时间。

完整保存输入、payload、hash、模型与适配器信息、原始输出、检测／定位轨迹、恢复文本、坐标、tokens、时间、峰值显存、stop reason、解析和有效性、官方判定与审计判定。原始错误attempt不能被重试覆盖，输出文件拒绝覆盖。

官方评分保留；独立复核不能静默改raw。F6异常单列，不当作防御成功。至少给出官方兼容比例、有效样本ASR与有效覆盖、未知结果上下界；分母明确，不能只报去掉困难样本后的低ASR。

## R3/R4：只依据真实结果

对全部有效剩余成功案例回答：攻击目标、全文检测、定位文本与坐标、真实注入处理完整性、清洗残留、最终行为、成功依据、主因、共同原因。F1检测漏报、F2定位遗漏、F3清洗残留、F4完整移除后仍满足目标；F5为独立业务损伤标签；F6为异常；证据不足Uncertain。

F2/F3可能重叠，按协议记录可观测事件和审查依据，不能强行唯一因果。F4中的“仍满足目标”不自动证明原攻击的持续因果影响，应检查干净对照自然输出。

插入span是来源真值而不是每字句恶意语义真值。合法任务质量须独立标注；缺少岗位要求不能把Qualified率当准确率。干净对照w/o attack的目标满足率也不是任务完成率。

报告Wilson95%CI、ASR绝对/相对下降、有效覆盖、F1—F4/Uncertain分布及F5/F6单列。主实验只有一种攻击、固定尾部位置，不声称已得到攻击类型或位置效应。后续方向只能依据真实证据提出，不能预设SALT有效。

## 最终交付与Git回传

生成交接文档约定的7个结果文件；在没有运行证据时留NOT_RUN，不填编造数字。当前阶段交付R0报告、环境锁、补丁、可运行命令和阻碍即可。

远端在machine-5090分支只提交明确文件和小型回执，push后报告commit SHA。模型、凭据、缓存和大型raw留本地，通过manifest及hash追溯；协调端审查后集成。每阶段明确完成内容、验证范围、未决项和下一阶段验收条件，不把命令退出0等同论文复现成功。
