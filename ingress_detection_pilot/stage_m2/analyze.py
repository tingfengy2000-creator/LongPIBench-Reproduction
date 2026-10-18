"""M2 descriptive paired analysis. Full run only; never optimize thresholds."""
from itertools import combinations
import csv
import json
from pathlib import Path
import sys
import numpy as np
from scipy.stats import binomtest

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(ROOT))
from prepare import sha,ih,write

PRIMARY=[('official','A_complete','B_cross'),('official','A_complete','C_tail'),
    ('shadow','offset0','offset256'),('recovery','native_truncated','native_full'),
    ('recovery','matched512_truncated','matched512_full'),('controls','local16','replace_cls')]


def table(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def cm(rows):
    tp=sum(r['label']==1 and r['prediction']==1 for r in rows)
    fp=sum(r['label']==0 and r['prediction']==1 for r in rows)
    tn=sum(r['label']==0 and r['prediction']==0 for r in rows)
    fn=sum(r['label']==1 and r['prediction']==0 for r in rows)
    return {'tp':tp,'fp':fp,'tn':tn,'fn':fn,'tpr':tp/(tp+fn) if tp+fn else None,
        'fpr':fp/(fp+tn) if fp+tn else None,'fnr':fn/(tp+fn) if tp+fn else None,
        'benign_pass_rate':tn/(tn+fp) if tn+fp else None}


def delta_stats(before,after):
    assert len(before)==len(after)>0
    delta=np.array([b['risk_score']-a['risk_score'] for a,b in zip(before,after)])
    error=np.array([int(b['prediction']!=b['label'])-int(a['prediction']!=a['label']) for a,b in zip(before,after)])
    rng=np.random.default_rng(20261019);resample=rng.integers(0,len(delta),(10000,len(delta)))
    ci=np.quantile(np.median(delta[resample],axis=1),[.025,.975]).tolist()
    eci=np.quantile(np.mean(error[resample],axis=1),[.025,.975]).tolist()
    up=sum(a['prediction']==0 and b['prediction']==1 for a,b in zip(before,after))
    down=sum(a['prediction']==1 and b['prediction']==0 for a,b in zip(before,after))
    return {'n_sources':len(delta),'risk_mean_delta':float(delta.mean()),'risk_median_delta':float(np.median(delta)),
        'risk_median_bootstrap95':ci,'error_rate_delta':float(error.mean()),'error_delta_bootstrap95':eci,
        'negative_to_positive':up,'positive_to_negative':down,
        'errors_corrected':int(np.sum(error<0)),'new_errors':int(np.sum(error>0)),
        'mcnemar_exact_p':float(binomtest(up,up+down,.5).pvalue) if up+down else 1.}


def main():
    plan=json.loads((ROOT/'plan.json').read_text())
    receipt=json.loads((ROOT/'full_receipt.json').read_text())
    raw=Path(receipt['observations_path'])
    assert sha(raw)==receipt['observations_sha256'] and receipt['n_sources']==40
    rows=[json.loads(x) for x in raw.read_text().splitlines()]
    flat=[];obs={};rawmap={}
    for row in rows:
        sid,label=row['source_id'],row['label'];rawmap[sid,label]=row
        shared={k:row[k] for k in ['source_id','domain','text_type','label','variant','semantic_family']}
        scopes={'official':row['official'],'shadow':{'offset0':row['official']['B_cross'],'offset256':row['shadow']},
            'recovery':row['recovery'],'controls':row['controls']}
        for scope,conditions in scopes.items():
            for cond,r in conditions.items():
                core_range=r.get('core_token_range',row['official']['B_cross']['core_token_range'])
                attack_span=r.get('attack_span',row['official']['B_cross']['attack_span'])
                coordinates='whole_document_token_offsets'
                if scope in ['recovery','controls']:
                    n=len(row['official']['core_reference']['chunks'][0]['input_token_ids'])-2
                    if scope=='recovery':
                        begin=0 if cond.endswith('_full') else max(0,row['core_cut']-16) if cond.endswith('_partial16') else row['core_cut']
                        local=511-(n-begin) if cond.startswith('matched512_') else 1
                    else:
                        begin=0;local=192 if cond=='local192' else 1 if cond.startswith('global') else 16
                    core_range=[local,local+n-begin]
                    lo,hi=row['core_target_range'];a=max(lo,begin);b=min(hi,n)
                    attack_span=[local+a-begin,local+b-begin] if row['label'] and a<b else None
                    coordinates='local_window_offsets; inherited source core may be truncated'
                entry=shared|{'scope':scope,'condition':cond,'risk_score':r['risk_score'],'prediction':r['prediction'],
                    'unit':'official document' if scope=='official' else 'counterfactual diagnostic; inherited source label',
                    'input_sha256':r.get('input_sha256',r.get('whole_input_sha256')),
                    'token_count':r.get('token_count',r.get('n_tokens',1024)),
                    'chunk_count':r.get('chunk_count',len(r.get('chunks',[])) or 1),
                    'chunk_scores':json.dumps([c['risk_score'] for c in r['chunks']]) if 'chunks' in r else json.dumps([r['risk_score']]),
                    'core_token_range':json.dumps(core_range),'attack_span':json.dumps(attack_span),'coordinate_system':coordinates,
                    'chunk_boundaries':json.dumps([[c['start_token'],c['end_token']] for c in r['chunks']]) if 'chunks' in r else 'diagnostic local window',
                    'special_token_layout':json.dumps([c['special_token_positions'] for c in r['chunks']]) if 'chunks' in r else json.dumps(r['special_token_positions'])}
                flat.append(entry);obs[sid,label,scope,cond]=entry
    assert len(rows)==80 and len({r['source_id'] for r in rows})==40
    for scope,name in [('official','03_official_chunk_results.csv'),('shadow','04_shadow_chunk_results.csv'),('recovery','05_context_recovery_results.csv'),('controls','control_results.csv')]:
        table(ROOT/name,[r for r in flat if r['scope']==scope])
    # Per-condition confusion and source-resampled uncertainty; labels remain paired.
    metrics=[]
    for scope,condition in sorted({(r['scope'],r['condition']) for r in flat}):
        base=[r for r in flat if (r['scope'],r['condition'])==(scope,condition)]
        for domain in ['overall','email','resume']:
            for kind in ['all','ordinary','hard_benign']:
                subset=[r for r in base if (domain=='overall' or r['domain']==domain) and (kind=='all' or r['text_type']==kind)]
                sources=sorted({r['source_id'] for r in subset})
                preds=np.array([[next(r['prediction'] for r in subset if r['source_id']==s and r['label']==label) for label in [0,1]] for s in sources])
                rng=np.random.default_rng(20261019);idx=rng.integers(0,len(sources),(10000,len(sources)))
                boots=preds[idx].mean(axis=1)
                intervals={'fpr':np.quantile(boots[:,0],[.025,.975]).tolist(),'tpr':np.quantile(boots[:,1],[.025,.975]).tolist()}
                metrics.append({'scope':scope,'condition':condition,'domain':domain,'text_type':kind,
                    'n_sources':len(sources),'n_inputs':len(subset),**cm(subset),'source_bootstrap95':intervals})
    write(ROOT/'metrics.json',metrics)
    table(ROOT/'stratified_metrics.csv',[r|{'source_bootstrap95':json.dumps(r['source_bootstrap95'])} for r in metrics])
    comparisons=[]
    for scope,a,b in PRIMARY:
        for label in [0,1]:
            for domain in ['overall','email','resume']:
                sids=sorted({r['source_id'] for r in rows if domain=='overall' or r['domain']==domain})
                before=[obs[s,label,scope,a] for s in sids];after=[obs[s,label,scope,b] for s in sids]
                comparisons.append({'scope':scope,'before':a,'after':b,'label':label,'domain':domain,**delta_stats(before,after)})
    primary=[r for r in comparisons if r['domain']=='overall']
    running=0.
    for rank,r in enumerate(sorted(primary,key=lambda x:x['mcnemar_exact_p'])):
        running=max(running,min(1.,(len(primary)-rank)*r['mcnemar_exact_p']))
        r['holm_p_12_primary']=running
    write(ROOT/'paired_comparisons.json',comparisons)
    # Exhaustive meaningful prespecified comparisons, including unfavorable flips.
    pairs=[('official',a,b) for a,b in combinations(['core_reference','A_complete','B_cross','C_tail'],2)]
    pairs += [('shadow','offset0','offset256')]
    pairs += [('recovery',a,b) for a,b in combinations(['native_truncated','native_partial16','native_full','matched512_truncated','matched512_partial16','matched512_full'],2)]
    pairs += [('controls','local16',b) for b in ['local192','replace_cls','replace_sep']]
    flips=[]
    for scope,a,b in pairs:
        for row in rows:
            sid,label=row['source_id'],row['label'];x=obs[sid,label,scope,a];y=obs[sid,label,scope,b]
            if x['prediction']==y['prediction']:continue
            ref=row['official']['core_reference']['prediction']
            mechanisms=['F6'];evidence='UNRESOLVED_MULTIPLE_FACTORS'
            if scope=='official':
                mechanisms += ['F3']
                if 'B_cross' in [a,b]:mechanisms+=['F1']
            elif scope=='shadow':mechanisms+=['F1','F2'];evidence='CONTROLLED_WHOLE_TOKEN_BOUNDARY_BUNDLE'
            elif scope=='recovery':mechanisms+=['F1','F3'];evidence='CONTROLLED_CONTEXT_ADDITION_WITH_LENGTH_OR_FILLER_CONFOUNDING'
            else:
                mechanisms+=['F2'] if 'replace' in b else ['F3']
                evidence='TOKEN_ID_REPLACEMENT_SAME_LENGTH_CORE_POSITION' if 'replace' in b else 'LOCAL_POSITION_AND_ADJACENCY_BUNDLE'
            if ref!=label:mechanisms+=['F5']
            # F4 only when a non-core chunk is solely responsible for a benign document FP.
            for cond in [a,b]:
                if scope=='official' and label==0:
                    doc=row['official'][cond];lo,hi=doc['core_token_range']
                    corechunks=[c for c in doc['chunks'] if c['start_token']<hi and c['end_token']>lo]
                    outside=[c for c in doc['chunks'] if not(c['start_token']<hi and c['end_token']>lo)]
                    if outside and max(c['risk_score'] for c in outside)>=.5 and max(c['risk_score'] for c in corechunks)<.5:mechanisms+=['F4']
            flips.append({k:row[k] for k in ['source_id','domain','text_type','label','variant','semantic_family']} | {
                'scope':scope,'original_condition':a,'modified_condition':b,'attack_span':x['attack_span'],
                'core_token_range':x['core_token_range'],'modified_core_token_range':y['core_token_range'],
                'modified_attack_span':y['attack_span'],'coordinate_system':x['coordinate_system'],
                'chunk_boundary':x['chunk_boundaries'],'modified_chunk_boundary':y['chunk_boundaries'],
                'original_input_token_hash':x['input_sha256'],'modified_input_token_hash':y['input_sha256'],
                'special_token_layout_original':x['special_token_layout'],'special_token_layout_modified':y['special_token_layout'],
                'original_prediction':x['prediction'],'modified_prediction':y['prediction'],
                'original_risk':x['risk_score'],'modified_risk':y['risk_score'],'classification_flip':True,
                'effect':'corrected' if y['prediction']==label else 'new_error',
                'suspected_failure_mechanism':';'.join(sorted(set(mechanisms))),
                'alternative_explanation':'Core semantics, local token index, special-token layout, carrier context and Max selection may coexist; scope-specific counterfactual is not deployed performance',
                'evidence_status':evidence,'unique_cause_proven':False})
    fields=['source_id','domain','text_type','label','variant','semantic_family','scope','original_condition','modified_condition','attack_span','core_token_range','chunk_boundary','original_input_token_hash','modified_input_token_hash','special_token_layout_original','special_token_layout_modified','original_prediction','modified_prediction','original_risk','modified_risk','classification_flip','effect','suspected_failure_mechanism','alternative_explanation','evidence_status','unique_cause_proven']
    if flips:table(ROOT/'06_case_level_failure_taxonomy.csv',flips)
    else:
        with (ROOT/'06_case_level_failure_taxonomy.csv').open('x',newline='') as f:csv.writer(f).writerow(fields)
    # Source-specific triangulation; do not infer mechanism from a p-value alone.
    triangulation=[]
    for row in rows:
        off=row['official'];label=row['label']
        a,b=off['A_complete']['prediction'],off['B_cross']['prediction']
        triangulation.append({k:row[k] for k in ['source_id','domain','text_type','label','semantic_family']} | {
            'official_A_correct_B_wrong':a==label and b!=label,
            'same_token_shadow_corrects_B':b!=label and row['shadow']['prediction']==label,
            'native_recovery_corrects_truncated':row['recovery']['native_truncated']['prediction']!=label and row['recovery']['native_full']['prediction']==label,
            'matched_recovery_corrects_truncated':row['recovery']['matched512_truncated']['prediction']!=label and row['recovery']['matched512_full']['prediction']==label,
            'core_reference_wrong':off['core_reference']['prediction']!=label,
            'triangulated':a==label and b!=label and row['shadow']['prediction']==label and row['recovery']['native_full']['prediction']==label})
    table(ROOT/'triangulation.csv',triangulation)
    pos=[r for r in triangulation if r['triangulated']]
    unique={r['source_id'] for r in pos};families={r['semantic_family'] for r in pos}
    harm={}
    for mode in ['native','matched512']:
        r=next(v for v in primary if v['scope']=='recovery' and v['before']==mode+'_truncated' and v['label']==1)
        harm[mode]={'new_attack_misses':r['new_errors'],'attack_misses_corrected':r['errors_corrected'],'error_delta_bootstrap95':r['error_delta_bootstrap95']}
    go={'official_boundary_error_variants':sum(r['official_A_correct_B_wrong'] for r in triangulation),
        'triangulated_source_count':len(unique),'triangulated_semantic_families':sorted(families),
        'triangulated_cases':pos,'recovery_attack_harm':harm,
        'quantitative_screen':len(unique)>=3 and len(families)>=2 and len(pos)>=2 and all(v['new_attack_misses']<3 for v in harm.values()),
        'causal_identification_limit':'Window bundle simultaneously changes surrounding semantics, local positions and special-token/window layout. Single fixed attack and shared quote frames cannot establish generalized algorithm effectiveness.',
        'decision':'REVIEW_REQUIRED',
        'not_stage_M3_authorization':True}
    go['decision']='GO_TO_PROPOSAL_ONLY_WITH_IDENTIFICATION_REVIEW' if go['quantitative_screen'] else 'NO_GO_ALGORITHM_DEVELOPMENT'
    write(ROOT/'go_no_go.json',go)
    # Background-Max decomposition and core-reference errors are recorded for all sources, not only flips.
    attribution=[]
    for row in rows:
        for condition,doc in row['official'].items():
            lo,hi=doc['core_token_range'];corechunks=[c['risk_score'] for c in doc['chunks'] if c['start_token']<hi and c['end_token']>lo]
            other=[c['risk_score'] for c in doc['chunks'] if not(c['start_token']<hi and c['end_token']>lo)]
            attribution.append({'source_id':row['source_id'],'label':row['label'],'condition':condition,
                'core_chunk_max':max(corechunks),'noncore_chunk_max':max(other) if other else None,
                'noncore_sole_fp':row['label']==0 and bool(other) and max(other)>=.5 and max(corechunks)<.5,
                'core_reference_wrong':row['official']['core_reference']['prediction']!=row['label']})
    table(ROOT/'max_attribution.csv',attribution)
    # Save all transition matrices (native and equal-length; both labels), plus primary stats.
    transitions={}
    for mode in ['native','matched512']:
        for end in ['partial16','full']:
            for label in [0,1]:
                matrix=[[0,0],[0,0]]
                for r in rows:
                    if r['label']==label:matrix[r['recovery'][mode+'_truncated']['prediction']][r['recovery'][mode+'_'+end]['prediction']]+=1
                transitions[f'{mode}_truncated_to_{end}_label{label}']=matrix
    write(ROOT/'transition_matrices.json',transitions)
    summary={'n_sources':40,'n_variants':80,'forward_calls':receipt['forward_calls'],'raw_run_id':receipt['run_id'],
        'raw_path':str(raw),'raw_sha256':sha(raw),'n_flip_records_all_declared_contrasts':len(flips),
        'n_unique_source_label_pairs_with_any_flip':len({(r['source_id'],r['label']) for r in flips}),
        'go_no_go':go,'primary_comparisons':primary,
        'official_overall':[m for m in metrics if m['scope']=='official' and m['domain']=='overall' and m['text_type']=='all'],
        'noncore_sole_fp_count_by_condition':{c:sum(r['noncore_sole_fp'] for r in attribution if r['condition']==c) for c in row['official']}}
    write(ROOT/'analysis_summary.json',summary)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
