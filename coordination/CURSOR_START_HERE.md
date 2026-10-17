# 给真实5090设备本地Cursor的当前指令

**2026-10-17最新入口：**任务002再次落到无GPU Cloud VM。用户已确认能进入5090电脑的Windows PowerShell，请先阅读 [Windows本机连接说明](WINDOWS_5090_CONNECT.md)，直接在真实电脑取得GPU输出；暂不把下列提示再次发给Cloud Agent。两次原始回执均已保留，硬件检查正确拦截，未做GPU实验。

**当前任务已更新为R0-5090-002。** 上次执行进入了无GPU的Cloud VM，状态BLOCKED。请在5090电脑桌面的本地Cursor终端执行下面这段：

```text
你只负责明确的GPU执行，主要代码和方法由协调端Codex负责。
仓库：https://github.com/tingfengy2000-creator/LongPIBench-Reproduction
先运行 nvidia-smi --query-gpu=name,memory.total --format=csv，确认5090及约32GB。
没有对应硬件就停止，不在Cloud VM安装或下载。
保护现有修改，fetch origin，在machine-5090合并origin/main。
阅读AGENTS.md、coordination/PROTOCOL.md和coordination/tasks/R0-5090-002.md。
按任务运行硬件、已有环境的合成CUDA/NF4和最小OPI导入。
缺包/代码故障原样回传，不自行升级依赖或改主要代码，不启动正式实验。
将新回执提交到machine-5090并push，报告commit SHA。
```

第一条项目预检命令：

```text
python scripts/remote_preflight.py --label actual-5090 --task-id R0-5090-002 --require-gpu "RTX 5090" --min-vram-mib 30000
```

以下内容为任务001的历史指令，已被任务002替代，不再执行：

下面整段可直接发给远端Cursor。仓库已创建为private，先在该设备登录有仓库权限的GitHub账号。若尚未克隆，Cursor可以先使用终端完成clone并打开目录。

---

请执行 LongPIBench 的 R0-5090-001 任务。你是GPU执行端，本机Codex是协调端，通过Git仓库通信：

`https://github.com/tingfengy2000-creator/LongPIBench-Reproduction`

若本地没有项目，克隆到合适的新目录：

```bash
git clone https://github.com/tingfengy2000-creator/LongPIBench-Reproduction.git
cd LongPIBench-Reproduction
```

先检查git status和远程分支：

```bash
git status --short
git fetch origin
git branch -a
```

若machine-5090分支不存在，新建 `git switch -c machine-5090`；若已有origin/machine-5090，切换或跟踪它。已有未提交修改时先保护现状，不reset或覆盖。将origin/main合并到工作分支，再阅读：

1. AGENTS.md
2. coordination/PROTOCOL.md
3. coordination/tasks/R0-5090-001.md
4. audit/00_reproduction_environment.md
5. audit/04_findings_and_blockers.md

当前唯一目标是完成R0硬件／环境准备和真实回执，不开展正式R1/R2，不设计SALT。

先执行：

```bash
python scripts/remote_preflight.py --label machine-5090
python scripts/bootstrap_upstreams.py --download-data
```

Linux可使用python3，Windows可使用py；按实际情况选择并记录。若torch未安装，第一条仍会产出缺包报告。按任务文档复用或建立独立环境，验证CUDA/BF16/NF4，盘点目标模型和适配器。记录完整命令、版本、错误，不输出任何token；不要把本机5060的历史报告改成5090结果。

将preflight脚本打印的实际return目录记作RETURN_DIR，在该目录新建REPORT.md，说明任务结果、阻碍和下一步。只提交本次明确的回执文件，例如：

```bash
# 用实际路径替换这里的RETURN_DIR，不要照抄占位符。
git add coordination/returns/RETURN_DIR/preflight.json coordination/returns/RETURN_DIR/REPORT.md
git commit -m "Report R0-5090-001 hardware and environment preflight"
git push -u origin machine-5090
```

如果补充了不含凭据的环境锁或必要兼容性文件，明确检查后一起提交。不要git add整个模型/数据目录，不强推，不向main直接写入，不为追求ASR修改攻击条件或checkpoint选择。完成后向用户报告commit SHA、任务完成程度和仍未解决项。

---

Git是文件交接渠道；此处没有声称已远程控制、唤醒或向Cursor发送消息。需要用户连接设备并将上述指令发给Cursor启动工作。
