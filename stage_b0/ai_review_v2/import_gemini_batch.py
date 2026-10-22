"""Preserve a user-returned Gemini batch and audit strictly mechanical quote repair.

Only one layer of backslash-before-double-quote may be removed from evidence,
and only if the resulting entire quote occurs exactly once in the frozen input.
Labels, reasoning and all other fields are immutable. No model is called.
"""
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import uuid

from review_io import validate_records,read_jsonl

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    with path.open('x',encoding='utf8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')


def parse(raw):
    lines=[l for l in raw.decode('utf-8-sig').splitlines() if l.strip()]
    if lines and lines[0].strip() in ['```json','```jsonl','```']:
        assert lines[-1].strip()=='```','Incomplete code fence'
        lines=lines[1:-1]
    return [json.loads(line) for line in lines]


def normalize_evidence(rows,cases):
    output=copy.deepcopy(rows);changes=[]
    for original,record in zip(rows,output):
        case=cases[record['review_id']]
        value=record['evidence'];document=case['untrusted_document']
        if value not in document:
            repaired=value.replace('\\"','"')
            if repaired==value or not repaired or document.count(repaired)!=1:
                raise ValueError('Evidence cannot be mechanically aligned: '+record['review_id'])
            record['evidence']=repaired
            changes.append({'review_id':record['review_id'],'field':'evidence',
                            'operation':'remove_one_literal_backslash_before_double_quote',
                            'before':value,'after':repaired,'exact_input_occurrences':1,
                            'source_char_span':[document.index(repaired),document.index(repaired)+len(repaired)]})
        assert {k:v for k,v in original.items() if k!='evidence'}=={k:v for k,v in record.items() if k!='evidence'}
    return output,changes


def packet(batch):
    path=BASE/f'packets/secondary/batch-{batch:03d}.jsonl'
    lock=json.loads((BASE/'packets/secondary/packet_manifest.json').read_text(encoding='utf8'))
    expected=next(b['sha256'] for b in lock['batches'] if Path(b['path']).name==path.name)
    assert sha(path)==expected
    return path,{r['review_id']:r for r in read_jsonl(path)}


def verify_return(folder):
    folder=Path(folder)
    report=json.loads((folder/'verification.json').read_text(encoding='utf8'))
    path,cases=packet(report['batch_number'])
    raw=folder/'raw_response.txt'
    assert sha(raw)==report['raw_response_sha256']
    original=parse(raw.read_bytes());normalized,changes=normalize_evidence(original,cases)
    assert normalized==read_jsonl(folder/'reviews.normalized.jsonl')
    assert sha(folder/'reviews.normalized.jsonl')==report['normalized_reviews_sha256']
    assert changes==json.loads((folder/'normalization_audit.json').read_text(encoding='utf8'))
    assert validate_records(normalized,cases)==report['batch_validation']
    assert report['original_batch_sha256']==sha(path)
    print(report['status'], 'batch',report['batch_number'],'n',len(normalized),'quote repairs',len(changes))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path)
    ap.add_argument('--batch',type=int,choices=range(1,7))
    ap.add_argument('--verify-return',type=Path)
    args=ap.parse_args()
    if args.verify_return:
        verify_return(args.verify_return);return
    assert args.source and args.batch
    path,cases=packet(args.batch)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+f'-b0-gemini-batch{args.batch:03d}-'+uuid.uuid4().hex[:8]
    folder=ROOT/'coordination/returns'/run_id;folder.mkdir(parents=True,exist_ok=False)
    raw=args.source.read_bytes()
    with (folder/'raw_response.txt').open('xb') as f:f.write(raw)
    rows=parse(raw)
    assert len(rows)==20 and {r['review_id'] for r in rows}==set(cases)
    normalized,changes=normalize_evidence(rows,cases)
    validation=validate_records(normalized,cases)
    with (folder/'reviews.normalized.jsonl').open('x',encoding='utf8',newline='\n') as f:
        for r in normalized:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    write(folder/'normalization_audit.json',changes)
    metadata={'channel':'secondary','annotation_type':'AI_NOT_HUMAN',
              'reviewer_entrypoint':'Gemini (user-reported; exact web or Windows entrypoint not supplied)',
              'model_name':'unknown','model_version':'unknown','model_version_evidence':'Not supplied by user yet; do not infer from generated text',
              'execution_mode':'User-pasted visible batch response',
              'detector_scores_seen':None,'proposed_labels_seen':None,'other_reviewer_labels_seen':None,
              'human_review_performed':False,'metadata_status':'PENDING_USER_MODEL_AND_BLINDNESS_DETAILS'}
    write(folder/'reviewer_metadata.pending.json',metadata)
    verification={'status':'GEMINI_BATCH_RECORDS_ACCEPTED_AFTER_MECHANICAL_NORMALIZATION_METADATA_PENDING',
                  'task_id':'B0-GEMINI-001','run_id':run_id,'batch_number':args.batch,
                  'input_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  'source_attachment':str(args.source),'raw_response_sha256':sha(folder/'raw_response.txt'),
                  'normalized_reviews_sha256':sha(folder/'reviews.normalized.jsonl'),
                  'original_batch_path':path.relative_to(ROOT).as_posix(),'original_batch_sha256':sha(path),
                  'batch_validation':validation,'literal_evidence_repairs':len(changes),
                  'labels_and_reasons_changed':False,'all120_secondary_complete':False,
                  'model_identity_confirmed':False,'blindness_confirmed':False,
                  'human_gold':False,'detector_scores_computed':0}
    write(folder/'verification.json',verification)
    report=f'''# Gemini第{args.batch}批原始回传接收

状态：GEMINI_BATCH_RECORDS_ACCEPTED_AFTER_MECHANICAL_NORMALIZATION_METADATA_PENDING。

20条唯一ID和text_sha256全部对应原固定batch-{args.batch:03d}，schema/角色/标签通过。原始附件按字节完整保存在raw_response.txt，SHA见verification.json。

其中{len(changes)}处evidence包含额外的字面反斜杠引号，不能通过原文子串检查。仅对这些evidence移除一层反斜杠，并要求修正后整段引文在原输入恰好出现一次。前后值、字符区间及规则保存normalization_audit.json；其余字段包括label、role、reason、confidence和ID/摘要均未改变。规范化结果另存，不覆盖原回答，也没有改变旧验证器。

本批20条引文与结构接收不证明标签语义全部正确，也不等于全部120条已收齐。未生成最终AI标签冻结或human_signoff，未运行检测模型/业务任务。

Gemini具体型号/版本、实际入口，以及是否仅看过盲审附件尚未由用户提供，均标pending/unknown，不代填为false或假造版本。因此本批不是完整的metadata验收；待后续统一补齐，不要求用户重审已完成标签。

可继续第2–6批新对话；不得把Cursor结果、建议标签或本接收报告交给Gemini。为避免后续格式转义问题，提示evidence应写文档实际字符，双引号仅做标准JSON转义，勿保留输入JSON的额外编码层。

只读复核：python stage_b0/ai_review_v2/import_gemini_batch.py --verify-return {folder.relative_to(ROOT).as_posix()}
'''
    with (folder/'REPORT.md').open('x',encoding='utf8',newline='\n') as f:f.write(report)
    verify_return(folder)
    print(folder.relative_to(ROOT).as_posix())


if __name__=='__main__':main()
