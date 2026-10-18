# 任务二：新的领域×长度验证资料可行性设计（只准备）

**资料可访问，但共同长区间支持尚未证明。**本轮仅获取两个公开接口各前20条作长度/来源检查，没有检测器评分、没有800源采集。40条已阅预览固定为设计开发资料，排除在未来冻结测试外。

## 候选来源与当前观察

1. Email上游候选：[CMU Enron官方分发页](https://www.cs.cmu.edu/~enron/)，来自约150用户的邮件档案，提供研究使用说明。可浏览镜像[corbt/enron-emails](https://huggingface.co/datasets/corbt/enron-emails)在当前`cfc06c758093d90993abce1a43668fb7357258a6`公开可读取。本轮镜像metadata未声明license，不把可下载等同重新发布许可；正式纳入须固定原始来源/版本/使用条件。前20条全部同一发件人，**不是20个独立作者/线程族**。
2. Resume候选：[作者发布的ResumeAtlas](https://huggingface.co/datasets/ahmedheakl/resume-atlas)，当前`3f80ca910fa9964890afb7845c09e239d07b9b1d`，card标MIT。[作者仓库](https://github.com/noran-mohamed/Resume-Classification-Dataset)说明来自Google/Bing图像和LiveCareer，经历OCR及去标点、停用词等清理。前20条均Accountant，不能当作职业覆盖证据；20个文本hash不同不代表20个独立人/模板，身份族尚未确定。这种预处理本身可能造成领域混杂，不与原始格式简历悄然合并。
3. 备选[opensporks/resumes card](https://huggingface.co/datasets/opensporks/resumes/blob/main/README.md)标CC0，声明来自LiveCareer/Kaggle并保留Resume_str与HTML。只审卡片，未下载样本。与ResumeAtlas可能同源，不能混合作为独立来源增加样本数。逐来源记录授权/来源链及原始HTML/PDF到文本的处理差异。

只缓存小型viewer响应和metadata于`E:\Caches\longpibench-m1-availability\`，不公开其中的个人信息原文。报告中保留行号、文本hash、token数和group hint hash。Viewer不支持不可变revision参数：取前后repo SHA一致，响应SHA已记录，但不能声称它是按固定revision直接下载的原始文件快照。

## 共同长度：已证实的有限支持

使用已固定三套tokenizer、整文add_special_tokens=True、truncation=False；没有模型前向。个别>512警告只发生在tokenization，未将长串直接送入模型。

| 20条预览范围 | Email | Resume |
| --- | --- | --- |
| DeBERTa token数 | 8–1235 | 185–380 |
| Prompt Guard token数 | 9–1416 | 267–562 |
| DistilBERT token数 | 8–1301 | 203–405 |

以DeBERTa固定参考tokenizer定义候选共同区间，**预览最小最大范围的交集为185–380**；这只证明有限覆盖的可能，不保证交集中任意长度都有独立文档。较宽分层的实际计数如下：

| DeBERTa token层 | Email | Resume | 本轮两域均观察到 |
| --- | ---: | ---: | --- |
| 128–255 | 2 | 5 | 是 |
| 256–511 | 2 | 15 | 是 |
| 512–1023 | 1 | 0 | 否 |
| 1024–2047 | 2 | 0 | 否 |
| 2048–4095 | 0 | 0 | 否 |

现有资料不足以确认可实施原先四个长层、每层100源的计划。未来应先只做分散来源的长度清点，证明共同支持后才冻结层边界、样本数及采集方案；不足就缩小范围/缩小主张，不能复制正文、拼接不同履历、padding或挑长攻击来制造长度支持。Prompt Guard边界机制还须记录自身token数、chunk数、尾块余数，不能把DeBERTa长度直接当PG长度。

## 来源分组、去重与隔离

- 永久排除原公开Email/Resume各100源、旧960评分相关全部变体、旧方向控制、M1新片段/载体、本次40条资料预览。核对原始来源文件hash、规范化文本hash、5gram近似重复、可追溯实体/模板信息。已做预览对旧200的5gram Jaccard最大约0.00112；这不能替代后续身份族/模板查重。
- Email按线程Message-ID/In-Reply-To、引用内容近似重复、转发族、发件组织/作者群形成group；同一长引用链不得跨分割。只按正文hash划分会遗漏转发副本。需人工确认良性，普通邮件可能含自然指令，不能仅因来源是Enron就判为无注入金标。
- Resume按人/履历版本、模板族、原PDF/图像URL、OCR副本、联系信息规范化hash聚类。联系信息只本地处理，不进入公开结果。相同模板来自多个站点仍优先同组；无法排除同源的样本隔离或剔除，不能标作独立测试。
- 精确去重后做词5gram/字符近似去重，建议预先固定Jaccard>=0.8的人工复核候选规则；它是待冻结的数据质检规则，不是检测算法。跨域也查重；整个group划分一次，所有切块和将来的配对变体继承同一split。
- 人工良性/来源检查与检测分数解耦，保留原文和各处理版本hash，不按分数挑选。清理/原始格式作为记录属性；不得将删除格式后的短简历与原始长邮件当作纯领域/长度差异。

## 独立校准与冻结测试的待执行方案

1. 在新来源清点阶段，仅用设计开发资料确认共同支持、group独立性、职业/作者覆盖、自然长度及许可。长度、领域、来源模板交叉匹配；800只是旧草案规模，本轮不落实。
2. 正式纳入前冻结reference tokenizer、长度层、各域每层源数、数据处理、分组算法、seed和唯一group清单；长层不足写明，不补造。为每个模型另存token_count/chunk_count/tail_count，研究长度须控制领域及来源格式。
3. 按group进行约1:1独立calibration/test划分，并尽量保持域×长度×来源格式分层平衡；组大小导致比例变化如实记录。整个group绑定一个split，不跨域拆族。
4. calibration仅拟合预先列明的旧基线参数；冻结后测试只运行一次用于独立验证，不再用本次历史留出作确认。保留未看分数的测试封存清单，结果分析再检查实际文档级FPR是否匹配。不得按test ASR/TPR筛权重或阈值。
5. 本轮24片段仅机制探索，无攻击正样本，不估计防御收益。未来若验证鲁棒处理，必须同时保留攻击敏感度和固定FPR公平比较，不能只看降低良性风险。5%FPR的正式论断需更多独立良性group和相应不确定性说明，不能把变体或大量同一邮件作者计作独立样本。

**尚未执行：**完整采集、800源评分、攻击构造、新校准、模型训练、多尺度复核或边界鲁棒防御模块。此文仅准备，不授权自动开展下一阶段。
