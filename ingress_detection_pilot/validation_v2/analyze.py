"""Audit real frozen scores, run the unmodified user evaluator, report H1 only."""
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT=Path(__file__).resolve().parent
PILOT=ROOT.parent
sys.path.insert(0,str(PILOT))
import analyze_scores as independent

ALIASES=['deberta','distilbert','prompt-guard']


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def verify_old():
    sources=[PILOT/'validation_receipt.json',PILOT/'results/prompt-guard/supplement_validation.json']
    count=0
    for source in sources:
        for name,expected in json.loads(source.read_text(encoding='utf-8'))['file_sha256'].items():
            assert sha(PILOT/name)==expected, f'Existing evidence modified: {name}'
            count+=1
    return count


def validate(alias, rows, manifest):
    completion=json.loads((ROOT/'results'/alias/'completion.json').read_text(encoding='utf-8'))
    assert completion['status']=='REAL_SCORES_COLLECTED'
    assert completion['scores_sha256']==sha(ROOT/'results'/alias/'pilot_real_scores.jsonl')
    assert completion['sample_manifest_sha256']==sha(ROOT/'sample_manifest.jsonl')
    assert completion['plan_sha256']==sha(ROOT/'plan.json')
    assert completion['runtime_model']['device']=='cpu' and completion['runtime_model']['dtype']=='torch.float32'
    committed_runner=subprocess.check_output(['git','-C',str(PILOT.parent),'show',completion['input_commit']+':ingress_detection_pilot/validation_v2/run.py'])
    assert hashlib.sha256(committed_runner).hexdigest()==completion['runner_sha256']
    assert sha(PILOT.parent/'upstream/LongPIBench/longpibench/detectors.py')==completion['original_detectors_sha256']
    assert sha(PILOT/'collect_scores.py')==completion['capture_sha256']
    frozen={r['sample_id']:r for r in manifest}
    assert len(rows)==len({r['sample_id'] for r in rows})==320
    assert set(frozen)=={r['sample_id'] for r in rows}
    labels=completion['runtime_model']['id2label']
    selected=[int(i) for i,label in labels.items() if label.upper() not in {'BENIGN','SAFE','LABEL_0'}]
    if not selected:selected=[len(labels)-1]
    groups=defaultdict(list)
    for row in rows:
        assert all(row[k]==v for k,v in frozen[row['sample_id']].items())
        assert row['detector']==alias and row['model_revision']==completion['model_revision']
        assert type(row['label']) is int and row['label'] in (0,1)
        assert type(row['token_count']) is int and row['token_count']>0
        assert row['chunk_count']==len(row['chunks'])==len(row['chunk_scores'])==math.ceil(row['token_count']/512)
        assert 0<row['official_evaluated_chunks']<=row['chunk_count']
        assert row['official_evaluated_chunks']+row['shadow_suffix_chunks']==row['chunk_count']
        for i,chunk in enumerate(row['chunks']):
            assert (chunk['start_token'],chunk['end_token'])==(512*i,min(512*(i+1),row['token_count']))
            assert chunk['score']==row['chunk_scores'][i] and math.isfinite(chunk['score']) and 0<=chunk['score']<=1
            logits=np.asarray(chunk['logits'],dtype=float)
            observed=np.asarray(chunk['softmax'],dtype=float)
            assert logits.shape==observed.shape==(len(labels),) and np.isfinite(logits).all() and np.isfinite(observed).all()
            calculated=np.exp(logits-logits.max());calculated/=calculated.sum()
            assert np.allclose(calculated,observed,atol=2e-7,rtol=2e-6)
            assert math.isclose(chunk['score'],max(observed[j] for j in selected),abs_tol=1e-12,rel_tol=0)
            assert chunk['evaluation_path']==('official_predict_prefix' if i<row['official_evaluated_chunks'] else 'shadow_suffix_same_forward')
        assert int(max(row['chunk_scores'])>=.5)==row['official_prediction']
        groups[row['source_document_id']].append(row)
    assert len(groups)==160
    assert all(len(v)==2 and {r['label'] for r in v}=={0,1} and len({r['split'] for r in v})==1 for v in groups.values())
    assert Counter((r['domain'],r['label'],r['split']) for r in rows)==Counter({(d,l,s):40 for d in ['email','resume'] for l in [0,1] for s in ['calibration','test']})
    return completion


def diagnostics(rows, prefix):
    output={}
    for domain in ['email','resume','pooled']:
        clean=[r for r in rows if r['label']==0 and (domain=='pooled' or r['domain']==domain)]
        multi=[r for r in clean if r['chunk_count']>1]
        tail_max=[r for r in multi if r['chunk_scores'][-1]==max(r['chunk_scores'])]
        output[domain]={'benign_n':len(clean),'benign_score_vs_tokens':independent.correlation([r['token_count'] for r in clean],[max(r['chunk_scores']) for r in clean]),
            'benign_score_vs_chunks':independent.correlation([r['chunk_count'] for r in clean],[max(r['chunk_scores']) for r in clean]),
            'default_fp':sum(r['official_prediction'] for r in clean),
            'max_top2_rank_inversions':independent.inversions(clean,'max','top2'),
            'max_q90_rank_inversions':independent.inversions(clean,'max','q90'),
            'multiple_chunks_n':len(multi),'last_chunk_is_max_n':len(tail_max),
            'last_chunk_is_max_sample_ids':[r['sample_id'] for r in tail_max],
            'default_fp_sample_ids':[r['sample_id'] for r in clean if r['official_prediction']]}
    return output


def distributions(rows):
    output=[]
    for split in ['calibration','test']:
        for domain in ['email','resume']:
            for label in [0,1]:
                selected=[r for r in rows if r['domain']==domain and r['label']==label and r['split']==split]
                for field,edges in [('chunk_count',[1,4,8]),('token_count',[512,2048,4096])]:
                    lower=0
                    for upper in [*edges,None]:
                        group=[r for r in selected if r[field]>lower and (upper is None or r[field]<=upper)]
                        if group:
                            values=[max(r['chunk_scores']) for r in group]
                            quantiles=np.quantile(values,[0,.25,.5,.75,1]).tolist()
                            output.append(dict(split=split,domain=domain,label=label,field=field,range=f'({lower},{upper or "inf"}]',n=len(group),
                                score_min=quantiles[0],score_q25=quantiles[1],score_median=quantiles[2],score_q75=quantiles[3],score_max=quantiles[4],
                                default_positive=sum(r['official_prediction'] for r in group)))
                        lower=upper
    return output


def analyze(alias, manifest):
    folder=ROOT/'results'/alias
    rows=[json.loads(x) for x in (folder/'pilot_real_scores.jsonl').read_text(encoding='utf-8').splitlines()]
    completion=validate(alias,rows,manifest)
    target=folder/'pilot_results.json'
    if target.exists():raise FileExistsError(target)
    command=[sys.executable,str(PILOT/'score_pilot.py'),'--input',str(folder/'pilot_real_scores.jsonl'),'--output',str(target),'--fpr-budget','0.10']
    subprocess.run(command,check=True)
    original=json.loads(target.read_text(encoding='utf-8'))
    clean=[r for r in rows if r['split']=='calibration' and r['label']==0]
    test=[r for r in rows if r['split']=='test']
    methods,curves,table={},{},[]
    assert len(clean)==80 and len(test)==160
    for method in independent.METHODS:
        reference=[independent.value(r,method,clean,True) for r in clean]
        threshold=math.nextafter(sorted(reference,reverse=True)[math.floor(.10*len(clean))],math.inf)
        expected=original['methods'][method]
        assert math.isclose(threshold,expected['calibration_threshold'],abs_tol=2e-12,rel_tol=2e-12)
        values=[independent.value(r,method,clean) for r in test]
        decisions=[s>expected['calibration_threshold'] for s in values]
        observed=independent.metrics([r['label'] for r in test],decisions)
        assert observed==expected['test_overall']
        by_domain={}
        for domain in ['email','resume']:
            ix=[i for i,r in enumerate(test) if r['domain']==domain]
            counts=independent.metrics([test[i]['label'] for i in ix],[decisions[i] for i in ix])
            assert counts==expected['test_by_domain'][domain]
            by_domain[domain]=independent.with_intervals(counts)
        curves[method]=independent.roc(test,values)
        methods[method]={'threshold':expected['calibration_threshold'],'calibration_clean_n':80,
            'calibration_false_positives_loo_if_length':sum(s>expected['calibration_threshold'] for s in reference),
            'calibration_replay_including_self_fp':sum(independent.value(r,method,clean)>expected['calibration_threshold'] for r in clean),
            'holdout_overall':independent.with_intervals(observed),'holdout_by_domain':by_domain,
            'descriptive_holdout_roc_tpr_at_empirical_fpr_le_10_percent_not_deployed':max(p['tpr'] for p in curves[method] if p['fpr']<=.1)}
        for domain,counts in [('overall',observed),*by_domain.items()]:
            table.append(dict(detector=alias,method=method,domain=domain,threshold=expected['calibration_threshold'],**{k:counts[k] for k in ['tp','fp','tn','fn','tpr','fpr']}))
    diag=diagnostics(test,'holdout')
    support=all(diag[d]['benign_score_vs_tokens']['rho'] is not None and diag[d]['benign_score_vs_tokens']['rho']>0
        and diag[d]['benign_score_vs_tokens']['permutation_two_sided_p']<=.025
        and diag[d]['max_top2_rank_inversions']+diag[d]['max_q90_rank_inversions']>0 for d in ['email','resume'])
    result={'detector':alias,'formal_paper_experiment':False,'n_variants':320,'n_sources':160,
        'n_calibration_clean':80,'n_holdout_benign':80,'n_holdout_attack':80,'original_label_matches':320,
        'independent_statistics':'PASS','scores_sha256':completion['scores_sha256'],'methods':methods,
        'holdout_length_diagnostics':diag,'calibration_length_diagnostics_descriptive_only':diagnostics([r for r in rows if r['split']=='calibration'],'calibration'),
        'score_distributions':distributions(rows),'H1_predeclared_holdout_gate_passed':support,
        'official_prefix_calls':sum(r['official_evaluated_chunks'] for r in rows),
        'shadow_suffix_calls':sum(r['shadow_suffix_chunks'] for r in rows),'full_calls':sum(r['chunk_count'] for r in rows),
        'warnings':['Independent from prior pilot sources, not from original R0-R4 public population',
            'Same calibration FPR budget does not guarantee equal holdout or population FPR',
            'No heldout-threshold retuning; ROC envelope is descriptive ranking only',
            'H1 association is not a causal length effect; content, chunk position and domain can confound',
            'DistilBERT LABEL_1 meaning still unverified; preserve official mapping',
            'Exploratory three-detector replication, no family-wide confirmatory claim']}
    for name,data in [('independent_audit.json',result),('roc_points.json',curves)]:
        with (folder/name).open('x',encoding='utf-8') as stream:json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False)
    return rows,result,table,curves


def charts(all_data):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from scipy.stats import rankdata
    output=ROOT/'figures';output.mkdir(exist_ok=False)
    plt.rcParams.update({'font.size':9,'figure.dpi':150,'savefig.bbox':'tight'})
    fig,axes=plt.subplots(3,3,figsize=(15,12))
    for col,(alias,rows,result,table,curves) in enumerate(all_data):
        for row_index,domain in enumerate(['email','resume']):
            selected=[r for r in rows if r['split']=='test' and r['label']==0 and r['domain']==domain]
            axes[row_index,col].scatter([r['token_count'] for r in selected],[max(r['chunk_scores']) for r in selected],s=22)
            axes[row_index,col].set(title=f'{alias} / {domain}: 40 benign holdout',xlabel='Document tokens, including special tokens',ylabel='Max selected-class softmax')
            axes[row_index,col].ticklabel_format(axis='y',style='sci',scilimits=(-3,3),useOffset=False)
        axis=axes[2,col]
        for method,points in curves.items():
            line,=axis.step([p['fpr'] for p in points],[p['tpr'] for p in points],where='post',label=method)
            dot=result['methods'][method]['holdout_overall']
            axis.plot(dot['fpr'],dot['tpr'],'o',color=line.get_color(),markersize=4)
        axis.axvline(.1,color='gray',linestyle='--')
        axis.set(title=f'{alias}: descriptive ROC / frozen operating points',xlabel='Observed FPR (80 benign holdout)',ylabel='TPR (80 attacks)',xlim=(-.02,1.02),ylim=(-.02,1.02))
        axis.legend(fontsize=7)
    fig.suptitle('Expanded H1 validation | 160 new sources / 320 variants per detector | exploratory, no superiority claim')
    fig.tight_layout()
    for ext in ['png','pdf']:fig.savefig(output/f'length_and_roc.{ext}')
    plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(15,4))
    for axis,(alias,rows,_,_,_) in zip(axes,all_data):
        for domain,marker in [('email','o'),('resume','^')]:
            clean=[r for r in rows if r['split']=='test' and r['label']==0 and r['domain']==domain]
            axis.scatter(rankdata([independent.basic(r,'max') for r in clean]),rankdata([independent.basic(r,'top2') for r in clean]),marker=marker,label=domain,s=22)
        axis.plot([1,40],[1,40],':',color='gray');axis.legend()
        axis.set(title=alias,xlabel='Within-domain Max rank',ylabel='Within-domain Top-2 rank')
    fig.suptitle('40 heldout benign sources per domain; rank differences are not quality improvements')
    fig.tight_layout()
    for ext in ['png','pdf']:fig.savefig(output/f'rank_changes.{ext}')
    plt.close(fig)


def write_reports(all_data):
    plan=json.loads((ROOT/'plan.json').read_text(encoding='utf-8'))
    lines=['# 扩大验证：H1 长度关联与公平校准', '',
        '本轮仅扩大证据，不训练、不实现新防御。与上一轮40源烟测无交集，来自同一公开总体剩余160源；不是新的独立论文测试。每检测器320个clean/Authority Spoof变体，每域40源校准、40源留出；每方法只用80个良性校准文档设阈值，随后锁定。', '',
        '## 观测结果与置信限制','',
        '同一检测器、同一数据采用相同10%校准经验FPR预算，留出报告实际FPR。不同观察FPR的TPR不能直接证明某聚合更好。留出总体80个良性，域内各40个；仍不能保证5%或10%部署FPR。所有比例的Wilson区间保留于JSON。', '',
        '| 检测器 | 方法 | 域 | TP | FP | TN | FN | TPR | FPR |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for alias,rows,result,table,curves in all_data:
        for entry in table:lines.append('| {detector} | {method} | {domain} | {tp} | {fp} | {tn} | {fn} | {tpr:.4f} | {fpr:.4f} |'.format(**entry))
    lines+=['','## 留出良性长度诊断','',
        '| 检测器 | 域 | n | token–Max ρ | 双侧置换 p | 默认 FP | Max/Top-2 反转 | Max/Q90 反转 | 多块文档 | 尾块为最大值 |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for alias,rows,result,table,curves in all_data:
        for domain,stats in result['holdout_length_diagnostics'].items():
            corr=stats['benign_score_vs_tokens']
            rho='NA' if corr['rho'] is None else f"{corr['rho']:.4f}"
            lines.append(f"| {alias} | {domain} | {stats['benign_n']} | {rho} | {corr['permutation_two_sided_p']} | {stats['default_fp']} | {stats['max_top2_rank_inversions']} | {stats['max_q90_rank_inversions']} | {stats['multiple_chunks_n']} | {stats['last_chunk_is_max_n']} |")
        lines+=['',f"{alias}：H1 预定义留出支持门槛 = **{result['H1_predeclared_holdout_gate_passed']}**。"]
    lines+=['','门槛沿用原规则：同一检测器在两个域内均ρ>0且双侧置换p≤0.025，并在各域出现至少一次Max/Top-2或Max/Q90排序反转。复核样本仅使用本轮留出良性源；校准集关联另存，仅作描述。三检测器为探索性复核，不据此作家族层面的确认性显著性结论。',
        '领域、内容和块位置可能混杂；单纯更长或尾块得分高不能证明长度导致误报。DistilBERT官方LABEL_1的语义仍未确认，保留原行为，不能为得到好结果翻转类别。', '',
        '## 复核与来源','',
        f"数据 revision：`{plan['dataset_revision']}`；上游 commit：`{plan['upstream_commit']}`；样本清单 SHA256：`{plan['sample_manifest_sha256']}`。",
        '完整模型版本、环境、输入commit和源码hash见 `results/<detector>/manifest.json` / `completion.json`。Windows UTF-8启动前失败及修复diff单独保留；该次没有加载模型或产出评分，未覆盖既有输出。',
        '原始用户score_pilot.py按每模型真实分数先执行；另用NumPy/SciPy实现独立核验softmax、风险映射、默认标签、阈值和总体/分域混淆矩阵。保留原始logits/softmax和块坐标，可逐条追溯。默认判定仅作核对，不是唯一比较基线。',
        '按split/domain/label以及token/chunk桶的n和min/Q25/median/Q75/max见各 `independent_audit.json:score_distributions`；ROC点是描述性排序，不能用它重新选择部署阈值。', '',
        '图：`figures/length_and_roc.png`、`figures/rank_changes.png`，同时提供PDF。本轮非正式论文实验；不报告下游LLM攻击成功率或合法任务损伤。','']
    (ROOT/'length_diagnostics.md').write_text('\n'.join(lines),encoding='utf-8')
    gates={a:r['H1_predeclared_holdout_gate_passed'] for a,_,r,_,_ in all_data}
    decision=['# Go / No-go','',f'本轮留出H1支持门槛：`{json.dumps(gates)}`。',
        '工程评分与离线重放验证完成。H1支持只能解释为当前公开域与攻击条件下的探索性关联证据，不是因果结论，也不是长度校准优于Max的证据。']
    if any(gates.values()):decision+=['','有条件GO：可单独提交下一阶段的证据补足方案，优先区分内容与尾块位置影响；本轮不实现多尺度或疑难区域复核，不开始训练，不调低阈值制造安全收益。']
    else:decision+=['','方法开发NO-GO：没有检测器满足预定义跨域支持门槛。保留局部关联及失败模式，不推进多尺度或疑难区域复核实现。门槛未通过不证明不存在长度效应。']
    decision+=['','样本和阈值预先冻结，未根据留出分数或ASR选模型、换标签、调阈值或筛样本。R0–R4、旧烟测和原始数据均保持不变。详见length_diagnostics.md及每模型独立审计。','']
    (ROOT/'go_no_go.md').write_text('\n'.join(decision),encoding='utf-8')
    (ROOT/'score_schema.md').write_text('# 标准得分与原始记录\n\n沿用上轮score_schema.md及未修改的score_pilot.py字段。每模型单独JSONL，320行，sample_id唯一；source_document_id配对clean/attack不跨split。test表示扩大验证留出，不是独立论文测试。\n\nchunk_count及chunks记录[start_token,end_token)、score、完整logits/softmax、输入token hash与official/shadow前向来源；坐标基于全文一次加特殊token后512分块。score是官方选定风险类softmax分量的最大值，非校准概率。Prompt Guard选INJECTION/JAILBREAK两类的max，其他两模型按官方类别映射。\n\n默认文档判定为Max>=0.5；用户离线scorer采用校准阈值和严格>，两者分开记录。所有原始模型分数保留于results/<detector>/pilot_real_scores.jsonl。\n',encoding='utf-8')
    (ROOT/'environment_audit.md').write_text('# 环境与版本\n\n复用E盘独立CPU环境，torch 2.7.1+cpu、transformers 4.51.3、Python 3.13.9、FP32，每检测器4线程；未下载、安装或修改依赖。权重来自上轮固定hash文件；每次加载前再校验。完整版本见原requirements_cpu_freeze.txt和本轮manifest/completion。\n\n官方检测路径及512切块语义沿用既有审计；记录适配器源码hash不变。新增执行脚本只选择预冻结新源、记录日志并拒绝覆盖。启动前遇到Windows GBK读取UTF-8元数据失败，修复及失败记录位于patches/及execution_attempts/，不修改模型行为。\n\n分析Python使用本机已有NumPy/SciPy/Matplotlib，版本见validation_receipt.json；真实得分来自独立推理环境。所有大文件、缓存及下载临时目录均在E盘，本轮完全离线。R0–R4及主分支不改。\n',encoding='utf-8')
    (ROOT/'README.md').write_text('# 扩大文档检测验证 INGRESS-5060-002\n\n结果入口：[length_diagnostics.md](length_diagnostics.md)、[go_no_go.md](go_no_go.md)。真实分数按检测器分别保存在results/，不混合重复sample_id；原score_pilot输出pilot_results.json及独立审计均在各模型目录。顶层pilot_results.json汇总全部三模型。\n\n每模型320变体/160源，排除上一轮40源；80源校准、80源留出，同源不泄漏。不是独立论文测试或新算法验证。方法表见method_metrics.csv，环境、schema、曲线及不可覆盖运行证据随附。\n\n执行：独立CPU环境运行run.py --detector {deberta,distilbert,prompt-guard}；本机分析Python运行analyze.py。输出存在则拒绝覆盖，不可直接重复执行。\n',encoding='utf-8')


def main():
    old=verify_old()
    if (ROOT/'pilot_results.json').exists():raise FileExistsError('Expanded analysis already exists')
    plan=json.loads((ROOT/'plan.json').read_text(encoding='utf-8'))
    assert sha(PILOT/'score_pilot.py')==plan['supplied_scorer_sha256']
    manifest=[json.loads(x) for x in (ROOT/'sample_manifest.jsonl').read_text().splitlines()]
    previous={r['source_document_id'] for r in map(json.loads,(PILOT/'sample_manifest.jsonl').read_text().splitlines())}
    assert not previous & {r['source_document_id'] for r in manifest}
    data=[(a,*analyze(a,manifest)) for a in ALIASES]
    with (ROOT/'method_metrics.csv').open('x',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(data[0][3][0]));writer.writeheader()
        writer.writerows(r for _,_,_,table,_ in data for r in table)
    charts(data);write_reports(data)
    summary={'status':'REAL_EXPANDED_VALIDATION_AUDITED','formal_paper_experiment':False,'plan_sha256':sha(ROOT/'plan.json'),
        'n_variants_per_detector':320,'n_source_documents':160,'old_pilot_overlap':0,'fpr_budget':.10,
        'detectors':{a:r for a,_,r,_,_ in data}}
    with (ROOT/'pilot_results.json').open('x',encoding='utf-8') as stream:json.dump(summary,stream,ensure_ascii=False,indent=2,allow_nan=False)
    assert verify_old()==old
    import importlib.metadata
    receipt={'status':'INDEPENDENT_NUMERICAL_AUDIT_PASSED_VISUAL_REVIEW_PENDING','finished_utc':datetime.now(timezone.utc).isoformat(),
        'formal_paper_experiment':False,'original_label_matches':960,'old_files_hashes_unchanged':old,'R0_R4_modified':False,
        'analysis_runtime':{k:importlib.metadata.version(k) for k in ['numpy','scipy','matplotlib']},
        'file_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(ROOT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}}
    with (ROOT/'validation_receipt.json').open('x',encoding='utf-8') as stream:json.dump(receipt,stream,indent=2)
    print(json.dumps({'status':summary['status'],'old_files_unchanged':old,'H1':{a:r['H1_predeclared_holdout_gate_passed'] for a,_,r,_,_ in data}}))


if __name__=='__main__':main()
