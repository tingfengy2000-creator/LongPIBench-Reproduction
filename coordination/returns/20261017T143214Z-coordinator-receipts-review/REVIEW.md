# 5090四次403原始回执集成审查

审查日期：2026-10-17。来源分支origin/receipts-5090-75547e0，来源commit为75547e0a8aa4492eaa25369b86b4ddbb46d1e295。与集成前main的共同祖先为b87587c4deaa6f688cbd80481f64dcbdcb015a88。用户报告本机仍在该HEAD，已将其推送到独立分支成功；协调端fetch核对完整SHA一致。

## 范围与原始证据

相对共同祖先仅有四个运行目录的8份新增文件（4个REPORT.md、4个model_access.json），无核心代码、方法、依赖、数据或权重变更。常见HF/GitHub令牌与私钥标记扫描未检出。逐文件来源路径、集成路径、原始Git blob和SHA256见blob_manifest.json；8份来源文件均逐字节保留。

运行ID与实际输入代码：

| Run ID | JSON记录的输入commit |
| --- | --- |
| 20261017T132208Z-model-access-e778ccf1 | b87587c4deaa6f688cbd80481f64dcbdcb015a88 |
| 20261017T133331Z-model-access-8ad2a511 | 44290b6a9ff3d845e1a240289a2f220fd5c0c1c5 |
| 20261017T134334Z-model-access-a54a3d6a | 053a8d9fff41ffbf33b8db9c97fc9c0935cb816d |
| 20261017T134526Z-model-access-fd55a183 | a330a2469141f4e86813c47f1de4c6726f52919a |

四个JSON均满足：task_id=R0-5090-005，hostname=DESKTOP-B5PNBNC，local_hf_credential_present=true；Llama为ACCESS_OR_NETWORK_ERROR、HTTP403，Mistral/GPT-2为PASS；所有模型ID/revision与upstream_lock一致。均无权重下载、模型加载或正式推理。输入commit随前一回执提交变化，未把四个运行错误写成相同输入commit。

## 同名原始文档冲突

20261017T132208Z-model-access-e778ccf1/REPORT.md在GitHub已发布分支与5090本机分支内容不同，产生add/add冲突。

- 原路径保留GitHub已发布的REPORT.md，blob a7d256ea166f35743d061eb91d2219ca758d999d。
- 5090本机原文逐字节保存在同目录REPORT.local-5090-original.md，blob a0fe5308ea073431339e05a4eda2e52f3cba2195。
- 本机原文包含退格控制字符0x08等格式差异，未修复或替换其原始字节；JSON不受此Markdown格式差异影响。

来源提交及其父链保留在merge历史中，不做cherry-pick、squash、rebase或强推；新增解释与原始回执分开存放。

## 接续结论

审查接受四次回执，但R0-5090-005仍为BLOCKED：已登录后403，用户称模型访问申请审核中，不能称未登录或已获模型权限。无需反复登录或重复请求。

本次main通过正常merge保留75547e0祖先关系，并保留此前已合入的752f52f。提交与push后，须用merge-base --is-ancestor分别验证两个来源提交；验证通过即解除006的既知分叉阻碍。执行端保持machine-5090，在工作区无已跟踪修改时fetch并merge --ff-only origin/main后，按原任务006下载公开GPT-2/Mistral并校验文件。

本结论不宣称006已下载成功、GPU模型加载通过或任何正式实验结果。用户所述本机SSH网络处理仅是执行端push成功的说明，协调端没有验证或修改其SSH配置。
