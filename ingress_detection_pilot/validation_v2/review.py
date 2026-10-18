"""Additive final review: paired decisions and domain-allocation diagnostics.

No new inference or threshold selection. Bootstrap resamples existing paired
source decisions, not model scores; uncertainty is conditional on calibration.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
from scipy.stats import binomtest

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
import score_pilot as supplied


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def compare(alias):
    folder=ROOT/'results'/alias
    rows=supplied.read_jsonl(folder/'pilot_real_scores.jsonl')
    clean=[r for r in rows if r['split']=='calibration' and r['label']==0]
    test=[r for r in rows if r['split']=='test']
    thresholds=json.loads((folder/'pilot_results.json').read_text())['methods']
    decisions={m:{r['sample_id']:supplied.score(r,m,clean)>thresholds[m]['calibration_threshold'] for r in test}
        for m in ['max','length_calibrated_max']}
    groups={}
    for domain in ['overall','email','resume']:
        scoped=[r for r in test if domain=='overall' or r['domain']==domain]
        sources=sorted({r['source_document_id'] for r in scoped})
        paired={source:{} for source in sources}
        for r in scoped:
            paired[r['source_document_id']][r['label']]=int(decisions['length_calibrated_max'][r['sample_id']])-int(decisions['max'][r['sample_id']])
        assert all(set(v)=={0,1} for v in paired.values())
        generator=np.random.default_rng(20261018)
        boot=np.zeros((10000,2))
        for stratum in ['email','resume']:
            selected=[s for s in sources if s.startswith(stratum+'-')]
            if not selected:continue
            values=np.asarray([[paired[s][0],paired[s][1]] for s in selected],dtype=float)
            indices=generator.integers(0,len(values),size=(10000,len(values)))
            boot+=values[indices].sum(axis=1)/len(sources)
        result={}
        for label,name in [(0,'fpr'),(1,'tpr')]:
            chosen=[r for r in scoped if r['label']==label]
            gained=[r['sample_id'] for r in chosen if decisions['length_calibrated_max'][r['sample_id']] and not decisions['max'][r['sample_id']]]
            lost=[r['sample_id'] for r in chosen if decisions['max'][r['sample_id']] and not decisions['length_calibrated_max'][r['sample_id']]]
            discordant=len(gained)+len(lost)
            result[name]={'n':len(chosen),'delta_length_minus_max':(len(gained)-len(lost))/len(chosen),
                'paired_domain_stratified_source_bootstrap_95':np.quantile(boot[:,label],[.025,.975]).tolist(),
                'changed_0_to_1':len(gained),'changed_1_to_0':len(lost),
                'exact_mcnemar_two_sided_p_unadjusted':float(binomtest(min(len(gained),len(lost)),discordant,.5).pvalue) if discordant else 1.,
                'changed_0_to_1_sample_ids':gained,'changed_1_to_0_sample_ids':lost}
        groups[domain]=result
    # Post-hoc explanatory audit, not a changed baseline or a causal test.
    neighborhood={}
    for domain in ['email','resume']:
        selected=[r for r in test if r['domain']==domain and r['label']==0]
        proportions=[]
        for row in selected:
            target=math.log1p(row['n_chunks'])
            ordered=sorted(clean,key=lambda c:(abs(math.log1p(c['n_chunks'])-target),c['sample_id']))
            size=min(len(ordered),max(20,math.ceil(.35*len(ordered))))
            proportions.append(sum(c['domain']==domain for c in ordered[:size])/size)
        neighborhood[domain]={'n_benign':len(selected),'same_domain_neighbor_fraction_mean':float(np.mean(proportions)),
            'same_domain_neighbor_fraction_min':min(proportions),'same_domain_neighbor_fraction_max':max(proportions)}
    return {'comparison':'length_calibrated_max minus max at original locked thresholds',
        'paired_holdout':groups,'posthoc_neighborhood_composition':neighborhood,
        'bootstrap_repetitions':10000,'seed':20261018,
        'limitations':['Post-hoc explanatory review, not confirmatory p-values; no multiplicity correction',
            'Bootstrap resamples paired source IDs within domain and holds fitted calibration thresholds fixed',
            'Does not include calibration-sample uncertainty or guarantee population FPR',
            'Domain-neighborhood composition is descriptive, not proof of causal explanation']}


def main():
    receipt=json.loads((ROOT/'validation_receipt.json').read_text(encoding='utf-8'))
    for name,expected in receipt['file_sha256'].items():assert sha(ROOT/name)==expected,name
    paired={alias:compare(alias) for alias in ['deberta','distilbert','prompt-guard']}
    with (ROOT/'paired_comparisons.json').open('x',encoding='utf-8') as stream:json.dump(paired,stream,ensure_ascii=False,indent=2)
    # Correct the presentation in a new view; preserve the original first pass.
    source=(ROOT/'length_diagnostics.md').read_text(encoding='utf-8')
    status=[line for line in source.splitlines() if '：H1 预定义留出支持门槛' in line]
    cleaned='\n'.join(line for line in source.splitlines() if '：H1 预定义留出支持门槛' not in line)
    while '\n\n|' in cleaned[cleaned.find('## 留出良性长度诊断'):cleaned.find('门槛沿用原规则')]:
        start=cleaned.find('## 留出良性长度诊断'); end=cleaned.find('门槛沿用原规则')
        cleaned=cleaned[:start]+cleaned[start:end].replace('\n\n|','\n|')+cleaned[end:]
    cleaned=cleaned.replace('门槛沿用原规则', '\n\n'+'\n\n'.join(status)+'\n\n门槛沿用原规则',1)
    with (ROOT/'length_diagnostics_reviewed.md').open('x',encoding='utf-8') as stream:stream.write(cleaned+'\n')
    d=paired['deberta']['paired_holdout']['overall']['tpr']
    summary=['# 扩大验证最终复核', '',
        '**工程验证完成；跨域 H1 仍不充分，不推进复杂方法开发。**三套固定检测器各320条真实评分，共960条；使用与旧烟测无交集的160个源，校准/留出各80源。不是独立论文测试。', '',
        '## 主要失败模式与局部信号', '',
        f"1. **总体改善伴随域间取舍。**DeBERTa的Max与长度校准Max均为8/80良性误报（观察FPR=10%），攻击检出24/80→32/80（30%→40%）。配对变化是新增16次、丢失8次，精确McNemar双侧p={d['exact_mcnemar_two_sided_p_unadjusted']:.4f}；按域分层、以同源clean/attack成对重采样的条件bootstrap 95% TPR差异区间为[{100*d['paired_domain_stratified_source_bootstrap_95'][0]:.2f}, {100*d['paired_domain_stratified_source_bootstrap_95'][1]:.2f}]个百分点，不能支持稳定提升。Email TP21→13、FP8→3；Resume TP3→19、FP0→5，不能把总体变化概括为各域均改善。",
        '2. **局部长度现象复现，但跨域不一致。**Prompt Guard在新留出Resume良性样本上的token–Max关联ρ=0.9121、置换p=0.00025；14个多块Resume中13个尾块为最大分数，默认误报2/40。Email相关ρ=-0.0505、p=0.74925。Resume仍没有Max/Top-2或Max/Q90排序反转，三模型均未达到既定跨域支持门槛。局部门槛未通过不意味着长度效应不存在，关联也不能区分内容与尾块位置影响。',
        '3. **条件校准也在改变领域门限。**同域近邻占比见paired_comparisons.json；token/chunk长度与领域高度重合。DeBERTa的近邻同域占比均值为Email 99.1%、Resume 97.3%。这是事后解释性审计，不是长度因果效应证明；本轮未设域条件Max对照，不能分离领域校准与长度校准的贡献，也没有新设阈值或改变基线。',
        '4. **DistilBERT标签语义未解决。**官方LABEL_1映射使本轮80/80留出良性被默认判为攻击，分数接近1；其长度校准TPR上升不能被包装为一个已核实语义的检测器提升。固定模型卡只有元数据，仍无显式类别解释。',
        '5. **Prompt Guard的长度校准未改善该留出工作点。**Max为TPR13.75%、FPR13.75%；长度校准为TPR12.5%、FPR16.25%。Top-2与Q90的实际FPR也超过10%，不按这份留出重新调阈值来制造优势。', '',
        '## 置信限制', '',
        '上面的配对检验与bootstrap是事后解释性复核，未作多重比较校正；区间只反映留出源重采样，不包含校准阈值拟合的不确定性。全部模型使用同一预定10%校准预算，但实际留出FPR不同，不能把不等拒绝率的TPR直接解释为固定FPR优势。80个良性留出仍不足以保证部署FPR。',
        '旧烟测40源加本轮160源已覆盖原公开200源；后续确认性评估需新独立源，不能把已用于开发或验证的这批数据再次称为未见测试集。R0–R4总体与这些源重叠，其原实验和输出未修改。', '',
        '## 证据与交付', '',
        '- [完整混淆矩阵、长度桶分布、判定规则与配置](length_diagnostics_reviewed.md)。此视图修正了首稿Markdown表的段落分隔，未更改任何数值；首稿length_diagnostics.md保留。',
        '- [配对差异、样本ID、bootstrap、近邻领域组成](paired_comparisons.json)。',
        '- [三模型统计汇总](pilot_results.json)，原scorer输出与完整逐块分数位于results/<detector>/。',
        '- [长度与ROC](figures/length_and_roc.png)、[排序变化](figures/rank_changes.png)，PNG已由协调端逐图可视检查，无裁切或标签遮挡；PDF使用相同图形导出。',
        '- [环境](environment_audit.md)、[schema](score_schema.md)、[初始数值核验回执](validation_receipt.json)、[最终复核回执](review_receipt.json)。', '',
        '工程路径可用；本轮不训练，不实现多尺度或疑难区域复核，不声称LCMD或其他创新方法已有效。R0–R4仍按既有冻结任务独立推进。','']
    with (ROOT/'review_summary.md').open('x',encoding='utf-8') as stream:stream.write('\n'.join(summary))
    for name,expected in receipt['file_sha256'].items():assert sha(ROOT/name)==expected,name
    final={'status':'SHARE_WITH_CAVEATS_REAL_SCORES_AND_RENDERED_FIGURES_REVIEWED',
        'reviewed_utc':datetime.now(timezone.utc).isoformat(),'formal_paper_experiment':False,
        'old_initial_expansion_artifacts_preserved':True,'n_original_label_matches':960,
        'PNG_figures_visually_reviewed':['figures/length_and_roc.png','figures/rank_changes.png'],
        'pdf_visual_review':'Same figure export; PDF pages not separately rasterized',
        'paired_review_scope':'Post-hoc fixed-threshold paired bootstrap/exact McNemar, no inference or retuning',
        'file_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(ROOT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}}
    with (ROOT/'review_receipt.json').open('x',encoding='utf-8') as stream:json.dump(final,stream,indent=2)
    print(json.dumps({'status':final['status'],'deberta_tpr_delta':d['delta_length_minus_max'],'paired_ci':d['paired_domain_stratified_source_bootstrap_95']}))


if __name__=='__main__':main()
