# B4/B5任务条件化消融：已预设，未执行

状态：`NOT_EXECUTED`。同一固定Llama-3.1-8B、BF16、greedy、192输出token上限、同一结构化标签格式、同一文档；只改变可信task字段为空（B4）或为manifest.trusted_task（B5）。冻结提示见llm_prompts.json。

不得提供sample_id、split、variant、label、rationale或攻击模板名给模型。文档只为证据，不执行其指令或任何工具。格式/标签/证据不合法记invalid，不修补重试。逐源配对报告两域、ordinary/HB及三攻击族，不按成功案例筛选。

级联预设PIGuard→B5，第一层阈值只由development攻击95%召回目标确定，阴性直接放行；离线重放时明确标注，其延迟是组件测量相加而非上线实测。第一层漏检不能被后层挽救。

Q3/Q4均待真实运行：目前不能说可信任务稳定增益或级联达到相近效果。可信说明增加token，不能据本对照独立证明语义而非额外长度的纯因果效应。
