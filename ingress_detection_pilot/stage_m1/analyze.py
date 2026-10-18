"""Paired descriptive analysis of the frozen M1 panel, no calibration or tuning."""
import csv
import json
from pathlib import Path
import sys
import numpy as np
from scipy.stats import binomtest

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from prepare import sha, write


def load(path):
    return [json.loads(v) for v in Path(path).read_text(encoding='utf-8').splitlines()]


def csv_write(path,rows):
    with path.open('x',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def paired(values):
    x=np.asarray(values,dtype=float)
    rng=np.random.default_rng(20261018)
    b=np.median(x[rng.integers(0,len(x),(10000,len(x)))],axis=1)
    pos=int(np.sum(x>1e-8));neg=int(np.sum(x< -1e-8))
    ci=np.quantile(b,[.025,.975]).tolist()
    return {'n_sources':len(x),'mean_delta':float(x.mean()),'median_delta':float(np.median(x)),
        'median_bootstrap95':ci,'min_delta':float(x.min()),'max_delta':float(x.max()),
        'positive':pos,'negative':neg,'ties_tolerance_1e8':len(x)-pos-neg,
        'two_sided_sign_p':float(binomtest(pos,pos+neg,.5).pvalue) if pos+neg else 1.,
        'screen_consistent':bool((ci[0]>0 or ci[1]<0) and max(pos,neg)>=18)}


def main():
    plan=json.loads((ROOT/'plan.json').read_text(encoding='utf-8'))
    raw=ROOT/'raw'/plan['run_id']
    completion=json.loads((raw/'completion.json').read_text(encoding='utf-8'))
    for name,h in completion['files'].items():assert sha(raw/name)==h
    formats=load(raw/'format_observations.jsonl')
    docs=load(raw/'document_observations.jsonl')
    sources=load(ROOT/'sources_and_conditions.jsonl')
    by={s['source_id']:{r['condition']:r for r in formats if r['source_id']==s['source_id'] and r['condition']!='position_negative_control'} for s in sources}
    assert len(formats)==216 and len(docs)==72 and len(by)==24
    deltas=[];contrasts={}
    for condition in plan['conditions']:
        if condition=='both_special':continue
        values=[];flip_up=flip_down=0
        for sid,obs in by.items():
            a,b=obs['both_special'],obs[condition]
            values.append(b['risk_score']-a['risk_score'])
            flip_up+=int(b['predicted']>a['predicted']);flip_down+=int(b['predicted']<a['predicted'])
            deltas.append({'source_id':sid,'condition':condition,'reference':'both_special',
                'input_sha256':b['input_sha256'],'reference_sha256':a['input_sha256'],
                'core_token_sha256':next(s['core_token_sha256'] for s in sources if s['source_id']==sid),
                'n_tokens':b['n_tokens'],'reference_tokens':a['n_tokens'],
                'risk_score':b['risk_score'],'reference_score':a['risk_score'],
                'delta':b['risk_score']-a['risk_score'],'predicted':b['predicted'],'reference_predicted':a['predicted'],
                'logit_delta_benign':b['logits'][0]-a['logits'][0],
                'logit_delta_injection':b['logits'][1]-a['logits'][1],
                'logit_delta_jailbreak':b['logits'][2]-a['logits'][2]})
        contrasts[condition]={**paired(values),'negative_to_positive':flip_up,'positive_to_negative':flip_down}
    # Holm familywise adjustment for all 6 predeclared comparisons against BOTH.
    ordered=sorted(contrasts,key=lambda k:contrasts[k]['two_sided_sign_p'])
    running=0.
    for i,k in enumerate(ordered):
        running=max(running,min(1.,(len(ordered)-i)*contrasts[k]['two_sided_sign_p']))
        contrasts[k]['holm_sign_p']=running
    negative=[]
    for r in formats:
        if r['condition']=='position_negative_control':
            a=by[r['source_id']]['both_special']
            assert r['input_token_ids']==a['input_token_ids']
            negative.append({'source_id':r['source_id'],'global_index':r['simulated_global_chunk_index'],
                'input_sha256':r['input_sha256'],'max_abs_logit_delta':max(abs(x-y) for x,y in zip(r['logits'],a['logits'])),
                'risk_delta':r['risk_score']-a['risk_score']})
    docrows=[]
    for r in docs:
        scores=r['chunk_scores'];prediction=int(max(scores)>=.5)
        assert prediction==r['official_prediction']
        assert all(len(c['input_token_ids'])==c['end_token']-c['start_token'] for c in r['chunks'])
        docrows.append({'source_id':r['source_id'],'condition':r['condition'],'n_tokens':r['token_count'],
            'n_chunks':r['chunk_count'],'first_score':scores[0],'last_score':scores[-1],
            'document_max':max(scores),'official_prediction':prediction,
            'preceding_max':max(scores[:-1],default=0.),
            'tail_attributable_positive':int(len(scores)>1 and scores[-1]>=.5 and max(scores[:-1])<.5),
            'official_evaluated_chunks':r['official_evaluated_chunks'],'shadow_chunks':r['shadow_suffix_chunks']})
    summary={}
    for condition in ['standalone','aligned_tail','split_core']:
        rows=[r for r in docrows if r['condition']==condition]
        summary[condition]={'n':len(rows),'false_positives':sum(r['official_prediction'] for r in rows),
            'constructed_panel_fpr':sum(r['official_prediction'] for r in rows)/len(rows),
            'tail_attributable_positives':sum(r['tail_attributable_positive'] for r in rows),
            'median_document_max':float(np.median([r['document_max'] for r in rows])),
            'by_style':{d:{'n':12,'false_positives':sum(r['official_prediction'] for r in rows if next(s['style'] for s in sources if s['source_id']==r['source_id'])==d)} for d in ['email','resume']}}
    comparisons={}
    docmap={(r['source_id'],r['condition']):r for r in docrows}
    for a,b in [('standalone','aligned_tail'),('aligned_tail','split_core')]:
        av=[docmap[s['source_id'],a] for s in sources];bv=[docmap[s['source_id'],b] for s in sources]
        comparisons[f'{b}_minus_{a}']={**paired([y['document_max']-x['document_max'] for x,y in zip(av,bv)]),
            'negative_to_positive':sum(y['official_prediction']>x['official_prediction'] for x,y in zip(av,bv)),
            'positive_to_negative':sum(y['official_prediction']<x['official_prediction'] for x,y in zip(av,bv)),
            'causal_caveat':'Different carrier context/length; not isolated boundary causation or population FPR'}
    result={'run_id':plan['run_id'],'n_sources':24,'formal_paper_experiment':False,
        'format_contrasts':contrasts,'position_negative_controls':{'n_reexecutes':len(negative),
            'max_abs_risk_delta':max(abs(r['risk_delta']) for r in negative),
            'max_abs_logit_delta':max(r['max_abs_logit_delta'] for r in negative)},
        'official_document_summary':summary,'official_document_comparisons':comparisons,
        'risk_semantics':'Uncalibrated model softmax-derived risk, not probability of attack in deployment',
        'scope':'24 authored benign fragments; shared author and repeated carrier; variants not independent samples; no attack sensitivity test; no general population FPR inference',
        'raw_files':{p.name:sha(p) for p in raw.iterdir() if p.is_file()}}
    write(ROOT/'mechanism_results.json',result)
    csv_write(ROOT/'paired_differences.csv',deltas)
    csv_write(ROOT/'document_decisions.csv',docrows)
    csv_write(ROOT/'negative_controls.csv',negative)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,2,figsize=(11,4.6),layout='constrained')
    for sid,obs in by.items():
        axs[0].plot([0,1],[obs['both_special']['risk_score'],obs['tail_sep_only']['risk_score']],color='#286ca4',alpha=.5,marker='o',ms=3)
    axs[0].set_xticks([0,1],['[CLS] + core + [SEP]','core + [SEP]'])
    axs[0].set_title('Same core: 24 paired new fragments')
    for i,condition in enumerate(['standalone','aligned_tail','split_core']):
        vals=[r['document_max'] for r in docrows if r['condition']==condition]
        axs[1].scatter(np.full(len(vals),i)+np.linspace(-.1,.1,len(vals)),vals,s=18,alpha=.7)
    axs[1].set_xticks([0,1,2],['Standalone','Aligned tail','Split core'])
    axs[1].set_title('Official document Max: constructed panel')
    for ax in axs:
        ax.axhline(.5,color='#b33b3b',linestyle='--',label='Original threshold 0.5')
        ax.set_ylim(-.02,1.02);ax.set_ylabel('Softmax-derived risk (uncalibrated)');ax.legend(fontsize=8)
    fig.suptitle('M1 exploratory mechanism check; no population FPR claim')
    fig.savefig(ROOT/'mechanism_panel.png',dpi=180)
    fig.savefig(ROOT/'mechanism_panel.svg')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
