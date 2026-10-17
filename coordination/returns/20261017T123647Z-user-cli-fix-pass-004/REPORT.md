# R0-5090-004：CLI依赖修复后的用户回执

- 证据：USER_PASTED_WSL_TERMINAL_OUTPUT；协调端没有在远端执行。
- 终端：`(base) tingfeng@DESKTOP-B5PNBNC:~$`，命令沿用明确指定的longpibench-r0。
- 接收记录时间：2026-10-17T12:36:47Z，不是远端运行时间。
- 接收时协调端commit：2c78687e665d76be84c38737465d5b6003354ed4；远端仓库状态未知。
- 本目录保存用户回传的安装结果和检查输出摘录，省略前部Requirement already satisfied与下载进度；前次失败回执保持不变。

## 验证结果

旧typer0.27.3和typer-slim0.24.0已成功卸载，click8.1.8、typer0.15.2、typer-slim0.15.2安装成功。pip check返回No broken requirements found。全部核心依赖导入及blank English sentencizer检查通过。实际Python为3.11.17，torch2.7.1+cu128，transformers4.51.3，peft0.15.2，numpy2.2.6，spacy3.8.7。

据此接受CLI兼容性修复为USER_REPORTED_PASS，阶段C依赖安装/导入部分通过。GPU合成检查已由前一回执独立记录。本次没有重新运行GPU算子，不声称修复后又完成一次GPU验证。

## 待完成

真实WSL本地私有仓库连接、固定上游恢复与源码哈希验证、最小OPI核心导入、完整传递依赖清单。任务004仍为PARTIAL。blank sentencizer不使用en_core_web_sm，也不是PromptLocate原方法的分句/模型验证；真实权重加载和正式实验均未执行。

下一步按 `coordination/WSL_REPO_IMPORT.md` 接通仓库并检查固定OPI导入。无需重新创建Conda环境或安装GPU包。
