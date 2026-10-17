# R0-5090-004：用户回传实际CUDA/BF16/NF4检查

- 接收时间：2026-10-17T12:25:35Z；不是远端运行时间。
- 证据类型：USER_PASTED_WSL_TERMINAL_OUTPUT；协调端没有远程执行本命令。
- 用户终端：`(base) tingfeng@DESKTOP-B5PNBNC:~$`。
- 运行环境参数：`conda run --no-capture-output -n longpibench-r0`。
- 接收时协调端代码：`2219138e37ddf09779e446ff0b5eca6357507d1f`；远端仓库状态未知，该命令不依赖本仓库。
- 原始命令与输出转录：`terminal_transcription.txt`；没有单独提供退出码，输出已返回shell且无traceback。

## 已确认范围

用户回传PyTorch `2.7.1+cu128`、构建CUDA `12.8`、设备 `NVIDIA GeForce RTX 5090`、bitsandbytes `0.46.1`。命令中的CUDA可用性断言、64×64 BF16矩阵乘法、NF4 CUDA层/quant_state/有限输出断言均执行通过。阶段B接受为USER_REPORTED_PASS。

这是合成运算检查；没有加载Llama、Mistral、GPT-2或任何adapter，没有运行正式数据或产生ASR。当前prompt中的base与通过conda run指定longpibench-r0不矛盾。没有从本次输出推断Python/NumPy版本或pip check结果。

## 待完成

任务004总体仍为PARTIAL：阶段A的Python版本及依赖一致性证据未齐；阶段C完整候选安装、pip check、固定源码的最小OPI导入、环境清单待回传。实际模型加载、权重授权、正式追踪接线与配置冻结仍待验收。若尚无本地Git仓库，可以先执行任务004新增的无仓库依赖安装命令；随后再接通私有仓库以运行固定源码导入。
