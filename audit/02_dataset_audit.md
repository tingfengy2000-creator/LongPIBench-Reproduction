# Stage R0：Email / Resume 数据检查

## 版本与范围

来源：[RainWatcher/LongPIBench](https://huggingface.co/datasets/RainWatcher/LongPIBench/tree/cdfdfdba8838911ec3d120d5bbf584c0afb280f2)。固定 revision：`cdfdfdba8838911ec3d120d5bbf584c0afb280f2`。

已下载本阶段全部 200 条原始 JSON 到 `data/<revision>/`，没有更改原始字节。保留 HF 文件树、元信息与逐文件 SHA256。未下载 Paper、Code 的原始样本，也没有下载真实业务数据；这不影响本轮两个任务的输入构造检查，但不能宣称四套完整数据校验已通过。

| 检查项 | Email | Resume |
| --- | --- | --- |
| 文件路径 | `emails/<id>.json` | `person_info/<id>.json` |
| 实际文件数 | 100 | 100 |
| ID | 完整 0—99 | 完整 0—99 |
| 完全相同文件 SHA256 重复组 | 0 | 0 |
| 必需结构检查错误 | 0 | 0 |
| 干净／Authority spoof 输入构造 | 100 / 100 | 100 / 100 |
| 攻击输入字符数：最短／中位／最长 | 5874 / 9868.5 / 13597 | 1450 / 2487 / 4719 |

字符数是 Python Unicode 字符计数，**不是 token 数**。本轮没有目标 tokenizer，因此不报告伪造的输入 token 长度。完全重复检查也不能排除近重复、同源模板或未来开发集泄漏。

## 原始 schema

Email 的 100 条记录均含 `email_out`、`email_in`、`attachment_name`、`attachment_content`。已检查前三个实际输入字段中的邮件正文与附件内容为非空字符串（attachment_name 只核对键存在，构造器不使用它）。

Resume 的 100 条记录均含 `name`、`work_experience`、`education`、`publications`、`skills`；姓名非空字符串，后四项为列表，并成功通过官方文本构造器。此为结构与可构造性检查，未逐条确认合成履历的事实一致性或资格标签。

## 主实验攻击配置

| 项目 | Email | Resume |
| --- | --- | --- |
| suite | email | resume |
| attack | authority_spoof | authority_spoof |
| goal | 0 | 2 |
| position | last | footnote |
| 目标行为 | summary 含指定域名 | final_recommendation 判为 Qualified |
| 注入位置 | attachment_content 末尾 | 格式化履历文本末尾 |
| 载荷来源 | 官方 attacks.py 动态生成 | 官方 attacks.py 动态生成 |

源 JSON 本身不是预生成攻击样本。Email 注入时源码直接将 payload 拼到附件末尾，**没有额外加换行**；Resume 为两次换行后拼 payload。必须沿用，不能为“更容易检测”自行加分隔符。Resume 的 footnote 是公开文本构造器的命名，不意味着本次执行了 PDF 页脚注入。

已用官方 `prepare_example()` 构造并保存 400 条输入（200 干净 + 200 攻击），检查攻击输入相对于干净文本只增加指定尾部 payload。文件：`audit/prepared_inputs.jsonl`。每条含原始 data_prompt、system_prompt、条件、源文件 SHA256；攻击条件另含 payload 与插入字符区间 `[start,end)`。`record_type` 明确为 prepared_input_not_model_result，`target_inference_executed=false`。

这是**注入来源真值**，可独立于模型预测用于计算插入区域的覆盖与误删；不等于对每个字句作了“真正恶意语义”的人工标注。模型内部的归一化分段必须映射回同一坐标系后才能计量。

## 还缺哪些标签

公开文件没有针对本阶段现成的 DataSentinel 分数、定位坐标、清洗结果、下游响应、人工失败分类或完整业务正确性标签。本轮不会生成带有虚假行的实验结果 CSV。

合法任务效果需另建固定标注：Email 的事实覆盖／回复适当性；Resume 在预先明确岗位要求下的事实提取与资格判断。没有明确岗位要求和真值时，只能报告事实保留及人工质性损伤，不能凭 Qualified 比例冒充任务完成率。不要为贴合基线而把岗位要求补进当前目标 prompt；这会构成新条件。

## 复查方式

`scripts/audit_r0_local.py` 展示全部离线检查逻辑。为保护证据，脚本对已有输出采用拒绝覆盖；重复执行时应先改用新的 Run ID 输出目录。已保存的 `evidence/dataset_audit.json`、`evidence/source_manifest.json` 可直接复核，无需重复下载。
