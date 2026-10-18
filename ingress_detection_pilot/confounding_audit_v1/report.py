"""Render sealed-score diagnostics and an independent-data design, no inference."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np

import offline as o

ROOT=Path(__file__).resolve().parent
NAMES={'global_max':'Global Max','domain_max':'Domain Max','length_max':'Length Max','domain_length_max':'Domain+Length Max'}


def write(name,lines):
    with (ROOT/name).open('x',encoding='utf-8') as stream:stream.write('\n'.join(lines).rstrip('\n')+'\n')


def figures(results,metrics,tail_cases,render_revision=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder=ROOT/'figures';folder.mkdir(exist_ok=render_revision)
    plt.rcParams.update({'font.size':9,'figure.dpi':150,'savefig.bbox':'tight'})
    styles={'global_max':dict(color='#2374ab',linestyle='-'), 'domain_max':dict(color='#222222',linestyle='--'),
        'length_max':dict(color='#e68a00',linestyle='-.'),'domain_length_max':dict(color='#b82132',linestyle=':')}
    for alias,result in results['models'].items():
        fig,axes=plt.subplots(2,2,figsize=(11,8))
        for col,domain in enumerate(['email','resume']):
            for method in o.METHODS:
                c=result['domain_curves'][domain]['curves'][method]
                point=next(r for r in metrics if r['detector']==alias and r['split']=='test' and r['domain']==domain and r['method']==method)
                axes[0,col].plot([v['fpr'] for v in c['roc']],[v['tpr'] for v in c['roc']],label=f"{NAMES[method]} AUC={c['auroc']:.3f}",**styles[method])
                axes[0,col].plot(float(point['fpr']),float(point['tpr']),'o',color=styles[method]['color'],markersize=4)
                # Right-endpoint precision on each recall interval matches AP.
                axes[1,col].step([v['recall'] for v in c['pr']],[v['precision'] for v in c['pr']],where='pre',label=f"{NAMES[method]} AP={c['average_precision']:.3f}",**styles[method])
                precision=int(point['tp'])/(int(point['tp'])+int(point['fp'])) if int(point['tp'])+int(point['fp']) else None
                if precision is not None:axes[1,col].plot(float(point['tpr']),precision,'o',color=styles[method]['color'],markersize=4)
            axes[0,col].axvline(.1,color='gray',linestyle=':',linewidth=.8)
            axes[0,col].set(title=f'{alias} / {domain}: 40 benign + 40 attacks',xlabel='Observed document FPR',ylabel='TPR',xlim=(-.02,1.02),ylim=(-.02,1.02))
            axes[1,col].axhline(.5,color='gray',linestyle=':',linewidth=.8)
            axes[1,col].set(title='PR: historical balanced prevalence = 50%',xlabel='Recall',ylabel='Precision',xlim=(-.02,1.02),ylim=(-.02,1.02))
            axes[0,col].legend(fontsize=7,loc='lower right');axes[1,col].legend(fontsize=7,loc='lower left')
        fig.suptitle('Historical explanatory replay only | Global/Domain Max curves overlap by construction\nDots = calibration-only frozen operating points; no test-threshold tuning')
        fig.tight_layout(rect=(0,0,1,.94))
        for ext in ['png','pdf']:fig.savefig(folder/f'{alias}_roc_pr.{ext}')
        plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    labels=[];delta_auc=[];delta_ap=[];cis_auc=[];cis_ap=[]
    for alias,result in results['models'].items():
        for domain,data in result['domain_curves'].items():
            c=data['curves'];ci=data['domain_length_minus_domain_fixed_calibration_bootstrap']
            labels.append(f'{alias}\n{domain}')
            delta_auc.append(c['domain_length_max']['auroc']-c['domain_max']['auroc'])
            delta_ap.append(c['domain_length_max']['average_precision']-c['domain_max']['average_precision'])
            cis_auc.append(ci['auroc_delta_95']);cis_ap.append(ci['average_precision_delta_95'])
    for axis,values,cis,title in zip(axes,[delta_auc,delta_ap],[cis_auc,cis_ap],['AUROC difference','Average-precision difference']):
        x=np.arange(len(labels));axis.axhline(0,color='gray',linestyle='--')
        axis.vlines(x,[c[0] for c in cis],[c[1] for c in cis],color='#2374ab')
        axis.scatter(x,values,color='#b82132',zorder=3)
        axis.set_xticks(x,labels,rotation=25,ha='right',fontsize=8)
        axis.set(title=title,ylabel='Domain+Length minus Domain-only')
    fig.suptitle('2000 paired stratified source bootstraps | historical data, fixed calibration; no causal claim')
    fig.tight_layout()
    for ext in ['png','pdf']:fig.savefig(folder/f'conditional_increment.{ext}')
    plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(14,8))
    for col,alias in enumerate(o.ALIASES):
        rows=[r for r in o.load(alias) if r['split']=='test' and r['domain']=='resume' and r['label']==0]
        for n in sorted({r['chunk_count'] for r in rows}):
            selected=[r for r in rows if r['chunk_count']==n]
            axes[0,col].scatter([r['token_count'] for r in selected],[r['maximum'] for r in selected],label=f'{n} chunks',s=22)
        axes[0,col].set(title=f'{alias}: 40 benign Resume sources',xlabel='Document token count',ylabel='Max selected-class softmax')
        axes[0,col].legend(fontsize=8)
        selected=[r for r in tail_cases if r['detector']==alias]
        for row in selected:
            axes[1,col].plot([int(row['first_tokens']),int(row['tail_tokens'])],[float(row['first_score']),float(row['tail_score'])],color='gray',alpha=.45,linewidth=.8)
        axes[1,col].scatter([int(r['first_tokens']) for r in selected],[float(r['first_score']) for r in selected],label='First chunk',marker='o',s=20)
        axes[1,col].scatter([int(r['tail_tokens']) for r in selected],[float(r['tail_score']) for r in selected],label='Tail chunk',marker='^',s=28)
        axes[1,col].set(title=f'{len(selected)} paired multichunk sources; content differs',xlabel='Chunk tokens; no 512-token tail overlap',ylabel='Chunk softmax score',xlim=(0,540))
        axes[1,col].legend(fontsize=8)
        for axis in axes[:,col]:axis.ticklabel_format(axis='y',style='sci',scilimits=(-3,3),useOffset=False)
    fig.suptitle('Resume length / tail diagnostics | all y axes independent | paired lines are observational, not interventions')
    fig.tight_layout(rect=(0,0,1,.96))
    for ext in ['png','pdf']:fig.savefig(folder/f'resume_length_position.{ext}')
    plt.close(fig)


def reports(results,metrics,positions,controls):
    lines=['# Domain–Length–Position Confounding Audit', '',
        '**结论：DeBERTa 此前长度校准的大部分表观收益，可由领域条件化解释；尚无证据支持开发 LCMD。** 本轮不训练、不实现新防御。结论仅针对既有公开数据的探索性解释，不能外推为长度在所有模型上无价值。', '',
        '## 核心观察', '',
        '1. **DeBERTa 的主要新增检出没有长度独占性。**Length Max 相对 Global Max 新增的16条攻击，Domain Max全部也检出。两者在160条历史留出输入上判定一致率95%。Domain Max为TP39/FP9，Length Max为TP32/FP8，实际FPR不同，因此不能把前者较高TPR直接叫作固定FPR优势；判定重合支持的是领域代理解释，不是因果解释比例。',
        '2. **控制领域后，DeBERTa 未出现额外域内排序收益。**Domain+Length对比Domain-only，Email AUROC 0.76625→0.763125，Resume 0.858125→0.8578125；两域AP也下降。AUROC/AP差异的固定校准bootstrap区间均包含0。Domain+Length只改变2条判定，且均是Email攻击由阳性变阴性；良性判定和Resume判定不变。',
        '3. **局部关联不等于可用的额外检测价值。**固定领域和精确Chunk数后，Resume的Token–Max秩关联在DistilBERT（ρ≈0.675，p=0.00025）和Prompt Guard（ρ≈0.723，p=0.00025）仍存在。两模型的一块Resume内部也有关联，不能把一切都归咎于尾块。但内容与长度仍共同变化；这些关联没有证明因果效应，也不直接证明校准能改善检测。',
        '4. **DistilBERT有需保留的局部信号。**Domain+Length在Resume的工作点为TP38/FP2，Domain-only为TP26/FP3，且AUROC轻微增加约0.00344；Email未改善，AUROC/AP差异区间仍包含0，不能称为跨域稳定收益。Domain-only仅覆盖Length Max新增检出的18/31，不能把DeBERTa的解释一概套到DistilBERT。',
        '5. **Prompt Guard尾块关联真实，但机制未识别。**14个多块良性Resume中13个尾块分数高于首块，中位差约0.208；配对符号检验p≈0.00183。尾块长度与尾块分数ρ≈-0.165、p=0.573，没有显示更长尾块更高。所有这些尾块没有起始特殊token、带结尾特殊token，且与512-token首块没有相同长度的对照。内容、长度、位置和特殊token格式的贡献仍未解决。',
        '6. **DistilBERT原作者标签方向已补证。**原作者Space明确LABEL_0=benign、LABEL_1=prompt injection，符合历史LongPIBench映射。32条独立短控制样本中，攻击16/16判阳性、良性11/16误报；作者的Hello、写诗请求、Ignore previous instructions三个示例方向一致。历史标签和所有分数未翻转。高误报应作为行为问题解释。', '',
        '## 数据、封存与解释范围', '',
        '主数据为最新960条真实评分：三检测器各320变体、共用160个源。每模型原calibration中仅80个良性源用于新诊断策略的校准（每域40）；原test含80源/160变体，现只用于既有结果解释，不再称为独立测试。未合并旧80条烟测来扩大拟合数据。',
        '开始前对360个既有tracked文件逐一SHA256封存，包含旧评分、阈值、结果和R0–R4代码/配置。原Global/Length阈值及总体/分域混淆矩阵数值完全复现；新参数另存calibration_parameters.json。所有分析结束后再验封。5090 R2未收到新任务，其工作区、Baseline、运行配置和raw均不接触。', '',
        '## 四种离线策略与公平性', '',
        '| 策略 | 风险排序量 | 原calibration良性参考 | 阈值 |',
        '| --- | --- | --- | --- |',
        '| Global Max | 原Chunk最大风险分数 | 合并两域80源 | 原合并阈值，原样复现 |',
        '| Domain Max | 原Chunk最大风险分数 | 本域40源 | 本域经验FPR≤10%的独立阈值 |',
        '| Length Max | 原28近邻平滑尾概率的-log10 | 合并80源，按log(1+Chunk数)近邻 | 原留一校准合并阈值，原样复现 |',
        '| Domain+Length Max | 相同尾概率、相同k=28 | 仅本域40源内取28近邻 | 本域留一校准阈值 |', '',
        '所有阈值、参考样本、邻域规模都在新结果计算前固定；没有按历史留出调阈值。长度变量仍为旧方法的Chunk数代理，不是Token数。Domain+Length固定28邻居是为了不同时改变k；每域40源时近邻已覆盖70%，局部支持有限。所有策略采用原nextafter阈值与严格>，离散尾概率和并列分数可能使校准FPR低于预算。',
        'Domain Max只改变本域阈值，不改变本域排序，因此它与Global Max的域内ROC/PR必然完全重合。这是实现不变量，不是发现“领域没有作用”。跨域合并时领域阈值重新分配误报预算，不能拿不可比的域内原分数拼成一个改进排序。', '',
        '## 历史解释性工作点', '',
        '| 检测器 | 域 | 策略 | TP | FP | TN | FN | TPR | 实际FPR |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    cal_table=['## 实际校准误报预算占用','',
        '| 检测器 | Global Max | Domain Max（Email / Resume） | Length Max | Domain+Length（Email / Resume） |',
        '| --- | --- | --- | --- | --- |']
    for alias,result in results['models'].items():
        p=result['fitting']['parameters']
        cal_table.append(f"| {alias} | {p['global_max']['pooled']['fit_fp']}/80 | {p['domain_max']['email']['fit_fp']}/40 / {p['domain_max']['resume']['fit_fp']}/40 | {p['length_max']['pooled']['fit_fp']}/80 | {p['domain_length_max']['email']['fit_fp']}/40 / {p['domain_length_max']['resume']['fit_fp']}/40 |")
    cal_table+=['','长度策略为留一校准计数。相同10%上限不代表实际校准FPR完全相同；尾概率离散并列使部分预算未用满。保留原Length参数，未为本轮解释重新优化旧阈值。因此判定重合应与域内整条曲线一起判断，不能仅靠不同工作点推断独立贡献。','']
    insert=lines.index('## 历史解释性工作点')
    lines[insert:insert]=cal_table
    for row in metrics:
        if row['split']=='test':
            lines.append(f"| {row['detector']} | {row['domain']} | {NAMES[row['method']]} | {row['tp']} | {row['fp']} | {row['tn']} | {row['fn']} | {100*float(row['tpr']):.2f}% | {100*float(row['fpr']):.2f}% |")
    lines+=['', '这些是校准后锁定阈值在历史留出上的实际计数。不同FPR工作点不可直接作同FPR性能结论；没有把旧留出重新调到恰好10%。域内ROC的TPR@经验FPR≤10%只作为描述性排序包络，不据它选部署阈值。PR中攻击占比固定50%，AP不能外推到低攻击率部署场景。', '',
        '## Domain+Length 相对 Domain-only 的域内曲线增量', '',
        '| 检测器 | 域 | ΔAUROC | bootstrap 95%区间 | ΔAP | bootstrap 95%区间 |',
        '| --- | --- | ---: | --- | ---: | --- |']
    for alias,result in results['models'].items():
        for domain,data in result['domain_curves'].items():
            a=data['curves']['domain_max'];b=data['curves']['domain_length_max'];ci=data['domain_length_minus_domain_fixed_calibration_bootstrap']
            lines.append(f"| {alias} | {domain} | {b['auroc']-a['auroc']:.5f} | [{ci['auroc_delta_95'][0]:.5f}, {ci['auroc_delta_95'][1]:.5f}] | {b['average_precision']-a['average_precision']:.5f} | [{ci['average_precision_delta_95'][0]:.5f}, {ci['average_precision_delta_95'][1]:.5f}] |")
    lines+=['', '区间由2000次同域、按标签分层的配对源文档bootstrap得出；拟合阈值固定，不包含校准样本不确定性，未作多重比较校正。旧留出已经反复用于解释，因此不作确认性显著性或独立泛化声明。', '',
        '## 长度、位置与内容：能识别什么', '',
        '| 问题 | 当前证据 | 尚未识别的部分 |',
        '| --- | --- | --- |',
        '| 领域之外是否还有Token相关性 | Resume内且固定Chunk数后，DistilBERT/Prompt Guard仍有相关性；DeBERTa没有稳定关联 | 内容随长度共同变化；相关性不是因果或增量检测价值 |',
        '| Token数和Chunk数能否作为独立因素 | 官方Chunk数=ceil(Token数/512)，是确定关系 | 无法在完全固定Token数时独立改变Chunk数 |',
        '| 文档绝对位置是否直接进入模型 | 官方每块只传局部input_ids，未传文档级位置；重复相同token hash的分数完全一致 | 不同位置的内容与边界格式不同，观察到的位置关联不是独立位置输入效应 |',
        '| 尾块更短是否造成高分 | PG尾块5–443 token，尾长/尾分数关联不显著；Resume尾块与首块无512-token长度重合 | 没有同内容、同长度、同格式的跨位置对照，因果不可识别 |',
        '| 尾块高分是否由显式指令词造成 | PG尾块仅1条含预设词表词且低分，多数高分尾块未命中词表 | 词表不是恶意性或语义真值，不能排除其他内容影响 |',
        '| 特殊token是否影响尾块 | 多块尾块无起始特殊token、均带结束特殊token，首块格式相反 | 未做干预评分，格式贡献未解决，未改官方切块行为 |', '',
        '精确重建了960条文档的2900个Chunk输入，token hash全部与原始记录一致；未调用模型对历史文档重新评分。词表/数字/标点等内容指标仅作描述，不作为新检测规则。位置表按Chunk给出统计时同时给独立源数，不把Chunk当作独立文档估计显著性。详见position_content_audit.json、chunk_position_strata.csv、resume_tail_cases.csv。', '',
        '## 标签核验', '',
        '原作者资料：[固定Space app.py](https://huggingface.co/spaces/fmops/prompt-injection-classifier/blob/ef784e4cadfe184f02683a87a6ad19f565fda9b4/app.py)。其示例模型名为fmops/distilbert-prompt-injection；演示代码明确LABEL_0为benign、LABEL_1为prompt injection。模型本身config仍未给语义id2label，训练标签来源未完全恢复；现已确认公开作者的预期映射。Space只是阅读保存，没有执行。',
        '独立控制样本在本轮推理前冻结，16良性+16显式注入，均短于512 token，用相同本地固定权重CPU FP32真实前向。控制集TP16、FP11、TN5、FN0，不是性能评测集；3个作者示例分别正确识别。所有logits/softmax、文本和hash保留。此证据支持预期方向且揭示误报，不支持根据历史留出或控制集翻转历史标签。', '',
        '## 决策', '',
        '**LCMD开发保持NO-GO。**DeBERTa的原观察可以主要由领域条件化说明，加入域内Chunk数条件没有额外排序收益。其他模型中保留局部相关性和DistilBERT Resume的工作点信号，但没有跨域、独立数据上的稳健增量证据。不能写“长度没有任何信息”，也不能写“长度校准已有效”。',
        '下一步仅交付独立数据验证设计，见next_independent_validation_plan.md；本轮不实现、训练或执行其中的新数据干预实验。', '',
        '## 可复核文件', '',
        '- audit_results.json：四策略曲线、判定重合、域内关联和bootstrap区间。',
        '- calibration_parameters.json：仅原calibration良性数据拟合的新诊断参数；旧参数不改。',
        '- stratified_comparisons.csv、document_decisions.csv：校准/历史留出的分层计数与逐文档四策略分数、阈值、判定。',
        '- chunk_features.csv、feature_receipt.json：准确token重建与内容代理，未保存文档全文。',
        '- distilbert_label_audit.json、controls_manifest.jsonl、controls_observations.jsonl、source_evidence/：原资料与独立控制证据。',
        '- figures/：三模型分域ROC/PR、域条件增量、Resume尾块与长度PNG/PDF。',
        '- frozen_existing_files.json及completion_receipt.json：旧证据封存与最终验封。','']
    write('diagnostic_report.md',lines)
    write('confounding_analysis.md',[
        '# 混杂因素与可识别性', '',
        '主结论和全部数值见diagnostic_report.md。本文件区分“领域之外存在分数关联”与“长度校准提供独立检测价值”。', '',
        '| 因素 | 已控制/审计 | 主要局限 |',
        '| --- | --- | --- |',
        '| Domain | Domain Max独立阈值；Domain+Length仅取本域近邻；逐域ROC/PR | 域内内容与长度仍未平衡 |',
        '| Token length | 在域内及精确Chunk数组内做秩关联、阻塞置换 | 未打乱内容；不作因果或贡献百分比分解 |',
        '| Chunk count | 旧L与新D+L均固定k=28 | Chunk数由Token数确定，域内近邻少，尾概率有并列 |',
        '| Position | single/first/interior/tail分开；每源一个首尾差 | 全局位置不直接输入；内容与特殊token格式和角色共线 |',
        '| Content | 准确token hash；预设指令词及数字/标点描述 | 无语义真值，不能用词表缺失证明内容无影响 |',
        '| Boundary format | 检查起始/结束特殊token | 没有格式配对干预，本轮不更改分块或新评分 |',
        '| Calibration allocation | 原G/L精确复现，新D/D+L仅用原良性cal | 相同预算不保证同一实际FPR；并列与有限样本影响工作点 |',
        '| Model label | 作者Space+独立controls；不改历史映射 | 预期语义已确认，训练实现仍未完整恢复；控制集不代表总体 |', '',
        'DeBERTa的Domain Max覆盖L相对G新增16次检出的100%，但其历史FPR为11.25%而L为10%，所以100%是样本集合覆盖，不是“领域因果解释100%”或公平固定FPR优越性。D+L相对D在每域的排序和AP不增进一步削弱长度模块的依据。',
        'DistilBERT的D仅覆盖L新增31次检出的18次（58.1%），不能宣称领域解释了该模型的全部收益。D+L Resume工作点及Token关联是未解决的局部信号，应进入新数据验证设计而非直接开发。',
        'Prompt Guard的Resume单Chunk组内也有强Token关联，因此“高分完全由尾块造成”的说法不成立；但尾块首尾差依然显著。两种现象可以共存，缺少干预时不能分配贡献。', '',
        '绝对文档位置没有进入局部模型。2900块里，相同输入token的重复组得分完全一致，但没有跨position_role的相同token组，无法从自然重复构成位置机制对照。', '',
        '当前可得结论：DeBERTa长度条件化主要表现为领域代理；Token关联在其他模型Resume内仍有，判别增量及机制尚未确认。LCMD保持NO-GO，所有因果解释标UNRESOLVED。'])
    write('next_independent_validation_plan.md',[
        '# 下一轮独立数据验证方案（设计，不执行）', '',
        '目的：检验长度是否提供领域之外、可重复的判别价值。不是新防御开发方案，不授权训练、多尺度复核或部署。旧公开200源均已被开发/解释使用，下一轮必须获取新源。', '',
        '## 独立样本与分组', '',
        '建议先准备800个新良性源：Email/Resume × 4个长度带 × 每格100源。参考长度带为256–511、512–1023、1024–2047、2048–4095 token，按固定主检测器tokenizer定义，另记录各模型自己的Token数。Email和Resume在每个长度带都要有真实支持，避免长Email/短Resume直接等同领域。',
        '每格事前按源组分为50 calibration、50 locked validation，总计400良性校准源和400良性验证源；每源另构造同一固定Authority Spoof配对，得到1600个输入。攻击变体共享源分割，不以输出挑payload或位置。邮件线程、简历同一人、模板近重复均作为同一源组，不跨分割。',
        '自然文档用于主验证，不能通过重复无意义padding把短简历伪造成主数据。稀缺长度格需如实报告、补充独立自然来源；支持不足时暂停相应分层结论。采集内容需有公开使用依据，标注与模型结果隔离。', '',
        '## 机制控制：单独样本族，与主性能集分开', '',
        '1. 固定完全相同的局部token序列，放在不同全局Chunk索引，检查局部模型得分不变这一负控制；全局位置本身不应直接影响仅看input_ids的模型。',
        '2. 在独立中性载体上保持核心文本相同，分别控制局部文本长度、核心文本在Chunk内的位置、以及起始/结束特殊token布局。各干预只改变一个因素或使用事前固定的小型因子设计。与自然数据分开，不作为算法提升证据。',
        '3. 对尾块分别做同内容/同长度、不同位置与格式的匹配控制，并保持Token级记录。中性填充本身改变内容，需多个独立填充族随机分派，不能声称完全消除了内容混杂。',
        '4. 同一载体及其所有干预变体归同一家族，禁止跨calibration/validation；按源族而非Chunk重采样。不在本轮实现这些干预或评分。', '',
        '## 冻结对照与主要比较', '',
        '仍比较四个离线策略，先在新的calibration良性文档确定阈值；主要比较为同一模型、同一域内D+L对D的TPR@固定文档FPR。保留Global/Length作为解释性对照，不把默认0.5当唯一基线。主模型保持DeBERTa，其他两模型作复制，不能按本轮分数改选主模型。',
        '先用10%文档FPR进行探索性复制。若评价5% FPR，需预先进行按域和长度层的样本量/区间设计；400份良性验证并不自动保证部署5%或各小格5%。报告实际计数与二项区间，不靠提高拒绝率降低ASR。',
        '曲线用于预声明的排序指标；锁定验证集不得反过来调阈值。若比较在同样实际FPR下的TPR，需事前固定评价规则，并将描述性ROC包络与部署阈值结果分开。AP同时报告攻击先验比例，避免把50%平衡集AP外推部署。',
        '独立验证主要检查两个域中的增量是否一致，并按源组给配对区间；主要假设和跨模型/域多重性策略应在新结果前登记。Token数与Chunk数代理应分别注明，不能把对Chunk代理的否定等同否定连续Token信息。', '',
        '## Go / No-go', '',
        '- 只有在新独立源上，D+L相对D在控制领域FPR后仍有稳定、可复现增量，且机制控制能够排除单纯领域/格式代理，才重新讨论长度模块。任何探索性正信号先进入独立验证，不直接触发开发。',
        '- 若优势仅出现在混合总体、实际FPR增加、单一域或已反复查看的数据上，LCMD继续NO-GO。',
        '- 即便未来有支持，本方案也只形成重新评审依据，不授权训练、新算法模块、多尺度覆盖或疑难区域复核。', '',
        '预期交付：事前样本清单/去重与源组证明、长度域交叉支持表、冻结拟合参数、完整真实分数、分域分层ROC/PR及计数、配对不确定性和机制控制结果。'])
    write('README.md',['# 独立混杂诊断 INGRESS-5060-003','',
        '入口：[diagnostic_report.md](diagnostic_report.md)。方法辨析：[confounding_analysis.md](confounding_analysis.md)。下一轮仅设计：[next_independent_validation_plan.md](next_independent_validation_plan.md)。',
        '输入是只读的960条历史真实评分；仅原calibration良性数据用于四策略参数。独立32条标签控制单独保存，未翻转历史标签。所有结论为探索性；LCMD开发NO-GO。', '',
        '执行顺序：freeze.py事前封存→独立CPU环境controls.py / features.py→分析Python analyze.py→report.py。输出存在时拒绝覆盖；不能在现有目录直接重跑。原评分与R2不修改。',
        '重要文件：calibration_parameters.json、stratified_comparisons.csv、document_decisions.csv、audit_results.json、chunk_position_strata.csv、resume_tail_cases.csv、distilbert_label_audit.json、figures/、completion_receipt.json。'])


def main():
    n=o.verify_seal()
    results=json.loads((ROOT/'audit_results.json').read_text(encoding='utf-8'))
    positions=json.loads((ROOT/'position_content_audit.json').read_text(encoding='utf-8'))
    controls=json.loads((ROOT/'distilbert_label_audit.json').read_text(encoding='utf-8'))
    with (ROOT/'stratified_comparisons.csv').open(encoding='utf-8') as stream:metrics=list(csv.DictReader(stream))
    with (ROOT/'resume_tail_cases.csv').open(encoding='utf-8') as stream:tails=list(csv.DictReader(stream))
    figures(results,metrics,tails);reports(results,metrics,positions,controls)
    assert o.verify_seal()==n
    receipt={'status':'EXPLORATORY_NUMERICAL_DIAGNOSTIC_COMPLETE_FIGURE_REVIEW_PENDING',
        'finished_utc':datetime.now(timezone.utc).isoformat(),'formal_paper_experiment':False,
        'all_existing_files_unchanged':n,'historical_scores_reinferred':False,'new_control_inferences':32,
        'exact_chunk_token_hash_matches':2900,'legacy_global_length_thresholds_and_counts':'EXACT',
        'fitting_uses_only_original_calibration_benign':True,'new_algorithm_development':False,'R2_5090_modified':False,
        'unit_tests_passed':5,'independent_auc_rank_and_ap_positive_precision_checks':'PASS',
        'file_sha256':{p.relative_to(ROOT).as_posix():o.sha(p) for p in sorted(ROOT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}}
    with (ROOT/'completion_receipt.json').open('x',encoding='utf-8') as stream:json.dump(receipt,stream,indent=2)
    print(json.dumps({'status':receipt['status'],'all_existing_files_unchanged':n}))


if __name__=='__main__':main()
