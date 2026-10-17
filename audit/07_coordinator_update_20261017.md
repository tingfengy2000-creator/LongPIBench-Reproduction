# 协调端代码进展与回执审查（2026-10-17）

## 分工及回执结论

用户明确指定：本机Codex负责主要代码修改、方法与实验条件把控；实际5090电脑上的Cursor只承担明确派发的GPU执行和证据回传。

已拉取并核对 [PR #1](https://github.com/tingfengy2000-creator/LongPIBench-Reproduction/pull/1) 的commit `186e6dfdb527fffe84608b8fe530a2f312828c6b`。仅新增5个回执文件；已将该commit快进纳入本地main，完整保留原文件与历史。原始目录：`coordination/returns/20261017T101922Z-machine-5090-1bbf8a93/`。

结论接受：**BLOCKED**。回执记录的是Ubuntu24.04 Cloud VM（hostname cursor），无nvidia-smi、无CUDA设备；torch2.7.1+cu128安装成功与BNB可导入不能替代GPU验证。代码与200条数据恢复成功，HF Llama访问401，模型／适配器未加载。候选transformers5.20.1、PEFT0.21.2等未获验证，不能冻结为正式兼容栈。

## 本轮代码

| 代码 | 用途与边界 |
| --- | --- |
| `repro/hardware.py`、增强remote_preflight.py | 同一张卡必须同时匹配RTX5090与>=30000MiB总显存；失败记录BLOCKED、跳过torch检查并退出2。label不参与硬件判定 |
| `scripts/gpu_runtime_probe.py` | 真实硬件通过后才运行当前解释器的CUDA BF16及64×64合成NF4；再核对CUDA设备0型号和显存。不下载模型、不处理正式数据 |
| `repro/opi_loader.py` | 校验4个核心源文件，私有命名空间加载，绕过官方顶层无关SDK导入；仅将PromptLocate的一条absolute import改为relative import，差异单列patch |
| `configs/opi_core_sources.json` | 固定核心源码的SHA256；仅将CRLF规范化为LF后计算，支持Windows/Linux同一Git内容，不接受其他改动 |
| `repro/pipeline.py` | **debug-only**单例接线：原指令与非信任数据分开；未触发不调用定位；记录清洗文本与原始输出；捕获定位error日志和上游异常 |
| `repro/scoring.py` | 调用原官方parse/score并保留判定；缺字段／错类型／非有限数值单列F6；Not qualified的官方与审计差异显式保留，自由文本需复核 |
| `repro/archive.py` | 唯一RunID、config hash、每次attempt独立文件、拒绝覆盖、拒绝NaN序列化；原始字段和身份元信息分开 |

最小loader没有改检测、分段、搜索、恢复或模型生成函数。GPU环境中还要验证真实依赖及模型加载，不能将带依赖替身的导入测试当实际torch/PEFT兼容性证明。loader不执行官方顶层__init__，这项初始化路径差异已显式记录；不会把公开OpenPromptInjection命名空间替换成假模块。

debug接线在检测／定位异常时停止下游调用、标F6；原实现可能异常后把原文继续传给下游。这个调试控制流不是原文异常路径的等价执行，不当作有效防御结果。helper非有限数值的全链路观察、原字符坐标映射、真实tokens/stop reason、加载/显存轨迹和正式配置冻结仍未完成，故未提供正式runner。

评分审计规则不是人工真值，也没有覆盖原官方判定；歧义决策及评分分歧必须人工复核，不能依据自动审计列宣称任务正确或降低ASR。

合成NF4调用参数已对照 [bitsandbytes官方Linear4bit文档](https://huggingface.co/docs/bitsandbytes/reference/nn/linear4bit)；这仅支持API编写，真实GPU调用仍待任务002验证。

## 验证

- `python -m pytest tests -q --basetemp runs/test-temp-r0-code-3 -p no:cacheprovider`：**27 passed**。这是离线契约测试，不是实验样本。
- `python -m compileall -q repro scripts tests`：通过。
- 在本机真实5060运行要求5090的预检：返回**2**，hardware_gate=false，未执行torch。负对照证据在 `coordination/returns/20261017T105044Z-local-5060-negative-control-089dd9b7/preflight.json`。
- 上游源文件未修改；兼容import差异只在内存执行，文本记录为 `patches/opi_minimal_import.diff`。

测试覆盖无GPU拒绝、型号和显存必须属于同一设备、源hash和LF跨平台、无关SDK隔离、原检测预处理与0/1含义、加载失败清理、未触发跳过定位、可信指令不混入清洗、吞异常转F6、官方评分保留、schema无效、歧义复核、记录不可覆盖及NaN拒绝。

首轮临时测试目录父目录缺失导致5个fixture setup错误，创建工作区runs目录后复测通过；未据此修改方法或隐藏研究运行。后续新增预检CLI回归测试后总计27项通过。

## 下一步

派发 `R0-5090-002`：只在真实5090电脑的本地Cursor运行硬件、合成CUDA/NF4和最小OPI导入。缺包／版本错误回传给协调端，不在执行端自行升级依赖或改研究代码。DataSentinel checkpoint继续unknown，无正式ASR、无新方法设计。
