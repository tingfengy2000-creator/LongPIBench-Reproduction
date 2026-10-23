# B0-5090-003 可用性回执

外层任务：B0-5090-003。原程序内部 `task_id` 仍是 B0-5090-001，本次没有改它。这是缓存路径预检修正后的新运行，不是把 001 的失败回执改成成功。不是 B0 评测完成，400 条候选没有评分。

- 主机：DESKTOP-B5PNBNC，NVIDIA GeForce RTX 5090
- 分支：machine-5090
- 输入 commit：`514949d6babf14655de8076650e514f493b0138e`
- 汇总 Run ID：`20261023T014134Z-b0-5090-003-24f347df`
- 缓存：`/mnt/e/LongPIBench-Reproduction/models/b0-cache`
- 命令：`stage_b0/remote_availability_v2.py --cache-root` 上述路径，三个 role 各自独立进程，顺序为 prompt_guard_2、datasentinel、llama
- `models` 父目录和既有链接没有移动。没有改代码、依赖、精度或参数，没有重下 Llama 或 Mistral。

## 各 role

| role | Run ID | 退出码 | 状态 |
| --- | --- | --- | --- |
| prompt_guard_2 | `20261023T013459Z-b0-availability-prompt_guard_2-570957a3` | 2 | `BLOCKED_OR_FAILED` / `GatedRepoError` / HTTP 403 |
| datasentinel | `20261023T013525Z-b0-availability-datasentinel-ef8859a0` | 0 | `DATASENTINEL_MODEL_LOAD_AND_CONTROLS_PASSED_NOT_B0_EVALUATION` |
| llama | `20261023T013847Z-b0-availability-llama-5c3f5d39` | 0 | `LLAMA_MODEL_LOAD_AND_SHORT_CONTROL_PASSED_NOT_B0_EVALUATION` |

三条回执的 `candidate_scores_computed` 都是 0。

Prompt Guard 2 固定 `meta-llama/Llama-Prompt-Guard-2-86M@a8ded8e697ce7c355e395a0df51f94adb4a2fd27`。请求返回 403，没有登录新账号、没有换镜像、没有执行 auto_map。权重未加载，短控制未执行。

DataSentinel 使用回执中的本地 Mistral-7B-v0.1 快照 `27d67f1b5f57dc0953326b2601d68371d40ea8da` 和 `detector_large/checkpoint-5000`。加载 62.388 秒，`max_context` 32768。三条短控制的 binary_flag 为 0、0、0，耗时 1.782、0.803、0.802 秒，`risk_probability` 为 null。

Llama 使用本地 `meta-llama/Llama-3.1-8B-Instruct@0e9e39f249a16976918f6564b8830bc894c89659`，`load_mode` 为 `BF16_NO_QUANTIZATION`，embedding dtype `torch.bfloat16`。加载含磁盘读取 71.860 秒，短前向 0.662 秒，`short_generation_verified` 为 true，`max_context` 131072。

第一次启动 Llama 时，`/tmp` 里的启动脚本已经不在，外壳退出 127，没有生成 Llama 回执，也没有加载模型。随后用同一条 v2 命令启动了一次，上面的退出码 0 来自这次实际进程。

## 未完成

Prompt Guard 2 仍不可用。没有 human_signoff，没有启动 400 条评分、B4/B5 或级联。
