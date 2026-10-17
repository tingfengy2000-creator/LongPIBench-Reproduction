# R0-5090-008 回执

- 运行 ID：20261017T160020Z-offline-hf-0a7c5a5d
- 输入 commit：cb57b9b321c1549f61fe3734420b613049f2455f
- 主机：DESKTOP-B5PNBNC
- 环境：longpibench-r0
- 命令：conda run --no-capture-output -n longpibench-r0 python scripts/offline_hf_bundle.py --download --roles target --bundle-dir models/direct-hf --task-id R0-5090-008 --report-root coordination/returns
- 退出码：0
- 状态：FILES_VERIFIED_NOT_MODEL_LOADED
- 保存：/mnt/e/LongPIBench-Reproduction/models/direct-hf/hf/target（仓库 models/direct-hf 为指向 E: 的符号链接）
- 只处理 target，13/13 文件，16,069,779,031 字节。
- 未加载模型，未启动正式实验，未选 DataSentinel checkpoint。
- 未重复下载 Mistral/GPT-2；006 缓存保留。007 非 HF 任务未重跑。

| 角色 | 仓库 / revision | 文件 | 结果 |
| --- | --- | --- | --- |
| target | meta-llama/Llama-3.1-8B-Instruct @0e9e39f249a16976918f6564b8830bc894c89659 | 13/13 | FILES_VERIFIED_NOT_MODEL_LOADED |

006 回执仍在 coordination/returns/20261017T152919Z-public-models-f7e08811/，输入 commit 7cf3b28160eda139582fba03ea67547bb25b7793。
