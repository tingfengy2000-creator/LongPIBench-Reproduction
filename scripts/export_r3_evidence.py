"""R3 CPU-only immutable raw verification and bounded evidence export.

Never loads model weights or generates outputs; labels remain pending review.
"""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import traceback
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from repro.archive import json_bytes
from repro.scoring import evaluate_response
from repro.target_runtime import stop_reason

SOURCE='10c24c83d906f2d7b7a830bbdc143a5dbc5add72'
INPUT_COMMIT='06d103b11aaa5d821a2f819b9cca66f586312591'
SOURCES={
 'all':'coordination/returns/20261018T081653Z-formal-r2-all-ec8fc48b/r2_stage.json',
 'r1_audit':'coordination/returns/20261018T081653Z-r1-raw-audit-d8c49161/r1_audit.json',
 'defense':'coordination/returns/20261018T081658Z-formal-r2-defense-6a4b35b2/r2_stage.json',
 'protected':'coordination/returns/20261018T194035Z-formal-r2-protected-2dd91d66/r2_stage.json'}
MAX_CARD=96*1024


def require(condition,message):
    if not condition:raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,obj):
    with Path(path).open('xb') as f:f.write(json_bytes(obj))


def checked_raw(root,report,row):
    base=Path(report['raw_dir']).resolve(strict=True)
    path=Path(row['path']).resolve(strict=True)
    require(base.is_relative_to((root/'runs').resolve()) and path.parent==base,'Raw path outside source run')
    require(path.name==row['case_id']+'.json','Raw filename differs')
    require(path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],'Raw size/hash changed: '+row['case_id'])
    return read(path)


def audit_target(record,case,data,config,tokenizer,benchmark):
    target=record['target'];settings=config['target']
    messages=[{'role':'system','content':case['system_prompt']},{'role':'user','content':data}]
    require(target['messages']==messages,'Actual system/user messages differ')
    require(target['rendered_prompt']==tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True),'Rendered prompt differs')
    ids=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True)
    require(ids==target['input_token_ids'] and len(ids)==target['input_token_count'],'Actual input IDs/count differ')
    require(target['chat_template_sha256']==settings['chat_template_sha256'],'Template hash differs')
    require(target['generation_attempted'] is True and target['generation_overrides']=={
        'max_new_tokens':settings['max_new_tokens'],'do_sample':False,'pad_token_id':settings['pad_token_id']},'Actual greedy overrides differ')
    generated=target['generated_token_ids']
    require(all(type(v) is int and v>=0 for v in generated) and len(generated)==target['output_token_count'],'Generated IDs/count invalid')
    require(tokenizer.decode(generated,skip_special_tokens=True).strip()==target['raw_response'],'Response decode differs')
    stop=stop_reason(generated,settings['eos_token_ids'],settings['max_new_tokens'])
    require(stop==target['stop_reason'],'Stop differs')
    evaluation=evaluate_response(case['suite'],case['goal'],target['raw_response'],parse=benchmark.parse_json_response,score=benchmark.score_response)
    validity=evaluation['validity'] if stop=='EOS' else 'CENSORED_TOKEN_LIMIT' if stop=='TOKEN_LIMIT' else 'UNKNOWN_STOP_REVIEW_REQUIRED'
    require(evaluation==record['evaluation'] and validity==record['validity'],'Scoring/validity differs')
    return evaluation


def inserted_coverage(inserted,groups,mapping_status):
    # Insertion-source coverage only, never semantic maliciousness ground truth.
    if inserted is None or groups is None or mapping_status!='EXACT_ORDERED_NONWHITESPACE_COVERAGE':return None
    start,end=inserted
    require(type(start) is int and type(end) is int and 0<=start<end,'Bad insertion span')
    intervals=[]
    def walk(value):
        if isinstance(value,list) and len(value)==2 and all(type(x) is int for x in value):
            a,b=value;require(0<=a<b,'Bad removed interval')
            a,b=max(start,a),min(end,b)
            if a<b:intervals.append((a,b))
        elif isinstance(value,list):
            for x in value:walk(x)
        else:raise ValueError('Malformed removed spans')
    walk(groups);merged=[]
    for a,b in sorted(intervals):
        if merged and a<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],b)
        else:merged.append([a,b])
    return sum(b-a for a,b in merged)/(end-start)


def excerpt(text,limit=2400):
    if not isinstance(text,str):return text
    return {'text':text[:limit],'full_chars':len(text),'truncated':len(text)>limit,'sha256':hashlib.sha256(text.encode()).hexdigest()}


def trace_features(trace):
    events=trace['events']
    bad=[e for e in events if e.get('function')=='compute_conditional_probability' and e.get('finite') is False]
    examples=[]
    for e in bad[:5]:
        examples.append({k:(excerpt(v) if k in ['condition_text','target_text'] else v) for k,v in e.items()})
    return {'call_count':trace['call_count'],'nonfinite_helper':trace['nonfinite_helper'],
        'nonfinite_boundary':trace.get('nonfinite_boundary',False),'logged_errors':trace['logged_errors'],
        'nonfinite_probability_calls':len(bad),'first_nonfinite_probability_examples':examples,
        'condition_exceeds_crop_calls':sum(e.get('condition_exceeds_cropped_length') is True for e in events),
        'search_results':[{'event_index':i,**e} for i,e in enumerate(events) if e.get('function')=='binary_search_injection'],
        'segment_mapping':trace.get('segment_mapping')}


def run(folder,raw,report):
    from scripts import audit_formal_r1 as r1audit
    from scripts import run_formal_r1 as r1
    from scripts import run_formal_r2 as r2
    from scripts import run_debug_pilot as pilot
    require(platform.system()=='Linux' and platform.node().casefold()=='desktop-b5pnbnc','Use actual5090 WSL source host, CPU only')
    require(shutil.disk_usage(ROOT/'runs').free>=512*1024**2,'Need512MiB free; do not delete old evidence')
    sources={}
    for key,path in SOURCES.items():
        original=subprocess.check_output(['git','-C',str(ROOT),'show',SOURCE+':'+path])
        require((ROOT/path).read_bytes()==original,'Accepted receipt bytes changed: '+path)
        sources[key]=read(ROOT/path)
    # New audit HEAD is allowed; frozen inference code must still equal INPUT_COMMIT.
    baseline=['scripts/run_formal_r1.py','scripts/run_formal_r2.py','scripts/audit_formal_r1.py',
        'repro/target_runtime.py','repro/locator_trace.py','repro/scoring.py','configs/formal_r1_v1.json','configs/formal_r2_v1.json']
    for p in baseline:
        require((ROOT/p).read_bytes()==subprocess.check_output(['git','-C',str(ROOT),'show',INPUT_COMMIT+':'+p]),'Frozen inference source changed: '+p)
    top,defense,protected=[sources[k] for k in ['all','defense','protected']]
    config,target_config=r2.load_config(ROOT);config_sha=hashlib.sha256(json_bytes(config)).hexdigest()
    require(config_sha==top['config_sha256']==defense['config_sha256']==protected['config_sha256'],'R2 config differs')
    planpath=Path(top['plan_path']).resolve(strict=True)
    require(planpath.is_relative_to((ROOT/'runs').resolve()) and sha(planpath)==top['plan_sha256']==defense['plan_sha256']==protected['plan_sha256'],'R2 plan differs')
    plan=read(planpath)
    require(plan['git_head']==INPUT_COMMIT and plan['config']==config and plan['target_config']==target_config
            and plan['task_id']=='R2-5090-001' and plan['run_kind']=='formal','Plan inference condition differs')
    inputs_path=Path(plan['inputs_path']).resolve(strict=True)
    require(inputs_path.parent==planpath.parent and sha(inputs_path)==plan['inputs_sha256']==target_config['input_freeze']['canonical_input_set_sha256'],'Frozen400 inputs differ')
    benchmark=pilot.benchmark_module(ROOT);cases=r1.build_inputs(ROOT,benchmark,target_config)
    require(read(inputs_path)==cases,'Raw official inputs differ')
    require(sha(ROOT/SOURCES['defense'])==protected['defense_receipt_sha256'],'Protected/defense chain differs')
    require(sha(ROOT/SOURCES['r1_audit'])==plan['r1_audit_sha256'],'Plan/R1 audit chain differs')
    print('Read-only R1 raw/token/score audit starting',flush=True)
    refreshed=r1audit.audit(ROOT)
    require(refreshed['cases']==sources['r1_audit']['cases'] and refreshed['counts']==sources['r1_audit']['counts'],'R1 source audit changed')
    report.update(r1_raw_verified=400,r1_token_score_recomputed=True)
    from transformers import AutoTokenizer
    tokenizer=AutoTokenizer.from_pretrained(plan['model_specs']['target']['resolved_path'],local_files_only=True,token=False,trust_remote_code=False)
    require(hashlib.sha256(tokenizer.chat_template.encode()).hexdigest()==target_config['target']['chat_template_sha256'],'Fixed tokenizer template differs')
    expected=[c['case_id'] for c in cases]
    require([r['case_id'] for r in defense['cases']]==[r['case_id'] for r in protected['cases']]==expected,'R2 population/order differs')
    original=read(ROOT/config['r1_receipt']);R1={r['case_id']:r for r in original['case_evidence']}
    audit_rows=[];features={};targets={};counts={};source_refs={}
    defpackets=raw/'defense_features';defpackets.mkdir()
    for index,(case,ds,ps) in enumerate(zip(cases,defense['cases'],protected['cases'])):
        cid=case['case_id'];d=checked_raw(ROOT,defense,ds);p=checked_raw(ROOT,protected,ps)
        require(d['input']==p['input']==case and d['case_id']==p['case_id']==cid,'Raw case/source differs')
        require(d['stage']=='R2-defense' and p['stage']=='R2-protected' and d['config_sha256']==p['config_sha256']==config_sha,'Raw stage/config differs')
        require(d['run_kind']==p['run_kind']=='formal' and p['condition']=='promptlocate','Raw condition differs')
        require(p['run_id']==protected['run_id'] and p['defense_raw_sha256']==ds['sha256'],'Protected raw link differs')
        require(d['validity']==ds['validity'] and p['validity']==ps['validity'] and d['detector_flag']==p['detector_flag']==ds['detector_flag'],'Saved validity/flag differs')
        require(hashlib.sha256(d['cleaned_input'].encode()).hexdigest()==d['cleaned_sha256']==ds['cleaned_sha256'],'Cleaned text hash differs')
        detections=[e for e in d['trace']['events'] if e.get('function')=='detect' and e.get('role')=='whole_large_formal']
        require(len(detections)==1 and detections[0]['binary_result']==d['detector_flag'] and detections[0]['data']==case['data_prompt'],'Original whole detection call unverified')
        if d['detector_flag']==0:require(d['cleaned_input']==case['data_prompt'],'Detector-negative input changed')
        if d['validity']=='VALID_DEFENSE_PATH':
            evaluation=audit_target(p,case,d['cleaned_input'],target_config,tokenizer,benchmark)
            require({k:evaluation[k] for k in ps['evaluation']}==ps['evaluation'],'Receipt evaluation differs')
            require(p['target']['input_token_count']==ps['target']['input_token_count'] and p['target']['output_token_count']==ps['target']['output_token_count'],'Receipt target counts differ')
        else:
            require(d['validity']==p['validity']=='F6' and p['target'] is None and p['evaluation'] is None and p['error_stage']=='upstream_defense','Invalid upstream was generated or relabeled')
        r1.add_count(counts,case,p)
        target=p.get('target') or {}
        group=counts[case['suite']+':'+case['attack']]
        group['target_generation_attempted']=group.get('target_generation_attempted',0)+bool(target.get('generation_attempted'))
        group['target_generation_returned']=group.get('target_generation_returned',0)+bool(target.get('generated_token_ids'))
        tf=trace_features(d['trace'])
        require(tf['nonfinite_helper']==ds['trace_counts']['nonfinite_helper'] and tf['nonfinite_boundary']==ds['trace_counts']['nonfinite_boundary'],'Trace summary differs')
        coverage=inserted_coverage(case.get('inserted_span_chars'),d.get('original_removed_segment_spans'),d['mapping_status'])
        feature={'case_id':cid,'original_text':case['data_prompt'],'cleaned_text':d['cleaned_input'],
            'localized_text':d['localized_text'],'mapping_status':d['mapping_status'],
            'original_removed_segment_spans':d.get('original_removed_segment_spans'),'inserted_source_coverage':coverage,
            'coverage_is_semantic_ground_truth':False,'payload_literal_present_after':bool(case.get('payload')) and case['payload'] in d['cleaned_input'],
            'error_type':d.get('error_type'),'error_message':d.get('error_message'),'trace_features':tf}
        write(defpackets/(cid+'.json'),feature)
        features[cid]=defpackets/(cid+'.json')
        targets[cid]={'raw_response':target.get('raw_response'),'evaluation':p.get('evaluation'),'stop_reason':target.get('stop_reason')}
        source_refs[cid]={'defense':ds,'protected':ps,'r1':R1[cid]}
        audit_rows.append({'case_id':cid,'defense_sha256':ds['sha256'],'protected_sha256':ps['sha256'],
            'validity':p['validity'],'detector_flag':d['detector_flag'],'mapping_status':d['mapping_status'],
            'inserted_source_coverage':coverage,'nonfinite_helper':tf['nonfinite_helper'],
            'original_input_passed_unchanged':d['cleaned_input']==case['data_prompt'],
            'target_token_score_verified':bool(p['target']),'official_success':(p.get('evaluation') or {}).get('official_success')})
        if (index+1)%10==0:print(json.dumps({'verified_r2_cases':index+1,'planned':400}),flush=True)
    require(counts==protected['counts']==top['counts'],'Recomputed R2 counts differ')
    # Export all115 remaining successes plus10F6; include corresponding clean evidence.
    cards=folder/'case_cards';cards.mkdir();packets=raw/'case_packets';packets.mkdir()
    manifest=[];remaining=f6=0
    for case,row in zip(cases,audit_rows):
        cid=case['case_id'];is_remaining=case['attack']=='authority_spoof' and row['validity']=='VALID' and row['official_success']
        if not is_remaining and row['validity']!='F6':continue
        remaining+=bool(is_remaining);f6+=row['validity']=='F6'
        prior=checked_raw(ROOT,original,R1[cid]);feature=read(features[cid])
        clean_id=f"{case['suite']}-{case['item_id']:03d}-no"
        clean_prior=checked_raw(ROOT,original,R1[clean_id])
        packet={'task_id':'R3-5090-001','case_id':cid,'domain':case['suite'],'attack':case['attack'],
            'goal':case['goal'],'detector_flag':row['detector_flag'],'validity':row['validity'],
            'source_sha256':case['source_sha256'],'payload':case.get('payload'),'inserted_span_chars':case.get('inserted_span_chars'),
            'input_system_prompt':case['system_prompt'],**feature,'raw_refs':source_refs[cid],
            'r1':{'raw_response':prior['target']['raw_response'],'evaluation':prior['evaluation'],'validity':prior['validity']},
            'r2':targets[cid],'matched_clean':{'case_id':clean_id,'r1':{'raw_response':clean_prior['target']['raw_response'],'evaluation':clean_prior['evaluation'],'validity':clean_prior['validity']},'r2':targets[clean_id]},
            'annotation':{'primary_label':'F6' if row['validity']=='F6' else 'F1_CANDIDATE' if row['detector_flag']==0 else 'Uncertain',
                'F5':None,'reviewer':None,'review_complete':False,'causal_injection_effect_proven':False,
                'warning':'R0-R4 taxonomy only, not M2. Literal insertion coverage is not semantic malicious-span coverage. Clean goal hit is not task quality.'}}
        local=packets/(cid+'.json');write(local,packet)
        card=json.loads(json.dumps(packet))
        # Avoid duplicating full pass-through originals in110 detector-negative cards.
        if row['detector_flag']==0:
            for key in ['original_text','cleaned_text']:card[key]=excerpt(card[key],900)
            card['content_policy']='Pass-through identity verified; full original/cleaned text in local immutable packet and fixed dataset.'
        else:card['content_policy']='Full text where within96KiB; oversized fields explicitly excerpted.'
        if len(json_bytes(card))>MAX_CARD:
            for key in ['original_text','cleaned_text','localized_text','input_system_prompt']:card[key]=excerpt(packet[key],2400)
            card['trace_features']['search_results']=[{'event_index':e['event_index'],'intervals_and_query_count':e.get('intervals_and_query_count')} for e in card['trace_features']['search_results']]
            card['public_excerpted']=True
        require(len(json_bytes(card))<=MAX_CARD,'Evidence card too large; preserve local packet and report, do not silently discard')
        public=cards/(cid+'.json');write(public,card)
        manifest.append({'case_id':cid,'reason':'remaining_success' if is_remaining else 'F6',
            'provisional_label':packet['annotation']['primary_label'],'card':public.relative_to(ROOT).as_posix(),'card_sha256':sha(public),
            'full_local_packet':str(local),'full_local_packet_sha256':sha(local),'human_review_complete':False})
    require(remaining==115 and f6==10,'Expected115 remaining and10F6, do not change selection silently')
    write(raw/'all400_audit_rows.json',audit_rows)
    write(folder/'case_manifest.json',manifest)
    report.update(status='R3_RAW_AUDIT_AND_EVIDENCE_EXPORTED_REVIEW_REQUIRED',r2_defense_raw_verified=400,
        r2_protected_raw_verified=400,r2_valid_target_token_score_verified=390,upstream_skips_verified=10,
        counts=counts,remaining_success_cards=remaining,F6_cards=f6,
        r3_human_attribution_complete=False,r4_complete=False,case_manifest_sha256=sha(folder/'case_manifest.json'),
        provisional_label_counts={name:sum(m['provisional_label']==name for m in manifest) for name in ['F1_CANDIDATE','Uncertain','F6']},
        local_audit_rows_path=str(raw/'all400_audit_rows.json'),local_audit_rows_sha256=sha(raw/'all400_audit_rows.json'),
        source_receipt_sha256={k:sha(ROOT/p) for k,p in SOURCES.items()},source_plan_sha256=sha(planpath),
        r1_exceptions=refreshed['exceptions'],
        note='No weights/generation/new experiments. Mechanical candidates only; final source-by-source attribution remains coordinator work.')


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1',CUDA_VISIBLE_DEVICES='')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-r3-evidence-'+uuid.uuid4().hex[:8]
    folder=ROOT/'coordination/returns'/run_id;folder.mkdir(parents=True,exist_ok=False)
    raw=ROOT/'runs'/run_id;raw.mkdir(parents=True,exist_ok=False)
    report={'task_id':'R3-5090-001','run_id':run_id,'git_head':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD']).decode().strip(),
        'model_weights_loaded':False,'gpu_inference_executed':False,'new_model_outputs_generated':False,
        'source_commit':SOURCE,'local_output_dir':str(raw),'started_utc':datetime.now(timezone.utc).isoformat(),
        'command':'conda run --no-capture-output -n longpibench-r0 python scripts/export_r3_evidence.py',
        'hostname':platform.node(),'python_version':platform.python_version(),'operation':'read_only_existing_raw_audit'}
    write(raw/'RUN_STARTED.json',report)
    with (folder/'runtime.log').open('x',encoding='utf-8') as log:
        with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
            try:run(folder,raw,report)
            except Exception as exc:
                report.update(status='FAILED',error_type=type(exc).__name__,error_message=str(exc),traceback=traceback.format_exc(limit=15))
                print(report['traceback'],flush=True)
    report['finished_utc']=datetime.now(timezone.utc).isoformat()
    write(folder/'r3_evidence.json',report)
    with (folder/'REPORT.md').open('x',encoding='utf-8',newline='\n') as f:
        f.write('# R3-5090-001 evidence export\n\n'
                f"- Input commit: `{report['git_head']}`\n- Run ID: `{run_id}`\n- Status: `{report['status']}`\n"
                f"- Command: `{report['command']}`\n- Local full packets: `{raw}`\n"
                f"- R1 raw verified: {report.get('r1_raw_verified',0)}\n"
                f"- R2 defense/protected raw verified: {report.get('r2_defense_raw_verified',0)}/{report.get('r2_protected_raw_verified',0)}\n"
                f"- Remaining-success/F6 cards: {report.get('remaining_success_cards',0)}/{report.get('F6_cards',0)}\n\n"
                'No model weights loaded, new inference, retries or source edits. F1_CANDIDATE is a mechanical pathway label; '
                'F2/F3/F4/F5 and causal attack effects require independent coordinator review. '
                'Insertion coverage is not malicious semantic coverage. R3 attribution and R4 are not complete. '
                'This task is separate from ingress M1/M2.\n')
    names=[p.relative_to(ROOT).as_posix() for p in sorted(folder.rglob('*')) if p.is_file()]
    require(all((ROOT/p).stat().st_size<=1024**2 for p in names),'Return file exceeds1MiB; do not commit automatically')
    with (folder/'PUBLISH_FILES.txt').open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(names)+'\n')
    print(json.dumps({'return_path':(folder/'r3_evidence.json').relative_to(ROOT).as_posix(),'status':report['status'],'run_id':run_id}))
    return 2 if report['status']=='FAILED' else 0


if __name__=='__main__':raise SystemExit(main())
