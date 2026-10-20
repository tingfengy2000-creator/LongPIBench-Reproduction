# B0强基线可用性审计

阶段状态：`PREPARATION_COMPLETE_HUMAN_LABEL_REVIEW_AND_REMOTE_AVAILABILITY_PENDING`。仅工程验证，**400候选条件尚未评分，B0未完成**。历史R0–R4/M1/M2/G0未改动。

## 固定身份与本机实测

| 基线 | 固定版本 | 当前证据 | 上限/精度/标签 |
| --- | --- | --- | --- |
| DataSentinel | Mistral-7B-v0.1@27d67f1b5f57dc0953326b2601d68371d40ea8da + large/checkpoint-5000 | 既有G0真实加载通过；B0-5090-001另派新独立加载控制，尚无新回执；本机CPU/5060不强行替代 | config32768/sliding4096；原NF4 double_quant BF16 compute；标记DGDSGNH存在→0，否则1；无原生注入概率 |
| Prompt Guard 86M | meta-llama/Prompt-Guard-86M@1209add6ca7d9c1d815171b8e5571587fe3e7b03 | 本机新B0进程加载及4控制真实前向通过，复用已有E盘权重 | DebertaV2TokenizerFast；config512；FP32；0 BENIGN/1 INJECTION/2 JAILBREAK |
| Prompt Guard 2 86M | meta-llama/Llama-Prompt-Guard-2-86M@a8ded8e697ce7c355e395a0df51f94adb4a2fd27 | 元数据可见，但本机认证账号固定config请求403；未下载权重、未加载；5090权限尚未知 | 官方卡512、BENIGN/MALICIOUS；**实际config/tokenizer/精度未验证，不倒填** |
| PIGuard | leolee99/PIGuard@dd78b24e330193a22d2293ac66922dd4f982f563 | 固定源码加载前已逐行审查，独立B0环境加载及4控制真实前向通过 | DebertaV2TokenizerFast；config512；FP32；0 benign/1 injection；class1 softmax |
| 零样本LLM | Llama-3.1-8B-Instruct@0e9e39f249a16976918f6564b8830bc894c89659 | 既有5090固定本地权重及短生成验收通过；B0新控制待回执；本机没有8B权重，不另下载/量化冒充 | 预定原BF16、不量化；固定JSON；最大上下文由B0远端实际config再记录 |

PG1实际总参数278,811,651，PIGuard184,423,682；“86M”沿用产品名称而非忽略embedding后的实测总参数。两个本机模型均为CPU FP32，torch2.7.1+cpu、transformers4.51.3、4线程；tokenizer长整数model_max_length为占位，不当作真实上下文。

权重SHA256：

- PG1：`1771712866662626517f2d85057de2d7078389a4c1f0bc93e461bdc4fdae4bd5`，1,115,271,284字节；复用原E盘文件并重新比对。
- PIGuard：`f90b9806de93b6286cda517300d4b55e5ce2e5ccbf8339dc59be21ca0dd9a25e`，737,719,272字节；本轮下载到E盘后与官方LFS摘要一致。
- DataSentinel adapter：`b1b023e63d3d49663187565c66d202c779dadf2af865d332643bd4a963125534`。这是作者ZIP首次观察摘要，不冒充HF revision；论文实际checkpoint仍unknown。
- PG2权重SHA未知，不能从产品名或其他模型猜测；远端可访问后按固定revision取得LFS/实际摘要。

所有小配置/源码/Tokenizer/权重文件摘要及本机控制logits、softmax、token IDs、输入hash、耗时见`source_audit/model_metadata.json`、`prompt_guard_1_load_probe.json`、`piguard_load_probe.json`。控制文本不来自400候选，控制标签未用来选模型/翻转语义。工程探针不估计检测性能；其输出不能替代Q1–Q4。

## 依赖、源码与存储

独立运行前缀`E:\LongPIBench\runs\b0_runtime`；通过只读.pth复用既有CPU环境依赖，不安装/卸载旧环境包。模型权重、HF Hub/Xet/assets/modules、Torch及下载TEMP/TMP均在`E:\Caches\longpibench-b0`。本机RTX5060 8151MiB，本轮探针不用GPU；最终B0延迟比较拟在同一5090完成，不把CPU与GPU当同条件速度对比。

PIGuard的auto_map源码SHA、完整阅读范围和不执行的辅助脚本见`source_audit/custom_code_review.md`。它输出原始分类logits，后续softmax只是类别分数。官方短示例含truncation=True，B0不照搬为全文处理：使用官方tokenizer原生special封装、非重叠全覆盖窗口、固定Max。与历史LongPIBench全局special后硬切的差异已在协议明示。

一次创建E:\Caches下运行环境的普通沙箱写入失败，未修改已有环境；随后在授权工作区的ignored runs建立独立前缀成功。初次HF缓存提示Windows无symlink权限，仅涉及E盘缓存存储方式；未为此提权、更改Windows设置或下载到C盘。

## RAPIDS可执行性

已检查[官方ACL论文](https://aclanthology.org/2026.acl-industry.127/)、[论文PDF](https://aclanthology.org/2026.acl-industry.127.pdf)及其[OSF数据入口](https://osf.io/ujyva/overview?view_only=fa95a71b23424e98a68a08d35f9afcd4)，并检索作者与题名对应代码/权重。论文声明公开的是攻击seed与合成注入片段，完整增强Resume因底层专有数据不能发布；OSF网页本轮工具访问失败，不能声称已经下载验证其内容。

本次没有定位到可取得并核验的官方RAPIDS完整代码、fine-tuned权重及完整评测数据链，状态`NOT_EXECUTABLE_OFFICIAL_CHAIN_NOT_VERIFIED`。这不是证明永远不存在公开实现。通用Sentinel、Defender及本轮PIGuard→LLM简单级联均不能冒充RAPIDS，不给RAPIDS伪造结果。

模型原始资料：[PG1固定卡](https://huggingface.co/meta-llama/Prompt-Guard-86M/blob/1209add6ca7d9c1d815171b8e5571587fe3e7b03/README.md)、[PG2官方卡](https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M)、[PIGuard官方仓库](https://github.com/leolee99/PIGuard)、[PIGuard模型](https://huggingface.co/leolee99/PIGuard)。网络资料只用于身份/实现审计，不作为本轮性能数字。

## 下一步执行边界

1. 用户审核label_review.html/CSV并签认最终标签、manifest和协议摘要；当前尚未签认。
2. 5090只执行B0-5090-001可用性任务；403或auto_map未审源码按阻碍回传，不更换模型。
3. 两项完成后才冻结最终运行配置并派发400条件检测、B4/B5及级联；不在本轮准备状态下自动启动评分。
