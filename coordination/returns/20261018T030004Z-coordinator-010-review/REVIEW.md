# 010回执审查与检查工具修正

来源ba6d4bc15ef2d26e7bc05bcc44e85ec9baed65f0，执行输入4ad060e1f88cfd7e867996397f23ebed741540bf。9个新增小文件经Git获取：4份JSON、4份日志及汇总REPORT；凭据模式扫描未命中。原始blob清单见source_blobs.json，正常merge保留来源祖先，原文件不改。

总体接受PARTIAL_WITH_BLOCKERS，不将工具修复追溯为原large成功。small/oracle无运行回执，明确未执行。全部debug，无正式样本、无checkpoint选择、无ASR、无完整PromptLocate constructor。

| 操作 | Run ID | 核验结论 |
| --- | --- | --- |
| prepare | 20261018T024846Z-aux-runtime-prepare-f576e035 | 6个推理成员hash/大小与007一致；spaCy3.8.0首次安装，28个包内文件与wheel一致；核心6包版本前后相同，pip check=0 |
| spacy | 20261018T025301Z-aux-runtime-spacy-303d02c0 | 原initialize_spacy通过；custom_sentence_segmenter实际激活，parser/senter禁用；3个合成句子字符范围有效 |
| target-tokenizer | 20261018T025307Z-aux-runtime-target-tokenizer-a21d4faa | 单BOS、50 tokens；脚本通过与直接chat模板全部token IDs一致的断言；未加载Llama权重 |
| large | 20261018T025445Z-aux-runtime-adapter-large-fbedb182 | 原构造返回、224NF4层及quant_state、default活动adapter；比较存盘张量值前失败，无forward/query验收 |

所有JSON输入commit/主机/5090硬件门槛一致；准备回执与007回执的SHA256引用按Git原始字节验证通过。原spaCy静态疑点未在当前栈复现，不改为初始化报错；009单BOS修复现在具有真实tokenizer验证，但不据此冻结正式target消息格式或生成预算。

## large停止原因

missing_in_model=[]；extra_in_model仅base_model.model.model.embed_tokens.weight。原工具使用get_peft_model_state_dict(save_embedding_layers=True)，PEFT会导出输入和输出embedding。协调端错误要求该导出集合必须等于adapter safetensors集合，造成检查工具误判；不是已确认的权重损坏、LoRA值错误或上游方法异常。

依据：[PEFT v0.15.2原实现](https://raw.githubusercontent.com/huggingface/peft/v0.15.2/src/peft/utils/save_and_load.py)，save_embedding_layers=True时从完整state_dict补入embedding模块张量，导出集合不必与输入checkpoint集合相等。运行记录在比较值前已退出，因此即便来源明确，也不能声明large全部张量加载正确。

## 修正及接续边界

脚本新增policy_version=2：所有存盘键必须在模型中，所有活动adapter键必须存在于存盘文件；任意未知额外键仍失败。每个存盘张量均保留原逐值精确比较（加载dtype转换后），包括文件中实际存入的lm_head/embedding。唯一可分类的额外输入embedding必须证明与实际get_input_embeddings权重同一存储，并与固定本地Mistral safetensors索引指定的底座张量逐值相等，才能继续。不能仅靠名称豁免，额外底座读取保留HF缓存链接，不下载或重写权重。

该修正只改检查工具，不修改模型加载、上游源、权重、量化/精度或query参数。新增task-id参数区分011新回执；010失败保持原值。011复用已通过prepare路径，仅依次large/small/oracle工程检查，不重做安装、分句、tokenizer或007/009。固定底座embedding值及实际adapter张量修正后验证仍待真实GPU执行。

本轮验证：python -m pytest tests/test_aux_runtime_probe.py tests/test_offline_transfer.py tests/test_local_model_probe.py tests/test_opi_loader.py -q --basetemp .pytest-local-aux-keys-20261018-b -p no:cacheprovider，26 passed；脚本编译及git diff --check通过。新回归覆盖已观察的额外底座键分类、缺存盘键、缺活动LoRA、额外LoRA、未知底座、空集合，以及输入embedding身份错误/底座值改变时仍拒绝。测试使用轻量替身，不冒充真实张量或GPU验证。
