# R0-5090-004：完整候选安装后的spaCy导入失败

- 证据：USER_PASTED_WSL_TERMINAL_OUTPUT，协调端未在5090执行。
- 运行环境：用户在 `DESKTOP-B5PNBNC` 的Ubuntu终端通过conda run指定longpibench-r0。
- 目录时间：2026-10-17T12:31:06Z协调端接收检查时间，不是远端运行开始时间。
- 协调端接收时commit：30d1db284e2642d6a9e2d15e37760a0e0f54dc73。远端仓库状态未知。
- 本目录保存用户日志的错误尾部原文摘录；下载进度及完整安装列表未重复转录。原始聊天保留完整粘贴。

## 观测

用户安装列表显示spacy3.8.7、typer0.27.3、typer-slim0.24.0、weasel0.4.3等安装成功，pip check返回No broken requirements found。随后依赖导入脚本在spacy/cli/_util.py的`from click import NoSuchOption`失败：`ModuleNotFoundError: No module named 'click'`。最后的Python/版本打印未执行，不能从本次日志声明导入全部通过。cp311路径与包标签支持使用Python3.11，但没有完整Python patch版本。

已通过的GPU合成检查见前一独立回执，本次无CUDA错误。当前失败是环境依赖故障，不是正式研究的检测/定位失败案例，不计入正式F1—F6分布。

## 官方证据与修复候选

`audit/evidence/r0_spacy_cli_dependency_metadata_20261017.json`保存PyPI固定版本依赖字段。spaCy3.8.7允许typer>=0.3,<1且未直接声明click；weasel0.4.3依赖typer-slim。此次typer-slim0.24.0依赖typer>=0.24.0；typer0.27.3不再声明click。spaCy固定源码仍导入click、click.parser及typer.main.get_command：

https://github.com/explosion/spaCy/blob/release-v3.8.7/spacy/cli/_util.py

因此不能只固定spaCy并放任CLI依赖漂移。协调端固定typer0.15.2与typer-slim0.15.2（二者声明click>=8），以及click8.1.8。保持其他直接版本及GPU栈不变。这是依赖兼容性候选修复，不改变攻击、检测、定位、评分或阈值；没有证据表明它已在5090解决问题。任务004提供补包与运行验证命令。

## 待验收

修复后的pip check、全部依赖导入、无外部模型的blank sentencizer检查，以及后续固定OPI导入、完整环境清单。阶段C保持未通过；任务004不记COMPLETED。
