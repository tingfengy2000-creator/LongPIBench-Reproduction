# 跨设备 Git 协作协议

## 分工与通信

- 协调端：本机Codex，负责主要代码修改、方法和实验条件把控，维护main上的审计、任务、配置与集成。
- 执行端：用户可连接的5090设备上的本地Cursor，在machine-5090分支执行明确的GPU命令并提交回执。遇到代码故障保留报错交给协调端，不自行修改核心方法、攻击、评分或研究配置。
- Git是任务、代码与小型证据的通信渠道；不是远程执行服务。只有远端Cursor实际启动并运行后，才有远端结果。当前未建立SSH、远程桌面或Cursor API连接。

任务文件使用 `coordination/tasks/<Task ID>.md`，回执使用 `coordination/returns/<UTC>-<label>-<unique>/`。不依赖修改一个共享STATUS文件，以免两端覆盖。每份回执写清task ID、输入commit、实际命令、输出证据、验证结果、未完成项及下一步。

R0-5090-001实际运行在无GPU的Cursor Cloud VM，回执commit为186e6df，已保留BLOCKED结论。分支名machine-5090、安装CUDA版torch或云端任务成功启动都不能证明使用了5090。后续GPU任务必须从5090电脑桌面的本地Cursor终端启动，并先通过型号与显存检查；失败后停止安装和模型下载。

R0-5090-002再次在同一类Cloud环境失败（commit66a50d6），说明硬件检查正确阻止了后续GPU步骤，执行位置仍未切换。用户已确认能打开真实5090电脑的Windows PowerShell；当前先由用户在该终端确认GPU，参见WINDOWS_5090_CONNECT.md。确认之前不继续派发相同Cloud任务，不把安装显卡驱动到Cloud VM当作解决方案。

后续用户已回传DESKTOP-B5PNBNC上的RTX5090、32607MiB、驱动610.88。该证据标为USER_PASTED_WINDOWS_TERMINAL_OUTPUT，不能改写为协调端远程执行。下一步为R0-5090-003本机环境盘点；不能由显卡型号与驱动直接推定Python/CUDA/NF4或模型可运行。

## 远端常规步骤

首次克隆后创建 `machine-5090`。之后先检查工作区，确认无未提交变更，再fetch main并合并；不使用hard reset、不强推：

```bash
git status --short
git fetch origin
git switch machine-5090
git merge origin/main
```

完成任务后只add本次明确文件，commit并push machine-5090。协调端fetch后检查回执和变更，再合并或cherry-pick。原始输出、异常attempt和旧回执不重写。

若另一设备已经建立machine-5090远程分支，使用 `git switch --track origin/machine-5090`；不要创建同名无关历史。命令必须根据现有状态选择，不盲目照抄建分支步骤。

## 数据与凭据

- `upstream/` 和 `data/` 从固定版本恢复，不嵌套提交上游Git仓库。
- 权重、缓存、虚拟环境、大规模原始实验输出保留在执行主机ignored目录；回传小型manifest、SHA256、配置、必要合成案例与统计。需要同步完整原始实验时另外明确传输方案，Git回执不能替代原始证据保存。
- 不提交token、API key、.env、HF/GitHub凭据。认证在各设备本地完成，不在聊天或回执中发送令牌。
- 本仓库为private；远端需使用有权限的GitHub账号登录，才能clone与push。

## 运行状态

`NOT_STARTED`、`RUNNING`、`COMPLETED`、`BLOCKED`、`FAILED`需绑定具体任务；研究运行另区分debug/formal/invalid。CUDA检查成功不等于R0全部验收成功，更不等于R1/R2完成。

不要求后台轮询或定时通知。用户告知回执已push后，协调端拉取检查；若用户另行要求持续监控，再建立相应机制。
