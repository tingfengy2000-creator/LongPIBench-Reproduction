# 现有Ubuntu-24.04 WSL2：下一步入口

最新结果：用户已完成本页第一批检查，WSL内部能看到5090/32607MiB/610.88，系统python3=3.12.3。交互Ubuntu提示符带(base)，且曾误把Windows侧wsl命令输入Ubuntu。当前请转到 [终端切换与Linux侧Conda检查](WSL_SHELL_AND_CONDA.md)，不再重复下面的GPU查询，不安装Linux同名wsl包。

用户已经回传Windows侧工具盘点：Git可用，py launcher列出Python3.14，Conda未在当前PATH找到；Ubuntu-24.04已存在，WSL版本2，当前Stopped。该信息不代表Ubuntu内部的Python版本或GPU已验证。

## 执行以下只读检查

直接在真实5090电脑当前Windows PowerShell逐行执行。wsl命令会启动已有发行版，无需重新安装Ubuntu；Windows的Python3.14保持现状。

```powershell
wsl -d Ubuntu-24.04 -- hostname
wsl -d Ubuntu-24.04 -- /usr/lib/wsl/lib/nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
wsl -d Ubuntu-24.04 -- python3 --version
wsl -d Ubuntu-24.04 -- which git python3 pip3
```

回传完整输出，包括缺少工具或WSL首次初始化的提示。任何命令失败时保留原文，不转到Cloud Agent重试。`which`只会列出找到的工具，缺少pip3也可能使其退出非零，并不证明GPU故障。

使用 `/usr/lib/wsl/lib/nvidia-smi` 是为避免WSL中工具不在PATH的情况。依据：[NVIDIA CUDA on WSL指南](https://docs.nvidia.com/cuda/wsl-user-guide/index.html)。该指南要求使用Windows映射的驱动，不在WSL另装Linux显卡驱动；本阶段也不安装完整CUDA Toolkit或重新安装WSL。

## 确认后执行方案

优先在此发行版的Linux文件系统内建立独立项目及venv，避免直接修改Windows Python或系统Python。Linux解释器版本先以实际输出为准，再确定是否复用；不凭Ubuntu名称自动记为3.12或强制安装3.11。

兼容候选沿用已有审计方向：PyTorch2.7.1的cu128官方wheel可用；bitsandbytes当前官方12.8构建列出sm120。但这只是候选依据，不是该机器CUDA/NF4实测通过，也不代表沿用Cloud VM自动解析出的transformers5.20.1栈。

依据：[PyTorch官方历史wheel](https://pytorch.org/get-started/previous-versions/)、[bitsandbytes官方构建矩阵](https://huggingface.co/docs/bitsandbytes/main/en/installation)。取得WSL输出后，由协调端冻结兼容候选包版本和安装命令，执行端再运行；不运行正式R1/R2，不更改DataSentinel checkpoint选择或方法。
