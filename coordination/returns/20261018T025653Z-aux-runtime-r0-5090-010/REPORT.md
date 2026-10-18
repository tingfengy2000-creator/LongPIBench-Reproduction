# R0-5090-010 回执

- 输入 commit：4ad060e1f88cfd7e867996397f23ebed741540bf
- 主机：DESKTOP-B5PNBNC / Ubuntu-24.04 / longpibench-r0
- 真实 PREPARED_REPORT：coordination/returns/20261018T024846Z-aux-runtime-prepare-f576e035/aux_runtime.json
- 总体：PARTIAL_WITH_BLOCKERS
- 未重跑 007/009，未下载模型，未跑正式样本，未选择 DataSentinel checkpoint。
- 未自行改代码或依赖。small/oracle 因 large 失败未执行。

| 项 | Run ID | 命令 | 退出码 | 状态 |
| --- | --- | --- | --- | --- |
| prepare | 20261018T024846Z-aux-runtime-prepare-f576e035 | conda run --no-capture-output -n longpibench-r0 python scripts/aux_runtime_probe.py --stage prepare | 0 | INFERENCE_FILES_STAGED_SPACY_INSTALLED |
| spacy | 20261018T025301Z-aux-runtime-spacy-303d02c0 | ... --stage spacy --prepared-report PREPARED_REPORT | 0 | ORIGINAL_SPACY_INITIALIZATION_PASSED |
| target-tokenizer | 20261018T025307Z-aux-runtime-target-tokenizer-a21d4faa | ... --stage target-tokenizer | 0 | TARGET_SINGLE_BOS_TOKENIZER_PASSED |
| large | 20261018T025445Z-aux-runtime-adapter-large-fbedb182 | ... --stage adapter --adapter large --prepared-report PREPARED_REPORT | 2 | FAILED at loaded_tensor_comparison |
| small | 未执行 | - | - | 未执行 |
| oracle | 未执行 | - | - | 未执行 |

阻碍：large 在原构造加载后，已加载适配器张量集合与 safetensors 不一致；extra_in_model 为 base_model.model.model.embed_tokens.weight，missing_in_model 为空。NF4 层 224 且 quant_state 齐全，active_adapters=[default]，但 adapter_loaded_verified=false，未进入短合成 query。交协调端审查，未改代码/精度/依赖。
