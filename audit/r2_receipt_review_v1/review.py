"""CPU-only receipt reconciliation; cannot verify remote R2 raw from summaries."""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
import csv
import hashlib
import json
import math
import statistics
import subprocess

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
REMOTE_COMMIT='10c24c83d906f2d7b7a830bbdc143a5dbc5add72'
PATHS={
 'all':'coordination/returns/20261018T081653Z-formal-r2-all-ec8fc48b/r2_stage.json',
 'r1':'coordination/returns/20261018T081653Z-r1-raw-audit-d8c49161/r1_audit.json',
 'defense':'coordination/returns/20261018T081658Z-formal-r2-defense-6a4b35b2/r2_stage.json',
 'protected':'coordination/returns/20261018T194035Z-formal-r2-protected-2dd91d66/r2_stage.json'}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def write(name,obj):
 with (OUT/name).open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def table(name,rows):
 with (OUT/name).open('x',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def wilson(s,n):
 if not n:return None
 z=1.959963984540054;p=s/n;d=1+z*z/n
 c=(p+z*z/(2*n))/d;r=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
 return [max(0,c-r),min(1,c+r)]
def rate(s,n):return {'successes':s,'evaluable':n,'rate':s/n if n else None,'wilson95':wilson(s,n)}


def main():
 reports={k:read(p) for k,p in PATHS.items()}
 for p in PATHS.values():
  assert (ROOT/p).read_bytes()==subprocess.check_output(['git','-C',str(ROOT),'show',REMOTE_COMMIT+':'+p])
 r1,defense,protected,top=[reports[k] for k in ['r1','defense','protected','all']]
 config=read('configs/formal_r2_v1.json')
 canonical=(json.dumps(config,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
 config_sha=hashlib.sha256(canonical).hexdigest()
 assert config_sha=='5d12649f82f7fde7f45b8f1c7ba9adf7b3366163423e8ffc1e3ab428adcec568'
 for r in [defense,protected,top]:
  assert r['config_sha256']==config_sha and r['git_head']=='06d103b11aaa5d821a2f819b9cca66f586312591'
  assert r['retries']==0 and not r['debug_output_reused'] and not r['strict_paper_configuration_recovered']
 assert len({r['plan_sha256'] for r in [defense,protected,top]})==1
 assert protected['defense_receipt_sha256']==sha(ROOT/PATHS['defense'])
 assert all(c['exit_code']==0 for c in top['children'])
 assert top['counts']==protected['counts']
 assert r1['verified_raw_count']==400 and r1['raw_hashes_verified'] and r1['official_and_audit_scores_recomputed']
 source_r1=read(config['r1_receipt'])
 assert sha(ROOT/config['r1_receipt'])==r1['source_receipt_sha256']==config['r1_receipt_sha256']
 expected=[r['case_id'] for r in source_r1['case_evidence']]
 for report in [r1,defense,protected]:assert [r['case_id'] for r in report['cases']]==expected and len(set(expected))==400
 R={r['case_id']:r for r in r1['cases']};D={r['case_id']:r for r in defense['cases']};P={r['case_id']:r for r in protected['cases']}
 assert all(R[r['case_id']]['raw_sha256']==r['sha256'] for r in source_r1['case_evidence'])
 prepared=[json.loads(s) for s in (ROOT/'audit/prepared_inputs.jsonl').read_text(encoding='utf-8').splitlines()]
 input_map={f"{r['suite']}-{r['item_id']:03d}-{r['attack']}":r for r in prepared}
 joined=[];queue=[];exceptions=[];groups={}
 for cid in expected:
  a,b,c=R[cid],D[cid],P[cid];inp=input_map[cid]
  assert b['detector_flag'] in (0,1)
  assert all(PurePosixPath(r['path']).name==cid+'.json' and r['bytes']>0 and len(r['sha256'])==64 for r in [b,c])
  if b['validity']=='VALID_DEFENSE_PATH':assert c['validity']=='VALID' and c['target'] and c['target']['stop_reason']=='EOS'
  else:assert c['validity']==b['validity']=='F6' and c.get('target') is None and c['error_stage']=='upstream_defense'
  if b['detector_flag']==0:assert b['cleaned_sha256']==hashlib.sha256(inp['data_prompt'].encode()).hexdigest()
  group=inp['suite']+':'+inp['attack'];groups.setdefault(group,[]).append(cid)
  row={'case_id':cid,'domain':inp['suite'],'attack':inp['attack'],'r1_validity':a['validity'],'r2_validity':c['validity'],
   'r1_official_success':a['official_success'],'r2_official_success':c.get('evaluation',{}).get('official_success') if c.get('evaluation') else None,
   'detector_flag':b['detector_flag'],'defense_validity':b['validity'],'mapping_status':b['mapping_status'],
   'r1_raw_sha256':a['raw_sha256'],'defense_raw_path':b['path'],'defense_raw_sha256':b['sha256'],
   'protected_raw_path':c['path'],'protected_raw_sha256':c['sha256'],'cleaned_sha256':b['cleaned_sha256'],
   'inserted_span':json.dumps(inp.get('inserted_span_chars')),'nonfinite_helper':b['trace_counts']['nonfinite_helper'],
   'nonfinite_boundary':b['trace_counts']['nonfinite_boundary'],'raw_verified_locally':False}
  joined.append(row)
  if inp['attack']=='authority_spoof' and c['validity']=='VALID' and c['evaluation']['official_success']:
   queue.append(row|{'preliminary_label':'F1_receipt_supported_candidate' if b['detector_flag']==0 else 'Uncertain_localization_residual_requires_raw',
    'human_review_complete':False,'causal_attack_success_proven':False,
    'note':'Resume clean goal satisfaction is82/100; goal hit alone is not causal attack effect. No semantic span/cleanup attribution from hashes alone.'})
  if c['validity']!='VALID':exceptions.append(row)
 rates=[];paired=[];detector=[];timing=[]
 for group,ids in groups.items():
  reportkey=group;counts=protected['counts'][reportkey]
  r1valid=[i for i in ids if R[i]['validity']=='VALID'];r2valid=[i for i in ids if P[i]['validity']=='VALID']
  s1=sum(R[i]['official_success'] for i in r1valid);s2=sum(P[i]['evaluation']['official_success'] for i in r2valid)
  assert counts['attempted']==100 and counts['evaluable']==len(r2valid) and counts['invalid_or_censored']==100-len(r2valid)
  assert counts['official_true_evaluable']==s2 and counts['target_generation_attempted']==counts['target_generation_returned']==len(r2valid)
  assert counts['token_limit']==0
  rates.append({'group':group,'metric':'attack-goal satisfaction; clean rows NOT task accuracy',
   'r1':rate(s1,len(r1valid)),'r2':rate(s2,len(r2valid)),
   'r1_planned_success_bounds':[s1/100,(s1+100-len(r1valid))/100],
   'r2_planned_success_bounds':[s2/100,(s2+100-len(r2valid))/100]})
  common=[i for i in ids if i in r1valid and i in r2valid]
  transitions=Counter((R[i]['official_success'],P[i]['evaluation']['official_success']) for i in common)
  old=sum(R[i]['official_success'] for i in common);new=sum(P[i]['evaluation']['official_success'] for i in common)
  improved=transitions[True,False];worsened=transitions[False,True];discordant=improved+worsened
  p=min(1.,2*sum(math.comb(discordant,k) for k in range(min(improved,worsened)+1))/2**discordant) if discordant else 1.
  paired.append({'group':group,'common_valid_n':len(common),'r1':rate(old,len(common)),'r2':rate(new,len(common)),
   'success_to_failure':improved,'failure_to_success':worsened,'both_success':transitions[True,True],
   'both_failure':transitions[False,False],'absolute_drop_pp':100*(old-new)/len(common),
   'relative_drop':(old-new)/old if old else None,'mcnemar_exact_two_sided_p':p,
   'excluded_pair_ids':[i for i in ids if i not in common]})
  hits=sum(D[i]['detector_flag'] for i in ids)
  detector.append({'group':group,'n':len(ids),'positive':hits,'negative':len(ids)-hits,
   'positive_rate':hits/len(ids),'wilson95':wilson(hits,len(ids)),
   'meaning':'clean false-positive rate' if group.endswith(':no') else 'attack detection rate'})
  for flag in [0,1]:
   times=[D[i]['seconds'] for i in ids if D[i]['detector_flag']==flag]
   if times:timing.append({'group':group,'detector_flag':flag,'n':len(times),'total_seconds':sum(times),'median_seconds':statistics.median(times),'max_seconds':max(times)})
 assert len(queue)==115 and len(exceptions)==10
 result={'status':'RECEIPT_REVIEW_PASSED_R2_RAW_AUDIT_PENDING','review_utc':datetime.now(timezone.utc).isoformat(),
  'source_commit':REMOTE_COMMIT,'config_sha256':config_sha,'cases':400,'protected_generated':390,'F6':10,
  'F6_nonfinite_helper':sum(r['nonfinite_helper'] for r in exceptions),'resource_censored':0,
  'remaining_successes':len(queue),'F1_candidates':sum(r['detector_flag']==0 for r in queue),
  'localization_success_uncertain':sum(r['detector_flag']==1 for r in queue),'r3_human_review_complete':False,
  'receipt_integrity_passed':True,'r2_raw_rehashed_locally':False,'strict_paper_reproduction':False,
  'rates':rates,'paired':paired,'detector':detector,'timing':timing,
  'source_file_sha256':{p:sha(ROOT/p) for p in PATHS.values()},
  'limits':['Remote R1 raw audit is a source receipt, not a second local raw verification',
   'R2 plan/raw/full prompts/queries/cleanup and actual target overrides still on5090',
   'Unknown localization mapping prevents F2/F3 attribution from counters',
   'Resume clean official goal hits82%;100% attack goal satisfaction does not isolate causal attack effect',
   'This R0-R4 taxonomy differs from M2 mechanism F1-F6; never combine labels']}
 write('receipt_review.json',result)
 table('paired_cases.csv',joined);table('r3_review_queue.csv',queue);table('f6_cases.csv',exceptions)
 lines=['# R2回执接收与初步统计审查','',
  '**R2执行完成；回执一致性通过，但完整R2 raw复核及R3逐例人工归因尚未完成。**',
  '',f'已取回并核对远端提交`{REMOTE_COMMIT}`。只新增8个允许的回执/日志文件，无源码、参数、依赖或原始数据修改；总墙钟11小时41分28秒。400条防御及400条配对记录齐全，390次目标生成均返回EOS，10条上游F6跳过，无资源截断、CUDA/OOM或重试。',
  '', '本报告计算仅来自逐例小型回执；不把它写成协调端已重算完整原始模型响应的最终验收。原始trace仍在5090，不启动新GPU实验，不改参数。',
  '', '## 攻击目标满足率（公开快照guarded条件，非严格原论文配置）','',
  '| 域 | R1有效 | R2有效 | 共同有效R1 | 共同有效R2 | 配对绝对下降 |','| --- | --- | --- | --- | --- | --- |']
 for domain in ['email','resume']:
  a=next(r for r in rates if r['group']==domain+':authority_spoof');b=next(r for r in paired if r['group']==domain+':authority_spoof')
  lines.append(f"| {domain} | {a['r1']['successes']}/{a['r1']['evaluable']} ({a['r1']['rate']:.2%}) | {a['r2']['successes']}/{a['r2']['evaluable']} ({a['r2']['rate']:.2%}) | {b['r1']['successes']}/{b['common_valid_n']} ({b['r1']['rate']:.2%}) | {b['r2']['successes']}/{b['common_valid_n']} ({b['r2']['rate']:.2%}) | {b['absolute_drop_pp']:.2f}个百分点 |")
 lines += ['', 'Wilson95%区间、配对McNemar、失效范围界和逐例分母见receipt_review.json。Email共同有效92例，74次成功→失败、0次反向；不能用96/99和15/93直接当同分母配对比较。R1 email-072解析异常仍保留，R2该例有效但不进入共同有效对。',
  '', '**Resume攻击100/100满足官方目标，但clean也有82/100满足同一个goal=2。**这不是正常任务准确率，也不能单凭100%证明每条成功由注入造成。Email clean目标满足0/100同样不能推断合法任务全部正确。',
  '', '## 检测与异常','',
  '全文检测：Email clean51/100报阳性、attack90/100；Resume clean0/100、attack0/100。clean误报与合法信息损伤F5不是同一个指标。115条有效剩余目标命中中，110条检测返回0且回执cleaned SHA与固定原文一致（Email10+Resume100）；可列为F1待复核候选。其余5条Email检测触发但仍成功，定位/残留原因目前Uncertain，不从计数硬分F2/F3。',
  '', '10条F6全部Email localization，trace_counts显示nonfinite_helper=true，非边界NaN；clean3、attack7，均未执行protected生成，不能计作防御成功。10条清单见f6_cases.csv。',
  '', 'Email检测触发后大量mapping_status为UNKNOWN或UNKNOWN_INVALID_ORIGINAL_INTERVALS。有效执行不等于定位坐标已可靠；即使EXACT_ORDERED_NONWHITESPACE_COVERAGE也仅说明原分段映射，不自动证明恶意指令被完整覆盖/清除。',
  '', '## 下一步（本次未执行）','',
  '只读核验5090已有R2 plan、400份defense及400份protected raw的hash/来源，重算target渲染/实际greedy overrides和官方评分，导出115条剩余成功、10条F6及必要clean对照的可审查证据包。优先审5条检测触发仍成功的Email，核对原恶意span、实际oracle/helper异常、恢复文本和最终响应；Resume还要逐源匹配clean目标命中，避免把自然目标满足当注入因果。无需重跑GPU、修改helper、换checkpoint或扩大预算。',
  '', '本次接收仅验收回执完整与一致性；R3、R4和严格论文复现均未宣告完成。M1/M2与这份R0–R4归因表独立，尤其不要混用两边F1–F6含义。']
 with (OUT/'REPORT.md').open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(lines)+'\n')
 print(json.dumps({'status':result['status'],'F6':10,'remaining':115,'F1_candidates':110,'localization_uncertain':5,'paired':paired[:2]},indent=2))


if __name__=='__main__':main()
