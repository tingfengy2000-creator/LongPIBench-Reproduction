# 007资源文件审查与010准备

来源：865787900fa5901c5f89474f7e1a1a785dfbed99，执行输入17826dc50f27bc3a707b7481a5c6f053cb270508。007接受为COMPLETED_FILES_CHECKED_NOT_MODEL_LOADED，不推定适配器加载或spaCy安装。仅新增REPORT.md与aux_downloads.json，凭据模式扫描未命中。

原始目录coordination/returns/20261018T023636Z-aux-downloads-fe64f023/；实际资源位于执行主机/mnt/e/LongPIBench-Reproduction/models/resource-download-20261018T022505Z-AXb5d0。协调端通过Git审查小型回执，未直接读取远端2.12GB包。

核对固定清单的两个官方Drive URL、两个ZIP中全部6个推理成员名称/大小、CRC标志、首次观察SHA256及固定spaCy wheel URL/版本检查状态，均一致；原工具按清单验证完整adapter config。ZIP大小分别1401845934/701657336字节，wheel大小12806118字节，见执行REPORT及固定清单。aux_downloads.json未包含输入commit/主机字段，由原REPORT提供，下一任务脚本新增这些结构化元信息，不改007原文件。

| 资源 | 首次观察SHA256 |
| --- | --- |
| DataSentinel_Models.zip | 7fd3b5ae4fb97d5fd8ad425e1125bee3504dfe640b22faecde3bba6f586b6767 |
| promptlocate_oracle.zip | c888231a4bbec391fcbfa2853600b8c7161a950e98942851eac6c70203500fc6 |
| en_core_web_sm-3.8.0-py3-none-any.whl | 1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85 |

以上为首次观察传输追溯摘要，不是作者独立公布摘要；不提升来源真实性声明。007未提取ZIP、安装spaCy、加载adapter或运行正式样本。

原始Git blobs：REPORT.md=15bedd13a72704c8938f4c818e148680d6d25a49；aux_downloads.json=cdfb127876eb1998f10a27e199ba81fd7c69775a。正常merge保留8657879祖先关系，原始blob保持不变。

协调端为010新增aux_runtime_probe.py及明确分阶段命令：只提取JSON/safetensors；本地wheel无依赖安装；原分句初始化；真实Llama tokenizer单BOS检查；large/small/oracle独立进程通过原构造加载并比对张量、合成forward和原query。不会因为哪套检测输出更好而选择checkpoint，不改变固定上游或方法行为。完整PromptLocate constructor始终未验收。

实现依据为固定上游源码、[PEFT v0.15.2状态导出实现](https://raw.githubusercontent.com/huggingface/peft/v0.15.2/src/peft/utils/save_and_load.py)、[safetensors接口](https://huggingface.co/docs/safetensors/api/torch)、[spaCy管线API](https://spacy.io/api/language#add_pipe)。这些资料只支持工程实现，真实初始化兼容性以010回执为准。

本轮离线验证：python -m pytest tests/test_aux_runtime_probe.py tests/test_local_model_probe.py -q --basetemp .pytest-local-aux-runtime-20261018-a -p no:cacheprovider，9 passed；aux_runtime_probe.py编译及git diff --check通过。覆盖只提取推理文件、不覆盖、CRC/哈希错误拒绝、路径穿越拒绝及错误主机不得安装/加载。替身/合成ZIP测试不等同真实模型或spaCy验证。

加入所有阶段版本门槛后，连同既有离线资源校验和固定OPI loader契约回归：python -m pytest tests/test_aux_runtime_probe.py tests/test_offline_transfer.py tests/test_local_model_probe.py tests/test_opi_loader.py -q --basetemp .pytest-local-aux-runtime-20261018-b -p no:cacheprovider，17 passed。未在协调端安装spaCy或加载GPU模型。
