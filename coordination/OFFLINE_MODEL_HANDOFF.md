# 给下载协作者：HF三套模型的固定版本离线交接

状态更新（2026-10-18，Asia/Tokyo）：用户已在5090本地更换账号并通过三个固定config访问，当前不再安排网盘交接。006保持运行，Llama直接下载按任务008执行。本文件仅保留为离线文件验收/历史交接参考，不继续委托重复下载。

日期：2026-10-17。当前保留原Llama目标，不切换Qwen。仅委托HF模型；Google Drive适配器及spaCy模型由研究执行端自行获取。

## 需要下载的HF模型

| 用途 | 官方仓库 | 必须固定的revision | 选定文件大小 |
| --- | --- | --- | --- |
| 目标模型 | meta-llama/Llama-3.1-8B-Instruct | 0e9e39f249a16976918f6564b8830bc894c89659 | 16,069,779,031字节，约16.07GB |
| DataSentinel/PromptLocate共用底座 | mistralai/Mistral-7B-v0.1 | 27d67f1b5f57dc0953326b2601d68371d40ea8da | 14,485,815,439字节，约14.49GB |
| 定位helper | openai-community/gpt2 | 607a30d783dfa663caf39e06633721c8d4cfcd7e | 550,967,953字节，约0.55GB |

共3套、31个选定文件、31,106,562,423字节，约31.11GB（十进制），不含打包、缓存与文件系统开销。若5090的006已完成Mistral/GPT-2，则只需补交缺失部分，优先Llama。

仓库链接：

- https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct
- https://huggingface.co/mistralai/Mistral-7B-v0.1
- https://huggingface.co/openai-community/gpt2

精确文件名、大小、LFS SHA256/Git blob SHA1见configs/offline_transfer_manifest.json。文件元数据来自上述固定commit的官方API；没有从此元数据访问推断能下载gated文件。

## Llama来源及许可

由对该模型有合法访问权、且能按适用许可分发文件的协作者获取和转交；使用者与转交者都需符合许可条件。随文件保留LICENSE、USE_POLICY.md、README.md及许可要求的NOTICE/归属说明。Llama许可允许有条件的再分发，具体条件见官方LICENSE；本清单不作任何个人/机构符合资格的认定。

https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct/blob/main/LICENSE

不转交账号、令牌、登录缓存或密钥。HF申请被拒绝仍单独记录；收到合法离线模型并不等于该HF账号获得访问批准。

## 下载与验证（协作者自己的独立环境）

取得本项目代码/ZIP，在项目根目录使用Python3.11和huggingface-hub0.30.2。协作者需要Llama时，在本机终端用自己的授权账号执行huggingface-cli login，不在聊天或脚本参数中填写token。

下载全部三套：

```bash
python scripts/offline_hf_bundle.py --download --bundle-dir LongPIBench-offline
```

若只需交Llama：

```bash
python scripts/offline_hf_bundle.py --download --roles target --bundle-dir LongPIBench-offline
```

也可只选择缺失的detector_base/helper。工具按清单使用local_dir下载，只保存已指定的HF正文文件；校验发现完整文件不匹配时停止该模型，不覆盖旧文件。下载失败可保留未完成缓存后重试；不要自行换revision、权重格式或量化版本。

需要原始HF Safetensors权重及配套配置/tokenizer。不要改成GGUF、GPTQ、AWQ、预量化bnb或第三方微调版；不要只给权重分片而遗漏tokenizer/配置/索引。Llama应有4个model-0000x-of-00004.safetensors和索引；Mistral应有2个分片和索引；GPT-2使用model.safetensors。精确名称以JSON清单为准。

## 网盘交接

目录保持：

```text
LongPIBench-offline/
  hf/
    target/          # Llama正文文件
    detector_base/   # Mistral正文文件
    helper/          # GPT-2正文文件
  <UTC>-offline-hf-<ID>.json  # 工具生成的文件哈希及固定来源回执
```

仅打包实际提供的模型目录、验证回执及必要许可说明，不打包用户目录、HF凭据缓存或项目.git。模型必须是实际文件，不能只发送指向另一台机器缓存的符号链接。不要把模型上传到本项目Git。可经用户选定的网盘传输，保留原目录名；无需另建公开模型仓库。

接收端先按清单离线验收，不加载模型、不联网：

```bash
python scripts/offline_hf_bundle.py --bundle-dir /实际/LongPIBench-offline
```

只收到Llama时加--roles target。路径按接收端实际系统替换，不混用Windows与Linux路径。离线验证不导入huggingface_hub、不读取HF凭据、不修改原模型配置。

输出FILES_VERIFIED_NOT_MODEL_LOADED只表示文件与官方元数据哈希一致，不证明来源的许可资格、模型加载或正式实验已通过。接收后由协调端另派5090本地加载任务；原HF访问403/Rejected证据继续保留。

## 由我们自行获取的其余资源

| 包 | 来源 | 已观察下载大小 | 用途 |
| --- | --- | --- | --- |
| DataSentinel_Models.zip | 官方Google Drive | 1,401,845,934字节 | 含large/checkpoint-5000与small/checkpoint-500，两份检测adapter |
| promptlocate_oracle.zip | 官方Google Drive | 701,657,336字节 | 专用定位oracle adapter，checkpoint-500 |
| en_core_web_sm-3.8.0-py3-none-any.whl | spaCy官方GitHub Release | 12,806,118字节 | PromptLocate英文分句所需spaCy模型 |

三份非HF资源合计约2.12GB；对应3份LoRA checkpoint和1个小型spaCy模型。正式DataSentinel选择仍unknown，两种均保留，不根据正式ASR挑选。详见任务R0-5090-007。它们不是三套HF底座的替代品。
