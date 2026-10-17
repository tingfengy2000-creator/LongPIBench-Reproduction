# 在真实5090电脑的Windows PowerShell确认执行位置

更新：用户已完成下面的身份检查并回传DESKTOP-B5PNBNC、RTX5090、32607MiB、驱动610.88。当前不需重复人工检查，进入任务R0-5090-003的Python/Conda/WSL盘点；保留以下步骤供首次在该电脑建立本地项目时参考。

用户已确认可以进入5090电脑桌面并打开Windows PowerShell。前两次回执来自无GPU的Cursor Cloud VM，GPU步骤均未执行。当前先做以下两步，不需要Python、Hugging Face登录或模型下载。

## 先由用户在5090电脑自己的PowerShell执行

```powershell
$env:COMPUTERNAME
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
```

将两条命令的文本输出发给协调端即可。若看到RTX5090及约32GB显存，再继续项目准备；若nvidia-smi报找不到命令，保留错误先排查这台Windows电脑的驱动／工具位置，不转到Cloud VM安装。

这里的PowerShell必须属于真实5090电脑。即使从那台电脑打开了Cursor，向Cloud Agent派发任务仍可能在云端运行；仓库名、分支名和任务label不能证明显卡位置。

## 身份确认后，再准备项目目录

使用已经具备本私有仓库访问权限的GitHub账号，在该电脑新建合适的项目目录。首次克隆可执行：

```powershell
git clone https://github.com/tingfengy2000-creator/LongPIBench-Reproduction.git
Set-Location -LiteralPath .\LongPIBench-Reproduction
git fetch origin
git switch --track origin/machine-5090
git merge origin/main
```

已有项目时先检查git status，保护未提交修改，再fetch、切换现有machine-5090、合并origin/main。不要重复clone到已有目录，不reset、不强推。

用桌面Cursor打开该本地项目，在本地终端再次运行前面的GPU查询，确认位置后让本地Agent按R0-5090-002执行。当前两次Cloud回执不等于这台Windows电脑已有Python环境；协调端依据真实机器反馈给安装命令。

## 分工

主要代码、依赖适配方案和方法配置由协调端Codex负责。5090端执行明确的检查和GPU命令、保存原始错误与结果、push小型回执；不自行改方法、调ASR或升级整套依赖。硬件未确认前不继续CUDA/NF4、模型下载或正式实验。
