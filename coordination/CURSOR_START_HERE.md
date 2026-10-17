# 给真实5090设备本地Cursor的当前指令

**当前任务：R0-5090-005。** 真实5090环境与固定OPI最小导入已获用户回传通过；按 `coordination/tasks/R0-5090-005.md` 保存环境清单、恢复固定200条数据、执行HF固定config元数据访问预检。不重建环境、不重复安装、不下载权重、不运行正式实验。用户称已临时公开仓库以完成clone，不据此假定push或HF权限。

**最新接续：任务004的CLI修复已获用户回传通过。** Python3.11.17、pip check、全部核心依赖导入及blank sentencizer正常。按 `coordination/WSL_REPO_IMPORT.md` 接通WSL本地协作仓库，在machine-5090快进到origin/main，恢复固定上游、执行最小OPI导入并保存环境清单。不重复安装依赖，不创建模型实例。下面缺click和安装步骤保留为历史，以本段与任务004顶部最新状态优先。

**当前待修复：任务004阶段C的spaCy缺少click。** 安装和pip check已通过，实际导入失败；先执行任务004顶部的固定typer0.15.2、typer-slim0.15.2、click8.1.8修复与导入/空白分句检查。此修复由协调端确定，实际验证仍待回传；GPU合成检查历史通过，不重建环境或重新下载torch。

**最新接续：R0-5090-004阶段B用户回传通过。** 实际5090上的torch2.7.1+cu128、BF16、bitsandbytes0.46.1/NF4合成检查已通过；见 `coordination/returns/20261017T122535Z-user-wsl-gpu-smoke-004/REPORT.md`。沿用已有longpibench-r0，直接接续任务004阶段C完整依赖及最小导入，不重建环境、不重跑历史盘点。若尚无Linux仓库，任务004含同版本的无仓库安装命令。完整模型加载和正式实验尚未验收。以下较早步骤保留为历史，以本段和任务004最新状态为准。

**当前执行任务：R0-5090-004。** 用户已在真实5090的Ubuntu中确认Conda及下载入口。请读 `coordination/tasks/R0-5090-004.md`，仅创建新longpibench-r0/Python3.11环境，按固定版本安装并执行CUDA/NF4合成检查；通过后再装requirements中的完整候选。现有base/gmtp-compat/llmguard-paper1保持原状。主要代码与依赖修复仍由协调端负责，不启动正式实验。

**最新入口：**WSL内部已能看到真实5090，系统python3=3.12.3。交互Ubuntu出现(base)，当前按 `coordination/WSL_SHELL_AND_CONDA.md` 查询Linux侧Conda、当前Python/pip及公开下载入口。Ubuntu中直接运行Linux命令，不加Windows的wsl前缀，不安装apt提示的同名wsl包。先保留检查输出，由协调端给环境安装命令。

**最新进展：**Windows工具盘点已由用户手动回传。真实电脑已有Ubuntu-24.04 WSL2；当前按 `coordination/WSL_5090_NEXT.md` 在该电脑PowerShell启动现有发行版，确认WSL内部GPU、Python与Git，再由协调端给环境安装命令。下面的Windows盘点提示保留为历史，不需重复执行。

**当前任务：R0-5090-003。** 用户已从DESKTOP-B5PNBNC回传RTX5090/32607MiB/610.88。请在该电脑桌面的本地Cursor打开本地仓库，在machine-5090保护修改、fetch并合并origin/main，然后阅读 `coordination/tasks/R0-5090-003.md`，运行 `powershell -NoProfile -File .\scripts\windows_host_inventory.ps1`。只盘点现有环境并回传JSON，不安装依赖或下载模型，主要代码和方案仍由协调端负责。

以下为此前执行位置核验的历史说明，任务003优先：

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
