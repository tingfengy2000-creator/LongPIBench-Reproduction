"""Write evidence-bound M2 reports after complete frozen analysis."""
import json
from pathlib import Path
from datetime import datetime,timezone
from prepare import sha,write

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]


def output(name,text):
    with (ROOT/name).open('x',encoding='utf-8',newline='\n') as f:f.write(text.strip()+'\n')


def pct(v):return 'NA' if v is None else f'{100*v:.1f}%'


def main():
    plan=json.loads((ROOT/'plan.json').read_text())
    rec=json.loads((ROOT/'full_receipt.json').read_text())
    start=json.loads(Path(rec['completion_path']).with_name('start.json').read_text())
    data=[json.loads(x) for x in Path(rec['observations_path']).read_text().splitlines()]
    summary=json.loads((ROOT/'analysis_summary.json').read_text())
    adjudication=json.loads((ROOT/'mechanism_adjudication.json').read_text())
    metrics=json.loads((ROOT/'metrics.json').read_text())
    comps=json.loads((ROOT/'paired_comparisons.json').read_text())
    tri=[r for r in summary['go_no_go']['triangulated_cases']]
    def metric(scope,cond,domain='overall',kind='all'):
        return next(x for x in metrics if x['scope']==scope and x['condition']==cond and x['domain']==domain and x['text_type']==kind)
    def comparison(scope,a,b,label):
        return next(x for x in comps if x['scope']==scope and x['before']==a and x['after']==b and x['label']==label and x['domain']=='overall')
    def table(scope,conditions,domains=['overall']):
        lines=['| 条件 | 域 | TP | FP | TN | FN | TPR | FPR | FNR | 良性通过率 |','| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
        for cond in conditions:
            for domain in domains:
                m=metric(scope,cond,domain)
                lines.append(f"| {cond} | {domain} | {m['tp']} | {m['fp']} | {m['tn']} | {m['fn']} | {pct(m['tpr'])} | {pct(m['fpr'])} | {pct(m['fnr'])} | {pct(m['benign_pass_rate'])} |")
        return '\n'.join(lines)
    boundary={label:comparison('official','A_complete','B_cross',label) for label in [0,1]}
    shadow={label:comparison('shadow','offset0','offset256',label) for label in [0,1]}
    recovery={mode:{label:comparison('recovery',mode+'_truncated',mode+'_full',label) for label in [0,1]} for mode in ['native','matched512']}
    core=metric('official','core_reference')
    matched_joint=[r for r in tri if r['matched_recovery_corrects_truncated']]
    go=summary['go_no_go']['quantitative_screen'] and len(matched_joint)>=2 and adjudication['n_strict_sources']>=3 and len(adjudication['strict_families'])>=2
    decision='有限GO：仅进入独立方案设计与验证规划' if go else 'NO-GO：当前不进入跨Chunk上下文一致性检测算法设计'
    # State qualitative review as a separate additive decision; keep computed screen intact.
    review={'decision':decision,'quantitative_screen':summary['go_no_go']['quantitative_screen'],
        'triangulated_with_matched512_recovery_cases':matched_joint,'n_matched_recovery_triangulated':len(matched_joint),
        'strict_core_window_adjudication_sources':adjudication['n_strict_sources'],
        'shared_templates_and_artificial_data_limit':True,'no_implementation_authorization':True}
    write(ROOT/'decision_review.json',review)
    envelope='本阶段为人工构造小样本机制探索；40基础源、80良性/攻击变体，每个条件共享这些源。不是自然业务分布、不是正式论文测试或算法收益证明。'
    env=f'''# 00 环境与封存

{envelope}

输入冻结提交：ccdd523；分析及烟测提交：88356a9；真实完整运行输入提交：{start['input_commit']}。
构造Run ID：{plan['run_id']}；4源烟测Run ID：{json.loads((ROOT/'smoke_receipt.json').read_text())['run_id']}；完整Run ID：{rec['run_id']}。
所有Run ID使用UTC；用户当地日期按Asia/Tokyo为2026-10-19。

固定模型：{plan['model_repo']}@{plan['model_revision']}。权重/Tokenizer文件逐项沿既有download receipt SHA256验证；model.safetensors SHA256=1771712866662626517f2d85057de2d7078389a4c1f0bc93e461bdc4fdae4bd5。模型和Tokenizer均已在E盘，不下载新文件。

原始LongPIBench commit=c7b80114ae56f65fb8019ec82afdb3df91e4ed65，detectors.py SHA256={plan['official_detector_sha256']}。风险=max(softmax[INJECTION],softmax[JAILBREAK])，非二者之和、非校准概率。文档阈值原样>=0.5，512非重叠切分、整文一次CLS/SEP、不逐块加特殊token，仅input_ids前向。

机器{start['hostname']}，Python {start['python']}。运行库：{json.dumps(start['runtime'],ensure_ascii=False)}。FP32 CPU、4线程、eval、inference_mode；torch CUDA={start['torch_cuda']}，CUDA可用={start['cuda_available']}。本机GPU盘点：{start['gpu_inventory']}。保留M1相同CPU/FP32路径，不声称使用5090。

4源8变体烟测176次前向；完整40源80变体{rec['forward_calls']}次前向，循环耗时{rec['elapsed_seconds']:.2f}秒。烟测只作工程门，不拼接正式面板、不按分数调条件。构造阶段一次失败保留于construction_attempts.md所列ignored目录；没有模型失败被删除。

437个既有tracked文件逐字节验封，包括M1、原960分数/参数/历史输出、R0–R4源码与配置。未访问5090、未向其发任务、未改变main或machine-5090。无训练、LCMD、多尺度或新防御模块。

完整冻结输入：{(REPO/plan['frozen_inputs_path']).as_posix()}（SHA256 {plan['frozen_inputs_sha256']}）。原始评分：{rec['observations_path']}（SHA256 {rec['observations_sha256']}）。输入全文/token/logits较大，按协议留本机E盘ignored runs；Git保存manifest、生成代码及小型结果，不能把小型回执当成完整原始数据备份。

独立数值/ID/统计核验见verification_full.json。区间按基础源成组重采样，良性与攻击同抽；同源条件不算独立样本。Bootstrap在全0/全1情形会退化，不能据此宣称母体误差为0。共同作者、载体重复及固定攻击模板也削弱传统独立抽样解释。
'''
    output('00_environment_and_freeze.md',env)
    lead=f"官方跨块相对完整呈现新增13条FP、17条FN，证明本构造面板存在实际判定不稳定。固定全文Shadow虽纠正27条FP，却新增19条攻击漏报；等长恢复纠正27条攻击漏报，同时新增7条FP。完整核心仍误报19/20个Hard-Benign。主要证据指向输入表示/上下文内容敏感与完整引用语义识别失败，尚不足支持普适上下文恢复算法。严格官方–核心Shadow–等长恢复交集只有{adjudication['n_strict_sources']}个同一Authority Spoof族的源。"
    lines=['# 07 机制分析', '',decision,'',lead,'',envelope,'','## 官方路径：完整文档判定','',table('official',['core_reference','A_complete','B_cross','C_tail']),
        '', '每条件n=40良性+40攻击；core_reference是官方单块短全文诊断参照，A/B/C均恰1024 token。A/B/C核心ID完全一致，但载体分配与record对齐词不同，不能作单变量因果解释。','',
        '## 分域官方判定','',table('official',['A_complete','B_cross','C_tail'],['email','resume']),
        '', '普通/Hard-Benign分层、所有区间详见stratified_metrics.csv和metrics.json；每域每类型只有10个基础源。','',
        '## 固定全文Token的Shadow','',table('shadow',['offset0','offset256']),
        '',f"固定B全文不增删，改变分区后：良性纠错{shadow[0]['errors_corrected']}、新增错{shadow[0]['new_errors']}；攻击纠错{shadow[1]['errors_corrected']}、新增漏报{shadow[1]['new_errors']}。这是局部窗口表示这一组合因素的受控影响。原文长度/内容总序列不变，但每窗上下文、局部位置、边块长度和特殊token布局随之改变，不能仅据此指定F1或F2为唯一原因。Shadow表不是部署Baseline性能。",
        '', '## 上下文恢复：报告两类全部结果','',table('recovery',['native_truncated','native_partial16','native_full','matched512_truncated','matched512_partial16','matched512_full']),
        '', '这里标签继承自原始全文意图，局部窗口可能已丢掉定义该意图的文字，因此是机制诊断指标，不是局部片段自然分布性能。所有80变体均执行，不按错误筛样本。恢复的truncated基线是从B切点提取的核心后缀，不是原B整个512-token块：它去掉载体并重新包CLS/SEP；matched512则加前侧载体。因此恢复纠错不能直接等同修复原B官方块，这也是H1/H3解释的限制。',
        '',f"native恢复：良性纠错{recovery['native'][0]['errors_corrected']}、新FP{recovery['native'][0]['new_errors']}；攻击纠错{recovery['native'][1]['errors_corrected']}、新FN{recovery['native'][1]['new_errors']}。等长512恢复：良性纠错{recovery['matched512'][0]['errors_corrected']}、新FP{recovery['matched512'][0]['new_errors']}；攻击纠错{recovery['matched512'][1]['errors_corrected']}、新FN{recovery['matched512'][1]['new_errors']}。",
        '', '等长512版本不仅长度和CLS/SEP相同，共享截断后缀的token及其局部位置也相同；恢复用必要语义前缀替代普通载体。这个控制比native更能排除长度/后缀局部位置解释，但恢复的上下文内容与载体被替换仍共同变化，且不是部署策略。',
        '', '## 特殊Token及位置控制','',table('controls',['local16','local192','replace_cls','replace_sep','global1','global7']),
        '', '80变体×2次全局位置重复中，相同ID的logits完全一致。local16/192均512 token、同核心和填充token多重集合，但邻接内容改变；不是孤立局部位置效应。replace_cls/sep只替换一处token，长度和核心局部位置严格不变，但输入为非标准人工反事实，不能直接证明官方漏洞。',
        '', '## 配对统计（12个主要类别对比）','', '| 范围 | 前→后 | 类 | 纠错 | 新错 | 风险中位差与95%CI | 错误率差与95%CI | Holm p |', '| --- | --- | --- | ---: | ---: | --- | --- | ---: |']
    for c in summary['primary_comparisons']:
        lines.append(f"| {c['scope']} | {c['before']}→{c['after']} | {c['label']} | {c['errors_corrected']} | {c['new_errors']} | {c['risk_median_delta']:.5f} {c['risk_median_bootstrap95']} | {c['error_rate_delta']:.3f} {c['error_delta_bootstrap95']} | {c['holm_p_12_primary']:.5g} |")
    lines += ['', '以上n=40基础源/类别，10000次源配对bootstrap。正的错误率差代表变差；p值为分类配对McNemar并对12次主要比较Holm修正。分域统计是描述性，未按p值选条件。小样本、共享模板和多重比较限制因果/部署主张。',
        '', '## 失败归因与三角核对','',f"A正确/B错误共有{summary['go_no_go']['official_boundary_error_variants']}个源类别对。官方A→B错误、固定全文Shadow纠正且native完整核心正确的三角证据有{summary['go_no_go']['triangulated_source_count']}个基础源；其中等长512恢复也纠正对应截断输入的有{len(matched_joint)}个源类别对。它们是证据交集，不代表独立新增样本。",
        '', f"完整核心单块本身已有FP={core['fp']}、FN={core['fn']}。这部分直接提示F5（检测器对这些完整语义样本本就出错），不能说由长文本分块新造成。F1–F6采用可能多因/Uncertain，不把所有翻转都归咎于缺CLS。",
        '', f"非核心Chunk独占造成文档FP的计数：{summary['noncore_sole_fp_count_by_condition']}。F4只在非核心块达到阈值、核心块均未到阈值时标为Max暴露背景误报；Max不会凭空把全部低于阈值的块变成阳性。核心所在块内部的载体贡献仍无法由这个分解识别。",
        '',f"06_case_level_failure_taxonomy.csv记录全部预定义比较的{summary['n_flip_records_all_declared_contrasts']}条翻转记录，覆盖{summary['n_unique_source_label_pairs_with_any_flip']}个唯一源类别对。一个源可在多个比较出现，不能把记录数当独立错误样本数。每条含前后hash、核心/攻击范围、特殊token布局、风险/判定、候选机制、替代解释与证据状态。没有翻转的全体记录也保留在03–05/control_results和原始数据中。",
        '', '## 图与案例','', '![官方配对与两类错误](figures/paired_risk_and_errors.png)','', '![完整恢复的全样本分类转移](figures/recovery_transitions.png)','', '![首个符合预定规则的边界错误](figures/boundary_cases.png)',
        '', '典型案例固定取每类中source_id字典序第一个A正确/B错误，不按最大效果挑选；若某类没有符合案例则不伪造。左图蓝色表示完整核心、红色表示其中目标语句（良性时是普通描述、攻击时是攻击指令），虚线为512边界。右图前四灰柱为官方/核心参照，后三橙柱为诊断，不可当成官方成绩。完整核心与ID、切点和风险见representative_cases.json。']
    lines += ['', '## Max与核心窗的追加归因核对', '',
        f"Shadow将2块变3窗，额外增加Max触发机会；仅边缘窗阳性而核心窗阴性的有{adjudication['n_shadow_edge_only_positives']}条。A的攻击TP只由非核心块提供的有{adjudication['n_A_attack_TP_only_from_noncore']}条。不能把这些背景阳性叫作核心检出恢复。进一步要求A核心块正确、Shadow完整核心中间窗正确及等长恢复纠错后，严格交集为{adjudication['n_strict_sources']}基础源，语义族{adjudication['strict_families']}。这是追加的机制解释核对，保留预声明结果、不改变任何评分或阈值，详见mechanism_adjudication.json。"]
    output('07_mechanism_analysis.md','\n'.join(lines))
    q1=f"本面板中，A完整→B跨块新增良性FP {boundary[0]['new_errors']}条、新增恶意FN {boundary[1]['new_errors']}条；同时纠正FP {boundary[0]['errors_corrected']}条、FN {boundary[1]['errors_corrected']}条。存在分类变化时也不能将全部变化单独归因语义丢失，因为官方载体分配不同。固定全文Shadow提供组合边界影响的独立核对。"
    q2=f"完整核心已经FP {core['fp']}/40、FN {core['fn']}/40，属于F5候选。官方边界与Shadow/等长恢复的交集见三角核对；F1语义、F2布局、F3局部内容/位置可共存。F4按非核心独占阈值单列，不把它与检测器误判混同。"
    q3=f"边界/局部输入表示敏感性H2的干预证据最直接：固定512长度和核心局部位置、仅替换CLS时13条良性判定翻转，攻击判定不变；但这是非标准反事实，不能直接宣布官方CLS布局是唯一原因。另一个强重复现象是F5：完整语义下19/20个Hard-Benign被误报，不是分块才产生。相同ID的全局位置160次重复完全不变。单纯语义丢失H1的独立贡献尚未分清，严格官方/Shadow/等长恢复交集仅{adjudication['n_strict_sources']}源且同一攻击族。"
    q4=f"恢复不是预设成功。native两类的纠错/新错为benign {recovery['native'][0]['errors_corrected']}/{recovery['native'][0]['new_errors']}、attack {recovery['native'][1]['errors_corrected']}/{recovery['native'][1]['new_errors']}；等长512为benign {recovery['matched512'][0]['errors_corrected']}/{recovery['matched512'][0]['new_errors']}、attack {recovery['matched512'][1]['errors_corrected']}/{recovery['matched512'][1]['new_errors']}。即使没有明显新FN，40个固定模板攻击也不能证明非劣或普遍安全。"
    q6='若进入方案设计，最小候选仅应针对已证实的边界错误决定何时查看相邻上下文，不先堆叠多尺度/长度校准。强Baseline须包含固定512非重叠Max、独立校准充分调阈值的Global/Domain Max、普通固定重叠窗口及每块特殊token规范化消融、可容纳完整核心的诊断oracle。未来统一新源分组/误报预算、同时比较TPR与实际FPR；本轮未实现这些方法。主要风险为共享模板/构造填充、引用语义标签争议、上下文稀释恶意指令、新FN、Max背景放大、开销增加和从探索集调参。'
    q7='若No-Go，停止把一般长文档错误默认解释为语义上下文丢失，暂停LCMD和跨Chunk一致性模块。下一优先问题是检测器对“引用的恶意措辞”与“正在对Agent发出的恶意要求”的意图区分：用新的短、完整、不同引用/主动指令模板，检验F5，而非先增加分块复杂度。若本轮尚有局部边界信号，也只保留为待独立验证的具体案例。'
    go_text=f'''# 08 Go / No-Go及Q1–Q7

**{decision}。**完成M2后停止，未授权/未执行M3、新算法实现或训练。

{envelope}

**Q1：切分是否造成FP/FN？** {q1}

**Q2：更可能的原因？** {q2}

**Q3：最强可重复证据？** {q3}

**Q4：恢复能否无明显攻击损失地纠错？** {q4}

**Q5：值得进入算法设计吗？** {decision}。预定数值筛查={summary['go_no_go']['quantitative_screen']}；等长恢复的三角交集={len(matched_joint)}。数值门只作筛查，必须连同共同作者、共享payload/引用框架、官方载体变动、Shadow残余混杂和小样本限制判断，不能把通过工程或统计门称为方法有效。

go_no_go.json保留的是预声明数值筛查及“待机制审查”的中间建议，**最终决策以decision_review.json和本报告为准**。本轮数值筛查通过，但13个良性native恢复交集没有获得等长恢复纠错支持；严格交集只有2个同一攻击族源，未达到3源/至少2语义族的可重复机制要求。当前不开发算法。这个追加归因复核不改变输入、分数、阈值或原预声明结果。

**Q6：若值得，最小模块/强Baseline/风险？** {q6}

**Q7：若不值得，停止什么、转向什么？** {q7}

## 用户五项Go条件的证据对照

1. 官方有效路径实际新错误：A正确/B错误{summary['go_no_go']['official_boundary_error_variants']}个源类别对；不是仅风险变化。
2. 固定全文与恢复交集：{summary['go_no_go']['triangulated_source_count']}基础源，语义族{summary['go_no_go']['triangulated_semantic_families']}；不能用多个变体放大。
3. 机制关联：固定全文Shadow可识别切窗组合，等长/共享后缀固定局部位置恢复交集{len(matched_joint)}；单一特殊token因果占比未识别。
4. 恢复纠错及两类代价：见Q4及所有80输入转移矩阵；新错误不隐藏。
5. 阈值始终0.5、无领域调参；A/B/C及固定全文Shadow检查位置依赖，但固定攻击模板与受控位置不支持跨攻击族外推。

所有判断仅对应完整40源真实记录；4源烟测未并入统计。结果不构成正式论文确认性证据。
'''
    output('08_go_no_go_report.md',go_text)
    output('09_next_stage_research_proposal.md',f'''# 09 下一阶段建议（未执行）

当前决策：{decision}。以下仅提案，M2完成后停止并等待用户授权。

若需独立验证机制：另取新作者/新自然来源，按基础源/线程/人/模板去重并分组；将本次40源、4烟测、M1及公开200源全部排除确认测试。先锁定自然长度与上下文角色，再固定未见过的多种安全目标Authority Spoof模板、合法引用/研究/测试语境及普通业务背景。人工复核意图标签，不能凭攻击关键词标恶意。

先复现本次具体的官方A/B/C错误与固定全文切窗现象，记录两类、多个切点和新文体。补充必要上下文与等长无关上下文对照，保持共享目标Token、位置、特殊token布局；不用分数反复挑载体/切点。对固定payload的检出率不能外推到新攻击族。

{q6}

{q7}

未来真正对比时，独立calibration拟合阈值；冻结测试只评一次，按源配对报告TPR@共同文档FPR预算及实际FPR、良性通过率、成本。须增加足够独立良性样本，不能由40个合成源证明5%FPR。攻击TPR下降及新漏报是停止条件。当前不采集800源、不训练、不构造或实现防御模块。
''')
    output('README.md',f'''# Stage M2

入口：[07_mechanism_analysis.md](07_mechanism_analysis.md)、[08_go_no_go_report.md](08_go_no_go_report.md)。

{decision}。{envelope}

环境/封存00、评分前计划01、80变体manifest02、官方/Shadow/恢复结果03–05、逐翻转归因06、下一阶段建议09。完整原始输入位于`{(REPO/plan['frozen_inputs_path']).as_posix()}`；真实评分`{rec['observations_path']}`，日志、start/completion同目录。原始大文件本地ignored，不随小型Git回执传输。

执行顺序：prepare.py -> 冻结ccdd523 -> run.py --phase smoke -> 烟测/分析预声明88356a9 -> run.py --phase full -> analyze.py -> verify.py --phase full -> adjudicate.py -> figures.py -> report.py -> finalize.py。
已有输出均排他创建，禁止覆盖重跑。所有缓存/模型/新原始数据在E盘，5090 R2不访问。M2已结束，不自动开始M3。
''')
    print(json.dumps({'decision':decision,'reports':['00','07','08','09'],'matched_triangulated':len(matched_joint)},ensure_ascii=False))


if __name__=='__main__':main()
