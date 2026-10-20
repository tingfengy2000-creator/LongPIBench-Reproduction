# B0-5090-001 可用性回执

任务状态：`COMPLETE_WITH_UNAVAILABLE_BASELINE`。这是三次独立工程可用性检查的回执，不是 B0 评测完成，也不是 400 条候选的评分结果。

- 主机：DESKTOP-B5PNBNC
- 分支：machine-5090
- 输入 commit：`fdb1d72b400da3872a9637624cc06e87fa156e18`（fast-forward 自 `a7e5e4eea4ea7c800e8f983a6e31928464b2e136`）
- 汇总 Run ID：`20261020T021928Z-b0-5090-001-1b8a133e`
- 候选评分：0。未打开 `dataset_manifest.jsonl` 做评分，未生成 human signoff，未填写人工标签。
- 源码、依赖、checkpoint、models 链接均未修改。

## 共同阻碍

`stage_b0/remote_availability.py` 在创建缓存和加载模型之前要求 `models` 解析路径位于 `/mnt/e` 或 `/mnt/d`。本机 `models` 不是符号链接，解析结果是 `/home/tingfeng/LongPIBench-Reproduction/models`。其下既有 `direct-hf`、`hf-cache`、资源目录仍指向 `/mnt/e`，这些链接保持原样。断言因此在三个 role 上各自失败，进程退出码均为 2。没有创建 `b0-cache`，没有下载，没有加载权重，没有执行短控制。

## 各 role

| role | Run ID | 退出码 | 状态 | 权限 | 实际模型/精度 | 控制耗时 |
| --- | --- | --- | --- | --- | --- | --- |
| prompt_guard_2 | `20261020T021641Z-b0-availability-prompt_guard_2-61169d51` | 2 | BLOCKED_OR_FAILED / AssertionError | 未到达请求 | 未加载 | 未执行 |
| datasentinel | `20261020T021758Z-b0-availability-datasentinel-186ba483` | 2 | BLOCKED_OR_FAILED / AssertionError | 未到达请求 | 未加载 | 未执行 |
| llama | `20261020T021828Z-b0-availability-llama-841f53e2` | 2 | BLOCKED_OR_FAILED / AssertionError | 未到达请求 | 未加载 | 未执行 |

三个回执的 `reason` 都是 `Resolved model root must be D/E; preserve existing links`。`http_status` 为空，`candidate_scores_computed` 为 0。

## 未完成

- Prompt Guard 2 固定 revision 的账号权限仍未知；本次没有发出模型请求，不能记成 403，也不能记成可用。
- DataSentinel 的冻结 large/checkpoint-5000 加载和三条短控制未执行。
- Llama 本地 8B BF16 短控制未执行。
- 400 条候选未评分。人工标签未签认。B0 检测、B4/B5 和级联未启动。
