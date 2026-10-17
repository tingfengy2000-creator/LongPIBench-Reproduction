# R0-5090-005 接续回执（HF 登录后重跑）

- 任务：`R0-5090-005`
- 新运行 ID：`20261017T132208Z-model-access-e778ccf1`
- 主机：`DESKTOP-B5PNBNC`（Ubuntu-24.04 WSL）
- 环境：`longpibench-r0`
- 分支：`machine-5090`
- 输入 commit：`b87587c4deaa6f688cbd80481f64dcbdcb015a88`
- Python：`conda run --no-capture-output -n longpibench-r0 python scripts/model_access_preflight.py --task-id R0-5090-005`
- 退出码：2
- 任务状态：**BLOCKED**（`BLOCKED_CONFIG_ACCESS`）
- 未下载权重、未加载模型、未启动正式实验，未改核心方法。

## 保留的旧结果

未删除、未改写：

- `coordination/returns/20261017T125418Z-model-access-bdec4d14/`（登录前，Llama HTTP 401，`local_hf_credential_present=false`）
- `coordination/returns/20261017T125504Z-user-model-access-005/`（协调端已收录的同一旧运行）
- `coordination/returns/20261017T132133Z-model-access-52577365/`（登录后较早一次，Llama HTTP 403；本次正式回传用下面新 ID）

## 登录后新结果

`local_hf_credential_present=true`。本机 `huggingface-cli whoami` 显示已登录账号为 `tingfenggg`。未读取、未记录、未发送 token。

| 角色 | 仓库 / revision | 状态 |
| --- | --- | --- |
| target | `meta-llama/Llama-3.1-8B-Instruct` `@0e9e39f249a16976918f6564b8830bc894c89659` | `ACCESS_OR_NETWORK_ERROR`，`GatedRepoError`，HTTP **403** |
| detector_base | `mistralai/Mistral-7B-v0.1` `@27d67f1b5f57dc0953326b2601d68371d40ea8da` | PASS |
| helper | `openai-community/gpt2` `@607a30d783dfa663caf39e06633721c8d4cfcd7e` | PASS |

对比：登录前 Llama 为 **401**（无凭据）；登录后为 **403**（有凭据，gated 仍拒绝）。403 不能写成“未登录”，也不能自行推断网页申请是否已批准。未更换模型或 revision，未绕过访问限制。

## 阻碍与未完成项

- 账号 `tingfenggg` 对固定 Llama revision 的 config HEAD 仍 403。需要用户在浏览器打开 https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct 确认该账号是否已获授权并接受协议；未获授权按页面申请。批准后再重跑同一预检。
- 本任务仍不覆盖权重下载、完整性校验、GPU 加载或 R1/R2。
- DataSentinel large/small 仍为 unknown。

证据：`coordination/returns/20261017T132208Z-model-access-e778ccf1/model_access.json`
