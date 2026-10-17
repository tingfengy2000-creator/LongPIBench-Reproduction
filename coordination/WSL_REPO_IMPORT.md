# 真实5090：WSL协作仓库与固定OPI最小导入

接续任务R0-5090-004。GPU合成检查和CLI依赖修复已获用户回传通过，不重建环境或安装软件。下列命令在DESKTOP-B5PNBNC的Ubuntu Bash执行。仓库放Linux用户目录，不使用协调端E盘路径。

## 仓库连接和核心导入

使用默认目录 `~/LongPIBench-Reproduction`。目录不存在时新克隆；已存在时仅接受该项目Git仓库且工作区干净。已在其他路径有本任务仓库时，应使用实际路径，不再克隆第二份。命令任何一步失败会停止。私有仓库需要本机已有GitHub授权；若出现认证错误或密码提示，先停下回传提示，由协调端安排本地认证，不把凭据粘贴到聊天。

```bash
(
set -e
test "$(hostname)" = "DESKTOP-B5PNBNC"
cd ~
if [ ! -e LongPIBench-Reproduction ]; then
  git clone https://github.com/tingfengy2000-creator/LongPIBench-Reproduction.git LongPIBench-Reproduction
fi
cd LongPIBench-Reproduction
case "$(git remote get-url origin)" in
  https://github.com/tingfengy2000-creator/LongPIBench-Reproduction.git|git@github.com:tingfengy2000-creator/LongPIBench-Reproduction.git) ;;
  *) echo 'Unexpected repository origin; stop.'; exit 1 ;;
esac
if [ -n "$(git status --porcelain)" ]; then
  echo 'Working tree has changes; stop and preserve them.'
  exit 1
fi
git fetch origin
if git show-ref --verify --quiet refs/heads/machine-5090; then
  git switch machine-5090
else
  git switch --track origin/machine-5090
fi
git merge --ff-only origin/main
git rev-parse HEAD
conda run --no-capture-output -n longpibench-r0 python scripts/bootstrap_upstreams.py
conda run --no-capture-output -n longpibench-r0 python -c 'from repro.opi_loader import load_opi_core; c=load_opi_core(); print(c.DataSentinelDetector.__name__, c.PromptLocate.__name__); print(c.provenance); print("Pinned OPI core import: PASS")'
)
```

若分支不能快进，保留现状回传，不reset、不强推，也不自动另造分支。任务004以本文件接续步骤优先，前述阶段A/B/C安装指令仅作历史与首次恢复参考。

此步骤仅下载固定版本上游代码，不下载数据或模型；不创建DataSentinel/PromptLocate实例。loader会核对固定源码哈希，记录唯一的导入路径兼容变换。不证明模型可加载、原方法分句可用或实际检测定位有效。

## 依赖清单本地保存

上面通过后，在该项目根目录保存完整环境清单供后续审查。新目录不可覆盖，runs目录被Git忽略；先不提交这些原始清单。

```bash
(
set -e
cd ~/LongPIBench-Reproduction
mkdir -p runs
ENV_RECORD_DIR=$(mktemp -d "runs/r0-env-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
conda run --no-capture-output -n longpibench-r0 python -m pip freeze > "$ENV_RECORD_DIR/pip-freeze.txt"
conda list -n longpibench-r0 --explicit > "$ENV_RECORD_DIR/conda-explicit.txt"
git rev-parse HEAD > "$ENV_RECORD_DIR/coordinator-code-commit.txt"
sha256sum "$ENV_RECORD_DIR"/*
printf 'Environment saved: %s\n' "$ENV_RECORD_DIR"
)
```

将上游恢复与OPI导入的输出、清单保存路径及哈希回传即可。不需要整份贴出含本地渠道URL的清单；后续小型Git回执遵循PROTOCOL并先检查凭据。实际模型与adapter预检另行派发，本文件不启动正式R1/R2。
