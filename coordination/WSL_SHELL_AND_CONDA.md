# 终端切换与Linux侧Conda检查

当前用户证据已经确认：Ubuntu-24.04内部能查询5090/32607MiB/610.88，非交互python3为3.12.3，/usr/bin/git可用；pip3未出现在which输出中。用户进入交互Ubuntu后提示符出现(base)，可能已有Linux侧Conda，需查询确认。这不与先前Windows PATH无Conda矛盾。

## 第一步：只在Windows PowerShell执行

用户已exit回到 `PS C:\windows\system32>`，此处执行：

```powershell
wsl -d Ubuntu-24.04
```

## 第二步：只在Ubuntu提示符下执行

看到 `(base) tingfeng@DESKTOP-B5PNBNC:...$` 或普通Linux用户提示符后，执行下列Linux命令。此处不再加 `wsl -d ... --` 前缀。

```bash
cd ~
hostname
command -v conda
conda --version
conda env list
command -v python
python --version
python -m pip --version
curl -I --connect-timeout 10 --max-time 20 https://pypi.org/simple/
curl -I --connect-timeout 10 --max-time 20 https://download.pytorch.org/whl/cu128/
```

若conda、python或curl未找到，保留错误回传，不根据系统建议自动apt安装。此批仅检查已有环境及两个公开下载入口，不安装软件、不修改代理、不下载模型。不要输出任何token或完整代理环境变量。

`wsl` 是Windows侧入口。微软文档说明Linux终端若要调用Windows WSL管理程序应使用wsl.exe；本任务已在Ubuntu内，直接运行Linux命令即可，无需安装apt提示的Linux同名包。[微软WSL命令说明](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)

## 代理提示的处理

localhost代理未镜像的提示没有阻止当前已完成的GPU查询，但尚未验证下载。上述两个curl检查用于确定是否实际影响网络；若失败再由协调端根据错误制定方案，不直接重写.wslconfig、关闭用户代理或改全局网络配置。[微软WSL网络说明](https://learn.microsoft.com/en-us/windows/wsl/networking)

拿到Conda与网络输出后，由协调端给出单独环境的明确版本和安装命令，避免在base安装研究依赖。Linux用户目录是后续项目位置，当前不在/mnt/c/windows/system32写入项目。
