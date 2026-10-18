# M2 证据字段与坐标

基础源为sources.json的40个source_id；02_data_manifest.jsonl每个源有label0/1两行，共80行。domain=email/resume，text_type=ordinary/hard_benign指来源良性版本的类型，不代表attack版本仍是良性。攻击全文标签1；有明确引用/研究/测试语境的固定攻击字串为label0。标签是创作意图标签，未经过独立标注者验证。

全输入保存在plan.json指定的本机runs/<construction-ID>/frozen_inputs.jsonl。含完整业务背景+上下文+核心、core_token_ids、target/attack span、三份全文文本及ID、固定恢复/控制输入。源和所有变体仅为探索材料，不充当未来独立论文测试。

风险映射：三类logits顺序BENIGN、INJECTION、JAILBREAK，torch.softmax后max(1,2)，不是sum，不是校准概率；risk>=0.5阳性。官方路径保持input_ids单参数、FP32 CPU、全局局部位置重置。input_sha256=SHA256(UTF-8 json.dumps(ids,separators=(',',':')))；文字另有UTF-8 SHA256。

原始observations.jsonl每行一个源类别对，嵌套official/core_reference,A_complete,B_cross,C_tail；shadow/offset256；recovery的native与matched512×truncated,partial16,full；controls局部16/192、替换CLS/SEP以及global1/7。每个真实forward保存完整input_token_ids、input hash、logits、softmax、风险、标签及特殊token的局部位置。

官方/Shadow的Chunk区间为整文token坐标[start_token,end_token)，含整文CLS和SEP；核心/target/attack范围为同一坐标。Shadow固定B全文，offset0引用原官方B记录，未额外调用模型；offset256完整分区[0,256),[256,768),[768,1024)，不重叠不漏token。

原predict提前阳性退出时，仅用额外影子forward补齐未访问尾块，evaluation_path清楚区分official_predict_prefix/shadow_suffix_same_forward；补齐的Max与原标签逐条一致。它不同于实验二的反事实Shadow切块。

恢复/位置/替换CSV坐标明确标为local_window_offsets：核心范围是当前保留的核心部分，攻击span可能因截断不再完整，标签仍继承原全文意图，不声称局部残片独立构成恶意意图。matched512条件中共享截断后缀的ID和局部位置均相同，两端CLS/SEP和总长也相同，仅前文内容恢复/替换；native同时改变长度。

classification_flip按每个预定义比较单独记录；同一源/类别可在多个比较重复，不将翻转行数计作独立样本数。F1语义截断、F2特殊token/边界、F3内容/局部位置、F4 Max暴露非核心误报、F5完整核心本就错误、F6未确定；标签为可共存的候选归因，不强行唯一解释。

统计主单位40基础源（每类n40、每域每类n20、每域每类型每类n10）。Bootstrap使用相同源索引共同抽取良性与攻击，10000次；分类配对McNemar，12个主要比较Holm修正。普通构造正确率、Shadow/恢复窗口的继承标签指标都不等于实际业务误报率或防御ASR。未运行受害LLM，不报告攻击成功率。
