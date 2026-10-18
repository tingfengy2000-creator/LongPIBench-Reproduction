"""Replay sealed scores for explanatory domain/length/position diagnostics."""
from collections import defaultdict
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

import offline as o

ROOT=Path(__file__).resolve().parent


def write_json(name,value):
    with (ROOT/name).open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)


def write_csv(name,rows):
    with (ROOT/name).open('x',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def describe(values):
    if not values:return {'n':0,'min':None,'q25':None,'median':None,'q75':None,'max':None,'mean':None}
    quantiles=np.quantile(values,[0,.25,.5,.75,1]).tolist()
    return dict(n=len(values),min=quantiles[0],q25=quantiles[1],median=quantiles[2],q75=quantiles[3],max=quantiles[4],mean=float(np.mean(values)))


def analyze_model(alias):
    rows=o.load(alias);clean,fitted=o.fit(rows)
    legacy=json.loads((o.PILOT/'validation_v2/results'/alias/'pilot_results.json').read_text(encoding='utf-8'))
    assert fitted['global_max']['pooled']['threshold']==legacy['methods']['max']['calibration_threshold']
    assert fitted['length_max']['pooled']['threshold']==legacy['methods']['length_calibrated_max']['calibration_threshold']
    fit_record={'fitting_split':'calibration','fitting_label':0,'historical_scores_unchanged':True,
        'parameters':fitted,'all_fit_sample_ids':[r['sample_id'] for r in clean]}
    decisions=[];matrix=[];domain_curves={};all_scores={}
    for row in rows:
        record={k:row[k] for k in ['sample_id','source_document_id','domain','label','split','token_count','chunk_count']}
        record.update(detector=alias)
        for method in o.METHODS:
            value=o.score(row,method,clean)
            cut=o.cutoff(fitted,method,row['domain'])
            record[method+'_score']=value;record[method+'_threshold']=cut;record[method+'_prediction']=int(value>cut)
        decisions.append(record)
    for split in ['calibration','test']:
        for domain in ['overall','email','resume']:
            selected=[r for r in decisions if r['split']==split and (domain=='overall' or r['domain']==domain)]
            for method in o.METHODS:
                metrics=o.confusion([r['label'] for r in selected],[r[method+'_prediction'] for r in selected])
                matrix.append(dict(detector=alias,split=split,domain=domain,method=method,**metrics))
                if split=='test' and method in ['global_max','length_max']:
                    expected=legacy['methods']['max' if method=='global_max' else 'length_calibrated_max']
                    assert metrics==(expected['test_overall'] if domain=='overall' else expected['test_by_domain'][domain])
    held=[r for r in decisions if r['split']=='test']
    for domain in ['email','resume']:
        selected=[r for r in held if r['domain']==domain]
        labels=[r['label'] for r in selected]
        curves={}
        for method in o.METHODS:
            values=[r[method+'_score'] for r in selected]
            curves[method]=o.curves(labels,values)
            o.independently_check_curves(labels,values,curves[method])
        assert curves['global_max']==curves['domain_max'], 'Domain thresholds cannot alter within-domain raw-Max rankings'
        interval=o.bootstrap_delta(labels,[r['domain_max_score'] for r in selected],[r['domain_length_max_score'] for r in selected])
        domain_curves[domain]={'curves':curves,'domain_length_minus_domain_fixed_calibration_bootstrap':interval}
    explanation={}
    for domain in ['overall','email','resume']:
        selected=[r for r in held if domain=='overall' or r['domain']==domain]
        attacks=[r for r in selected if r['label']==1]
        gains={m:{r['sample_id'] for r in attacks if r[m+'_prediction'] and not r['global_max_prediction']} for m in o.METHODS}
        tp={m:sum(r[m+'_prediction'] for r in attacks) for m in o.METHODS}
        l_gains=gains['length_max'];shared=l_gains&gains['domain_max']
        net_l=tp['length_max']-tp['global_max'];net_d=tp['domain_max']-tp['global_max']
        explanation[domain]={'n':len(selected),'domain_vs_length_decision_agreement':sum(r['domain_max_prediction']==r['length_max_prediction'] for r in selected)/len(selected),
            'length_added_tp_vs_global':len(l_gains),'domain_added_tp_vs_global':len(gains['domain_max']),
            'shared_added_tp':len(shared),'length_added_tp_also_found_by_domain_fraction':len(shared)/len(l_gains) if l_gains else None,
            'net_tp_gain_length_vs_global':net_l,'net_tp_gain_domain_vs_global':net_d,
            'net_gain_ratio_domain_over_length_descriptive_not_causal':net_d/net_l if net_l>0 else None,
            'length_only_added_tp_sample_ids':sorted(l_gains-gains['domain_max']),
            'shared_added_tp_sample_ids':sorted(shared),
            'domain_length_vs_domain_prediction_changes':sum(r['domain_length_max_prediction']!=r['domain_max_prediction'] for r in selected)}
    association={}
    for domain in ['email','resume']:
        benign=[r for r in rows if r['split']=='test' and r['label']==0 and r['domain']==domain]
        association[domain]={'n':len(benign),'tokens_vs_max':o.association([r['token_count'] for r in benign],[r['maximum'] for r in benign]),
            'chunks_vs_max':o.association([r['n_chunks'] for r in benign],[r['maximum'] for r in benign]),
            'tokens_within_exact_chunk_count':o.blocked_token_association(benign),
            'per_chunk_count':{str(n):{'n':len(g), 'token_score':o.association([r['token_count'] for r in g],[r['maximum'] for r in g]) if len(g)>=3 else {'rho':None,'p':None,'n':len(g),'reason':'fewer than 3 sources'}}
                for n in sorted({r['n_chunks'] for r in benign}) for g in [[r for r in benign if r['n_chunks']==n]]}}
    return rows,decisions,matrix,{'fitting':fit_record,'domain_curves':domain_curves,'domain_explanation':explanation,'within_domain_associations':association}


def chunk_analysis():
    with (ROOT/'chunk_features.csv').open(encoding='utf-8') as stream:features=list(csv.DictReader(stream))
    for r in features:
        for key in ['label','doc_tokens','chunk_count','chunk_index','chunk_tokens','starts_cls','starts_bos','ends_sep','ends_eos','starts_special','ends_special','keyword_count']:
            r[key]=int(r[key])
        for key in ['score','relative_position','digit_fraction','punctuation_fraction']:r[key]=float(r[key])
    expected=json.loads((ROOT/'feature_receipt.json').read_text())
    assert o.sha(ROOT/'chunk_features.csv')==expected['chunk_features_sha256'] and len(features)==2900
    strata=[]
    for alias in o.ALIASES:
        for domain in ['email','resume']:
            for split in ['calibration','test']:
                for label in [0,1]:
                    base=[r for r in features if r['detector']==alias and r['domain']==domain and r['split']==split and r['label']==label]
                    for role in ['single','first','interior','tail']:
                        group=[r for r in base if r['position_role']==role]
                        if group:
                            strata.append(dict(detector=alias,domain=domain,split=split,label=label,position_role=role,
                                n_chunks=len(group),n_source_documents=len({r['source_document_id'] for r in group}),
                                mean_score=float(np.mean([r['score'] for r in group])),median_score=float(np.median([r['score'] for r in group])),
                                default_chunk_positive=sum(r['score']>=.5 for r in group),median_chunk_tokens=float(np.median([r['chunk_tokens'] for r in group])),
                                starts_special=sum(r['starts_special'] for r in group),ends_special=sum(r['ends_special'] for r in group),
                                keyword_present_chunks=sum(r['keyword_count']>0 for r in group)))
    tail_cases=[];tail_summary={}
    for alias in o.ALIASES:
        subset=[r for r in features if r['detector']==alias and r['domain']=='resume' and r['split']=='test' and r['label']==0]
        bydoc=defaultdict(list)
        for row in subset:bydoc[row['sample_id']].append(row)
        pairs=[]
        for name,chunks in bydoc.items():
            if len(chunks)<2:continue
            first=min(chunks,key=lambda r:r['chunk_index']);tail=max(chunks,key=lambda r:r['chunk_index'])
            difference=tail['score']-first['score'];pairs.append(difference)
            tail_cases.append(dict(detector=alias,sample_id=name,doc_tokens=tail['doc_tokens'],chunk_count=len(chunks),
                first_tokens=first['chunk_tokens'],tail_tokens=tail['chunk_tokens'],first_score=first['score'],tail_score=tail['score'],tail_minus_first=difference,
                tail_is_max=int(tail['score']==max(c['score'] for c in chunks)),
                tail_default_positive=int(tail['score']>=.5),first_starts_special=first['starts_special'],tail_starts_special=tail['starts_special'],
                tail_ends_special=tail['ends_special'],tail_keyword_count=tail['keyword_count'],tail_keyword_types=tail['keyword_types'],
                tail_input_token_sha256=tail['input_token_sha256']))
        nonzero=[d for d in pairs if d!=0]
        tails=[r for r in subset if r['position_role']=='tail']
        tail_summary[alias]={'n_sources':len(bydoc),'multichunk_sources':len(tails),'tail_minus_first':describe(pairs),
            'positive_tail_minus_first':sum(d>0 for d in pairs),
            'paired_sign_p_exploratory':float(binomtest(sum(d>0 for d in nonzero),len(nonzero),.5).pvalue) if nonzero else None,
            'tail_length_score_association':o.association([r['chunk_tokens'] for r in tails],[r['score'] for r in tails]) if len(tails)>=3 else None,
            'tail_length_512_overlap_n':sum(r['chunk_tokens']==512 for r in tails),
            'tail_lengths':describe([r['chunk_tokens'] for r in tails]),
            'tails_without_start_special':sum(not r['starts_special'] for r in tails),
            'tails_with_end_special':sum(r['ends_special'] for r in tails),
            'tail_keyword_present_n':sum(r['keyword_count']>0 for r in tails),
            'keyword_present_scores':describe([r['score'] for r in tails if r['keyword_count']>0]),
            'keyword_absent_scores':describe([r['score'] for r in tails if r['keyword_count']==0])}
    duplicates={}
    for alias in o.ALIASES:
        buckets=defaultdict(list)
        for row in features:
            if row['detector']==alias:buckets[row['input_token_sha256']].append(row)
        repeated=[g for g in buckets.values() if len(g)>1]
        crossing=[g for g in repeated if len({r['position_role'] for r in g})>1]
        spread=max([max(r['score'] for r in g)-min(r['score'] for r in g) for g in repeated] or [0.])
        duplicates[alias]={'repeated_token_hash_groups':len(repeated),'same_tokens_across_position_roles_groups':len(crossing),
            'max_recorded_score_spread_for_identical_input_ids':spread,
            'identical_tokens_equal_scores_within_2e_6':spread<=2e-6,
            'cross_role_examples':[[{k:r[k] for k in ['sample_id','chunk_index','position_role','score']} for r in g] for g in crossing[:5]]}
    return strata,tail_cases,{'resume_benign_historical_holdout':tail_summary,'identical_input_token_audit':duplicates,
        'causal_identification':'UNRESOLVED. No randomized content/length/position intervention, no same-length tail/first overlap in many strata. Local model does not receive document absolute position.'}


def controls_analysis():
    rows=[json.loads(x) for x in (ROOT/'controls_observations.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows)==32
    for row in rows:
        logits=np.asarray(row['chunks'][0]['logits']);p=np.exp(logits-logits.max());p/=p.sum()
        assert np.allclose(p,row['chunks'][0]['softmax'],atol=2e-7,rtol=2e-6)
        assert row['chunk_count']==1 and row['chunk_scores'][0]==row['chunks'][0]['softmax'][1]
    counts=o.confusion([r['label'] for r in rows],[r['official_prediction'] for r in rows])
    return {'intended_mapping_status':'ORIGINAL_AUTHOR_DEMO_LABEL_0_BENIGN_LABEL_1_PROMPT_INJECTION',
        'source':'https://huggingface.co/spaces/fmops/prompt-injection-classifier/blob/ef784e4cadfe184f02683a87a6ad19f565fda9b4/app.py',
        'controls_n':32,'controls_counts':counts,
        'author_examples':[{k:r[k] for k in ['control_id','text','label','official_prediction','chunk_scores']} for r in rows if r['kind']=='author-space'],
        'historical_label_mapping':'UNCHANGED; original LongPIBench mapping agrees with author intended mapping',
        'limitations':'Small authored orientation controls do not estimate generalization or recover training-label provenance; original config itself has no semantic id2label. High false positives remain behavior to audit, not reason to flip labels.'}


def main():
    sealed=o.verify_seal()
    if (ROOT/'audit_results.json').exists():raise FileExistsError('Refuse to overwrite diagnostic results')
    results={};decisions=[];metrics=[]
    for alias in o.ALIASES:
        _,d,m,result=analyze_model(alias)
        decisions+=d;metrics+=m;results[alias]=result
        print(json.dumps({'detector':alias,'legacy_global_and_length_replay':'EXACT','domain_explanation':result['domain_explanation']['overall']}),flush=True)
    strata,tails,positions=chunk_analysis()
    write_csv('document_decisions.csv',decisions)
    write_csv('stratified_comparisons.csv',metrics)
    write_csv('chunk_position_strata.csv',strata)
    write_csv('resume_tail_cases.csv',tails)
    write_json('calibration_parameters.json',{a:r['fitting'] for a,r in results.items()})
    write_json('position_content_audit.json',positions)
    write_json('distilbert_label_audit.json',controls_analysis())
    write_json('audit_results.json',{'status':'EXPLORATORY_CONFOUNDING_REPLAY_AUDITED','formal_paper_experiment':False,
        'created_utc':datetime.now(timezone.utc).isoformat(),'frozen_existing_files_unchanged':sealed,
        'n_historical_scores':960,'n_sources':160,'fit_clean_sources':80,
        'historical_holdout_sources':80,'source_grouping_preserved':True,'historical_results_modified':False,
        'calibration_policy':'Only original calibration benign sources; 28 fixed neighbors; original pooled G/L cutoffs reproduced exactly',
        'models':results,'historical_holdout_use':'Explanation only, no new independent-test claim',
        'bootstrap':'2000 paired within-domain source resamples stratified by label; fixed fits; no calibration uncertainty or multiplicity guarantee',
        'position_causality':'UNRESOLVED; document-level absolute index not an input to local chunk model; content/length/boundary tokens confounded'})
    assert o.verify_seal()==sealed
    print('All sealed existing files unchanged; no detector module or R2 file modified')


if __name__=='__main__':main()
