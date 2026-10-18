"""Independently validate supplied replay statistics and describe real scores.

This script never supplies model scores. Random permutations only quantify
uncertainty in associations between existing benign scores and lengths.
"""
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

import numpy as np
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parent
METHODS = ['max', 'top2', 'q90', 'length_calibrated_max']


def basic(row, method):
    values = np.asarray(row['chunk_scores'], dtype=float)
    if method == 'max': return float(np.max(values))
    if method == 'top2': return float(np.mean(np.sort(values)[-2:]))
    if method == 'q90': return float(np.quantile(values, .90, method='linear'))
    raise ValueError(method)


def value(row, method, clean, loo=False):
    if method != 'length_calibrated_max':
        return basic(row, method)
    refs = [r for r in clean if not (loo and r['sample_id'] == row['sample_id'])]
    distances = np.abs(np.log1p([r['chunk_count'] for r in refs]) - np.log1p(row['chunk_count']))
    order = np.lexsort(([r['sample_id'] for r in refs], distances))
    size = min(len(refs), max(20, int(np.ceil(.35*len(refs)))))
    maxima = np.array([max(refs[i]['chunk_scores']) for i in order[:size]])
    return float(-np.log10((1 + np.count_nonzero(maxima >= max(row['chunk_scores']))) / (size+1)))


def metrics(labels, predictions):
    tp = sum(l == 1 and p for l,p in zip(labels,predictions))
    fp = sum(l == 0 and p for l,p in zip(labels,predictions))
    tn = sum(l == 0 and not p for l,p in zip(labels,predictions))
    fn = sum(l == 1 and not p for l,p in zip(labels,predictions))
    return {'tp':tp,'fp':fp,'tn':tn,'fn':fn,'tpr':tp/(tp+fn) if tp+fn else None,'fpr':fp/(fp+tn) if fp+tn else None}


def wilson(k, n):
    if not n: return None
    z = statistics.NormalDist().inv_cdf(.975)
    center = (k/n + z*z/(2*n))/(1+z*z/n)
    half = z*math.sqrt(k/n*(1-k/n)/n + z*z/(4*n*n))/(1+z*z/n)
    return [max(0.,center-half), min(1.,center+half)]


def with_intervals(result):
    return dict(result, tpr_wilson_95=wilson(result['tp'],result['tp']+result['fn']),
                fpr_wilson_95=wilson(result['fp'],result['fp']+result['tn']))


def validate_rows(rows):
    assert len(rows) == 80 and len({r['sample_id'] for r in rows}) == 80
    groups = defaultdict(list)
    for row in rows:
        assert type(row['label']) is int and row['label'] in [0,1]
        assert row['domain'] in ['email','resume'] and row['split'] in ['calibration','test']
        assert row['chunk_count'] == len(row['chunk_scores']) == len(row['chunks']) > 0
        assert all(isinstance(s,(int,float)) and not isinstance(s,bool) and math.isfinite(s) and 0 <= s <= 1 for s in row['chunk_scores'])
        assert row['chunk_count'] == math.ceil(row['token_count']/512)
        for i,chunk in enumerate(row['chunks']):
            assert (chunk['start_token'],chunk['end_token']) == (512*i,min(512*(i+1),row['token_count']))
            assert chunk['score'] == row['chunk_scores'][i]
            logits = np.array(chunk['logits'],dtype=float)
            shifted = logits - logits.max()
            probabilities = np.exp(shifted) / np.exp(shifted).sum()
            assert np.allclose(probabilities,chunk['softmax'],atol=2e-7,rtol=2e-6)
            # Both measured classifiers use class 1 under the official mapping.
            assert math.isclose(chunk['score'],chunk['softmax'][1],rel_tol=0,abs_tol=1e-12)
        assert int(max(row['chunk_scores']) >= .5) == row['official_prediction']
        groups[row['source_document_id']].append(row)
    assert len(groups) == 40
    assert all(len(g)==2 and {r['label'] for r in g}=={0,1} and len({r['split'] for r in g})==1 for g in groups.values())
    assert Counter((r['domain'],r['label']) for r in rows) == Counter({(d,l):20 for d in ['email','resume'] for l in [0,1]})


def roc(rows, values):
    labels = np.asarray([r['label'] for r in rows])
    scores = np.asarray(values)
    points = [{'fpr':0.,'tpr':0.}]
    for cut in sorted(set(values),reverse=True):
        predictions = scores >= cut
        result = metrics(labels.tolist(),predictions.tolist())
        points.append({'fpr':result['fpr'],'tpr':result['tpr']})
    # A curve description only. No threshold from this curve is deployed.
    return points


def correlation(x,y,permutations=3999):
    x,y = rankdata(x),rankdata(y)
    if len(set(x))<2 or len(set(y))<2:
        return {'rho':None,'permutation_two_sided_p':None,'n':len(x),'reason':'constant ranks'}
    x=(x-x.mean())/np.linalg.norm(x-x.mean()); y=(y-y.mean())/np.linalg.norm(y-y.mean())
    rho=float(x@y)
    generator=np.random.default_rng(20261018)
    extreme=sum(abs(float(x@generator.permutation(y))) >= abs(rho)-1e-12 for _ in range(permutations))
    return {'rho':rho,'permutation_two_sided_p':(1+extreme)/(1+permutations),'n':len(x),
            'permutations':permutations,'seed':20261018}


def inversions(rows,a,b):
    return sum((basic(x,a)-basic(y,a))*(basic(x,b)-basic(y,b)) < 0 for x,y in itertools.combinations(rows,2))


def analyze(alias):
    folder=ROOT/'results'/alias
    source=folder/'pilot_real_scores.jsonl'
    rows=[json.loads(line) for line in source.read_text(encoding='utf-8').splitlines()]
    validate_rows(rows)
    # Exact requested evaluator, preserved byte-for-byte, runs before independent audit.
    output=folder/'pilot_results.json'
    if output.exists():
        raise FileExistsError('Refuse to overwrite replay output')
    command=[sys.executable,str(ROOT/'score_pilot.py'),'--input',str(source),'--output',str(output),'--fpr-budget','0.10']
    subprocess.run(command,check=True)
    original=json.loads(output.read_text(encoding='utf-8'))
    clean=[r for r in rows if r['split']=='calibration' and r['label']==0]
    test=[r for r in rows if r['split']=='test']
    summaries,curves={},{}
    table=[]
    for method in METHODS:
        cal_values=[value(r,method,clean,True) for r in clean]
        # Independent order-statistic construction; same comparator semantics as supplied scaffold.
        allowed=int(.10*len(clean)); cut=math.nextafter(sorted(cal_values)[-(allowed+1)],math.inf)
        observed=original['methods'][method]
        assert math.isclose(cut,observed['calibration_threshold'],abs_tol=2e-12,rel_tol=2e-12)
        scores=[value(r,method,clean) for r in test]
        predictions=[s > observed['calibration_threshold'] for s in scores]
        overall=metrics([r['label'] for r in test],predictions)
        assert overall==observed['test_overall']
        per_domain={}
        for domain in ['email','resume']:
            indices=[i for i,r in enumerate(test) if r['domain']==domain]
            result=metrics([test[i]['label'] for i in indices],[predictions[i] for i in indices])
            assert result==observed['test_by_domain'][domain]
            per_domain[domain]=with_intervals(result)
        calibration_fps=sum(v>observed['calibration_threshold'] for v in cal_values)
        deployed_cal_fps=sum(value(r,method,clean)>observed['calibration_threshold'] for r in clean)
        curves[method]=roc(test,scores)
        envelope=max(point['tpr'] for point in curves[method] if point['fpr']<=.10)
        summaries[method]={'threshold':observed['calibration_threshold'],'calibration_false_positives_loo_if_applicable':calibration_fps,
            'calibration_clean_n':len(clean),'calibration_empirical_fpr':calibration_fps/len(clean),
            'calibration_replay_including_self_false_positives':deployed_cal_fps,
            'development_holdout_overall':with_intervals(overall),'development_holdout_by_domain':per_domain,
            'descriptive_roc_tpr_envelope_at_fpr_le_0_10_not_deployed':envelope}
        for domain,result in [('overall',overall),*per_domain.items()]:
            table.append({'detector':alias,'method':method,'domain':domain,'threshold':observed['calibration_threshold'],
                          **{k:result[k] for k in ['tp','fp','tn','fn','tpr','fpr']}})
    diagnostics={}
    for domain in ['email','resume','pooled']:
        selected=[r for r in rows if r['label']==0 and (domain=='pooled' or r['domain']==domain)]
        diagnostics[domain]={
            'benign_score_vs_tokens':correlation([r['token_count'] for r in selected],[max(r['chunk_scores']) for r in selected]),
            'benign_score_vs_chunks':correlation([r['chunk_count'] for r in selected],[max(r['chunk_scores']) for r in selected]),
            'default_fp':sum(r['official_prediction'] for r in selected),'benign_n':len(selected),
            'max_top2_rank_inversions':inversions(selected,'max','top2'),
            'max_q90_rank_inversions':inversions(selected,'max','q90')}
    bins=[]
    for domain in ['email','resume']:
        for label in [0,1]:
            for field,edges in [('chunk_count',[1,4,8]),('token_count',[512,2048,4096])]:
                selected=[r for r in rows if r['domain']==domain and r['label']==label]
                lower=0
                for upper in [*edges,None]:
                    group=[r for r in selected if r[field]>lower and (upper is None or r[field]<=upper)]
                    if group:
                        values=[max(r['chunk_scores']) for r in group]
                        bins.append({'domain':domain,'label':label,'field':field,'range':f'({lower},{upper or "inf"}]',
                            'n':len(group),'score_min':min(values),'score_q25':float(np.quantile(values,.25)),
                            'score_median':statistics.median(values),'score_q75':float(np.quantile(values,.75)),
                            'score_max':max(values),'default_positive':sum(r['official_prediction'] for r in group)})
                    lower=upper
    support=all(diagnostics[d]['benign_score_vs_tokens']['rho'] is not None
                and diagnostics[d]['benign_score_vs_tokens']['rho']>0
                and diagnostics[d]['benign_score_vs_tokens']['permutation_two_sided_p']<=.025
                and diagnostics[d]['max_top2_rank_inversions']+diagnostics[d]['max_q90_rank_inversions']>0
                for d in ['email','resume'])
    result={'detector':alias,'real_model_scores':True,'formal_paper_experiment':False,
        'scores_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'n_documents':80,'n_source_documents':40,'n_calibration_clean':24,'n_development_holdout':32,
        'original_label_matches':80,'independent_replay_checks':'PASS','methods':summaries,
        'length_associations':diagnostics,'score_distributions':bins,'H1_predeclared_support_gate_passed':support,
        'counterfactual_suffix_chunks':sum(r['shadow_suffix_chunks'] for r in rows),
        'official_prefix_model_calls':sum(r['official_evaluated_chunks'] for r in rows),
        'full_model_calls':sum(r['chunk_count'] for r in rows),
        'warnings':['Calibration budget is empirical, not a guarantee of heldout or population FPR',
          'Test schema split is development holdout; all source documents overlap original public reproduction population',
          'Length neighborhood is 20/24 clean calibration documents; little local support',
          'ROC envelope is a descriptive ranking upper envelope, never a selected deployment threshold',
          'Small domain holdout: 8 benign and 8 attack documents; rates change in 12.5 percentage-point steps',
          'Length associations pool calibration and development benign data for exploratory H1 diagnosis only']}
    with (folder/'independent_audit.json').open('x',encoding='utf-8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
    with (folder/'roc_points.json').open('x',encoding='utf-8') as stream:
        json.dump(curves,stream,indent=2)
    return rows,result,table,curves


def charts(all_data):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder=ROOT/'figures'; folder.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':10,'figure.dpi':150,'savefig.bbox':'tight'})
    fig,axes=plt.subplots(2,2,figsize=(11,8))
    for col,(alias,rows,result,table,curves) in enumerate(all_data):
        for domain,marker in [('email','o'),('resume','^')]:
            selected=[r for r in rows if r['label']==0]
            selected=[r for r in selected if r['domain']==domain]
            axes[0,col].scatter([r['token_count'] for r in selected],[max(r['chunk_scores']) for r in selected],label=domain,marker=marker,alpha=.8)
        axes[0,col].set(xlabel='Document tokens (special tokens included)',ylabel='Max selected-class softmax score',title=f'{alias}: 40 real benign documents')
        axes[0,col].legend(); axes[0,col].set_ylim(-.03,1.03)
        for method,points in curves.items():
            line,=axes[1,col].step([r['fpr'] for r in points],[r['tpr'] for r in points],where='post',label=method)
            point=result['methods'][method]['development_holdout_overall']
            axes[1,col].plot(point['fpr'],point['tpr'],'o',markersize=4,color=line.get_color())
        axes[1,col].axvline(.1,color='gray',linestyle='--',label='exploratory FPR budget')
        axes[1,col].set(xlabel='Observed document FPR (16 benign holdout)',ylabel='TPR (16 attack holdout)',title=f'{alias}: descriptive ROC; dots = locked thresholds',xlim=(-.02,1.02),ylim=(-.02,1.02))
        axes[1,col].legend(fontsize=7)
    fig.suptitle('Engineering pilot only | 40 sources, 80 variants per detector | no paper performance claim')
    fig.tight_layout()
    fig.savefig(folder/'length_and_roc.png');fig.savefig(folder/'length_and_roc.pdf');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for axis,(alias,rows,_,_,_) in zip(axes,all_data):
        clean=[r for r in rows if r['label']==0]
        for domain,marker in [('email','o'),('resume','^')]:
            selected=[r for r in clean if r['domain']==domain]
            # Sorted by observed max solely to display ranking changes.
            rank_max=rankdata([basic(r,'max') for r in selected])
            rank_top=rankdata([basic(r,'top2') for r in selected])
            axis.scatter(rank_max,rank_top,label=domain,marker=marker)
        axis.plot([1,20],[1,20],':',color='gray')
        axis.set(xlabel='Within-domain Max rank',ylabel='Within-domain Top-2 rank',title=alias)
        axis.legend()
    fig.suptitle('Real benign-score rank changes; neither ranking is ground truth')
    fig.tight_layout();fig.savefig(folder/'rank_changes.png');fig.savefig(folder/'rank_changes.pdf');plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(11,7))
    for col,(alias,rows,_,_,_) in enumerate(all_data):
        for row_index,domain in enumerate(['email','resume']):
            selected=[r for r in rows if r['label']==0 and r['domain']==domain]
            axis=axes[row_index,col]
            axis.scatter([r['token_count'] for r in selected],[max(r['chunk_scores']) for r in selected],s=25)
            axis.set(xlabel='Tokens',ylabel='Max selected-class softmax score',title=f'{alias} / {domain}: 20 benign sources')
            axis.ticklabel_format(axis='y',style='sci',scilimits=(-3,3),useOffset=False)
    fig.suptitle('Within-domain length diagnostics | independent y-axis zooms; compare trends, not height')
    fig.tight_layout();fig.savefig(folder/'within_domain_length_zoom.png');fig.savefig(folder/'within_domain_length_zoom.pdf');plt.close(fig)


def main():
    all_data=[]
    for alias in ['deberta','distilbert']:
        rows,result,table,curves=analyze(alias)
        all_data.append((alias,rows,result,table,curves))
    import csv
    with (ROOT/'method_metrics.csv').open('x',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(all_data[0][3][0]));writer.writeheader()
        writer.writerows(row for _,_,_,table,_ in all_data for row in table)
    charts(all_data)
    summary={'status':'TWO_PUBLIC_DETECTORS_REAL_SCORES_VERIFIED','is_formal_paper_experiment':False,
        'primary_detector':'deberta','fpr_budget':.10,'prompt_guard':'Deferred by owner; anonymous protected config request 401',
        'input_plan_sha256':hashlib.sha256((ROOT/'pilot_plan.json').read_bytes()).hexdigest(),
        'supplied_scorer_sha256':hashlib.sha256((ROOT/'score_pilot.py').read_bytes()).hexdigest(),
        'detectors':{alias:result for alias,_,result,_,_ in all_data}}
    with (ROOT/'pilot_results.json').open('x',encoding='utf-8') as stream:
        json.dump(summary,stream,indent=2,ensure_ascii=False,allow_nan=False)
    # The requested root JSONL always refers to the predeclared primary model.
    # Do not mix detector populations or duplicate IDs in one evaluator input.
    with (ROOT/'pilot_real_scores.jsonl').open('xb') as stream:
        stream.write((ROOT/'results/deberta/pilot_real_scores.jsonl').read_bytes())
    print('Real-score statistics independently verified; documents still require narrative review')


if __name__ == '__main__':
    main()
