# 给真实5090设备本地Cursor的当前指令

**当前执行：R0-5090-014独立Email条件。** 013摘要777f194已核验：搜索段数持续减少，012观察预算截断了推进过程。按coordination/tasks/R0-5090-014.md执行run_email_continuation.py --stage all，从相同原输入重跑两条Email定位；观察8192/3600秒，模型/方法配置不变，旧记录保留。自动比较旧已完成逻辑前缀并附新轨迹摘要；定位有效后才独立生成Llama输出。无防御、Resume、环境不重跑；遇失败按任务保留证据，不自行放宽预算或修方法。以下为历史指令。

**当前执行：R0-5090-013既有轨迹分析。** 012三阶段回执cbe3dca已集成：完整PromptLocate构造及6次真实目标生成已完成，两条Email定位受调试观察预算中断。按coordination/tasks/R0-5090-013.md运行标准库只读分析器analyze_debug_trace.py，仅导出本地raw的真实generate/oracle计数、搜索进度及末尾错误；不使用GPU、不改预算、不重跑样本/环境。原始hash必须匹配，不改旧证据，不自行继续GPU任务。以下为历史指令。

**当前执行：R0-5090-012真实样本调试。** 011三适配器工程验收通过，0476ab8祖先已集成。按coordination/tasks/R0-5090-012.md执行唯一命令run_debug_pilot.py --stage all，顺序运行无防御Llama、完整检测定位、恢复后Llama三个独立GPU阶段。预先固定Email/Resume ID0，干净/攻击及两条件；512token仅debug预算。不重做环境检查，不依据输出改参数或选择large/small，不计算ASR；原始输入/输出及轨迹留runs，Git只提交小型回执与日志。失败按任务保留证据，不自行改代码。以下为历史指令。

**当前执行：R0-5090-011。** 010的prepare/spaCy/tokenizer已通过，原回执ba6d4bc已集成。large因协调端工具错误要求导出张量集合全等而停止，原失败证据保留；修正后仍严格检查所有适配器张量，并将唯一额外输入embedding与固定底座逐值核对。按coordination/tasks/R0-5090-011.md复用实际010 prepare回执，仅large、small、oracle依次独立GPU进程运行；遇失败停止后续。不重装/提取/下载，不重跑已通过阶段，不改依赖或方法，不选正式checkpoint。以下为历史指令。

**当前执行：R0-5090-010。** 007文件回执8657879已审查并保留祖先关系。按coordination/tasks/R0-5090-010.md先prepare，仅提取6个推理文件并安装已校验本地spaCy wheel；成功后使用实际prepare回执，分别检查原spaCy初始化、真实Llama tokenizer单BOS，以及large/small/oracle逐进程适配器加载与短合成query。分句检查失败原样报告，可继续本任务明确授权的独立适配器检查；任一适配器失败停止后续适配器。不重下HF、不重跑007/009、不改方法或正式checkpoint、不跑正式样本。以下为历史指令。

**当前执行：R0-5090-007资源准备。** 009的三套模型GPU加载/短合成检查已审查通过，101c124历史已集成。按coordination/tasks/R0-5090-007.md先检查并复用已有资源，再获取/验证两个官方Drive ZIP及固定spaCy wheel；只回传小型aux_downloads.json和REPORT.md。不重下HF模型、不重跑009，不提取/安装/加载adapter或跑正式数据。协调端已修正检查脚本重复BOS，未替换原始009证据，正式消息格式仍待后续验证。下面各段为历史指令，以本段及007当前接续为准。

**当前执行：R0-5090-009。** 006的GPT-2/Mistral和008的Llama共31个文件回执已审查，保留5f02133历史。按任务009在真实5090 WSL用已有E盘链接顺序加载helper、detector_base、target，每条命令独立进程；全程本地、无下载、无adapter、独立合成短输入，不运行正式数据。007资源仍有效，完成状态待回执。不重下/复制/移动模型，失败交协调端处理。

**当前队列：006保持运行，008排队直接下载Llama。** 新账号的三个固定config访问已通过并集成7cf3b28；不再安排网盘，不更换目标。不要停止Mistral或删除GPT-2缓存。006自然结束后按coordination/tasks/R0-5090-008.md下载/校验target的13个文件，不重下其他role；无需再次等协调端批准。007非HF资源任务保持有效，不自动重复已运行任务。此阶段不加载模型或启动正式实验。

**当前分工更新：HF三模型走合法离线交接，执行端做007非HF资源准备。** 见coordination/OFFLINE_MODEL_HANDOFF.md。保留原Llama目标和Rejected记录，不执行Qwen候选；006已有HF文件复用。按coordination/tasks/R0-5090-007.md下载两个官方Drive包和spaCy wheel，只验证文件，不安装/加载模型或运行正式实验。

**Llama账户状态已变为Rejected。** 任务005停止同一请求重试，历史登录/403回执保留；任务006公开GPT-2/Mistral准备继续。不要自行换目标或扩大运行范围。协调端已整理独立目标候选方案audit/09_llama_access_rejected_and_target_options.md，尚未建立新目标执行任务。

**任务006快进接续：四次原始403回执已集成。** 协调端已取回75547e0并保留其祖先关系，同名REPORT双份保留。真实5090本机在machine-5090保护已有工作区，fetch后merge --ff-only origin/main，按任务006继续公开GPT-2/Mistral下载和哈希校验。无需重装环境、重复登录或再次请求Llama；006文件下载尚未验收。以任务006最新接续和审查REVIEW为准。

**当前可执行：R0-5090-006。** 用户的Llama申请审核中，任务005保留阻碍。真实5090本地Cursor按任务006准备公开GPT-2/Mistral固定文件，执行下载与官方大小/hash校验，回传唯一路径及状态。不读取HF凭据、不下载Llama、不替换目标、不选DataSentinel checkpoint、不运行正式实验。协调端保持主要代码与方法控制。

**当前接续：任务005的Llama本机认证。** 环境004已按用户回执完成，200条数据通过，Mistral/GPT-2配置访问通过。Llama请求401且未检测到HF凭据。请在真实5090本机Cursor执行任务005“当前接续”一节，用户本地交互登录HF后重跑预检，保留旧return目录并报告新结果。不重复安装或下载数据，不使用Cloud Agent，不读取/发送用户令牌。主要代码及方法由协调端维护。

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
