# M1 原始记录 schema

`sources_and_conditions.jsonl`每行一个原始片段，主键source_id，字段包括style、label=0、text、source/generation/independence、text_sha256、core_token_ids、core_token_sha256、对原200源word5 Jaccard、全部variants及两个完整文档documents。documents带全文、整文ID、核心起止offset、text/input hash和载体说明。

`raw/<Run ID>/format_observations.jsonl`：

- source_id + condition + simulated_global_chunk_index确定一条前向；不同变体不算独立源。
- input_token_ids完整实际输入；n_tokens；input_sha256=SHA256(UTF-8 json.dumps(ids,separators=(',',':')))；global_position_passed_to_model=false。
- logits为三个类别原始FP32 logit；softmax顺序BENIGN、INJECTION、JAILBREAK；risk_score=max(softmax[1],softmax[2])；predicted=int(risk_score>=0.5)。不是概率校准结果。
- seconds仅前向计时，不用于筛选。position_negative_control真实重复相同token ID，序号只做元数据。

`document_observations.jsonl`：source_id、condition（standalone/aligned_tail/split_core）、整文hash、token_count、chunk_count、chunk_scores、official_prediction、official_threshold、official_evaluated_chunks、shadow_suffix_chunks、official_max_equivalence_verified。

每个chunks含[start_token,end_token)（整文含CLS/SEP的token坐标）、完整input_token_ids、canonical_input_sha256（上述compact JSON规则）、logits、softmax、score及evaluation_path。原记录器保留的input_token_sha256使用默认JSON空格序列化，与compact hash字节规则不同，二者不能直接比较；记录未改写。official_predict_prefix表示原始predict真实调用，shadow_suffix_same_forward表示原predict提前阳性退出后单独补的后缀，用来复核全量Max。

`paired_differences.csv`逐原始片段/条件保存风险和三类logit相对both_special的差、输入hash、长度和判定。`document_decisions.csv`包含前块Max、尾块分数和tail_attributable_positive（前块均<0.5且尾块>=0.5）；它不是总体误报率估计。`negative_controls.csv`保存48次重复的logit最大绝对差和risk差。

`candidate_length_screen.json`仅新来源可获取性预览的行号、hash、三tokenizer长度和group hint hash，无原文、无模型评分。source_group_hint不是最终同源族：邮件只按发件人给初始hint，简历目前只是全文hash，不能当独立性证明。
