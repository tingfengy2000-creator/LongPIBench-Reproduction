# R0-5090-011 回执

- 输入 commit：34795d71acbc5630e44dc2c02444c1b3d5d4b1af
- 主机：DESKTOP-B5PNBNC / Ubuntu-24.04 / longpibench-r0
- 沿用 prepare：coordination/returns/20261018T024846Z-aux-runtime-prepare-f576e035/aux_runtime.json
- 总体：三项均为 ADAPTER_LOAD_AND_SYNTHETIC_QUERY_PASSED
- 未重跑 prepare/spaCy/tokenizer，未下载，未改依赖或方法，未跑正式样本。
- 010 原始失败回执保持不变。formal_checkpoint_selected=false。阻碍：无。

| 项 | Run ID | 命令 | 退出码 | 状态 |
| --- | --- | --- | --- | --- |
| large | 20261018T030940Z-aux-runtime-adapter-large-6d20db5a | conda run --no-capture-output -n longpibench-r0 python scripts/aux_runtime_probe.py --stage adapter --adapter large --prepared-report PREPARED_REPORT --task-id R0-5090-011 | 0 | PASSED；adapter_loaded_verified/finite_cuda_logits/original_query_verified 均为 true |
| small | 20261018T031132Z-aux-runtime-adapter-small-6be8f67c | 同上 adapter small | 0 | PASSED；同上 |
| oracle | 20261018T031318Z-aux-runtime-adapter-oracle-a59f5a5b | 同上 adapter oracle | 0 | PASSED；同上 |

张量检查：policy_version=2。三项均 extra_exported_keys=[base_model.model.model.embed_tokens.weight]，unexplained_extra_keys 为空；base_extra_verified=true，base_input_embedding_check 证明 is_actual_input_embedding=true 且 equals_base_after_dtype_cast=true。存盘键无缺失。

010 未重写。011 通过只验收独立适配器工程路径；large/small 正式选择仍 unknown。
