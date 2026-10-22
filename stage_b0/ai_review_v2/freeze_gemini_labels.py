"""Append-only exploratory label overlay after the missing Gemini record is supplied.

No detector is called. --check-only replays source validation and the existing gate.
Original candidate labels and all partial/failed receipts remain immutable.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from import_gemini_batch import normalize_evidence, packet, parse, sha, write
from label_gate import require_exploratory_label_freeze, second_review_required
from receive_gemini_followup import check as check_partial_intake, CURSOR
from review_io import public_cases, read_jsonl, validate_metadata, validate_records

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
PREVIOUS = ROOT/'coordination/returns/20261022T153311Z-b0-gemini-intake-08640906'
DEFAULT = ROOT/'coordination/returns/20261022T153529Z-b0-gemini-completion-2ba621b8'


def rel(path):
    return Path(path).relative_to(ROOT).as_posix()


def jsonl(path, rows):
    with path.open('x', encoding='utf8', newline='\n') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False)+'\n')


def derive(folder):
    previous = check_partial_intake(PREVIOUS)
    assert previous['coverage']['n'] == 119
    missing = previous['missing_review_ids']
    assert missing == ['item-2ba621b87832e4b404a9']
    original = parse((folder/'raw_response.txt').read_bytes())
    normalized, changes = normalize_evidence(original, packet(5)[1])
    validate_records(normalized, packet(5)[1])
    by_id = {r['review_id']: r for r in normalized}
    state = json.loads((PREVIOUS/'intake.json').read_text(encoding='utf8'))
    old5 = next(b for b in state['batches'] if b['batch_number'] == 5)
    old = read_jsonl(ROOT/old5['normalized_reviews'])
    assert len(old) == 19
    assert all(by_id[r['review_id']] == r for r in old), 'Completed first responses changed'
    assert set(by_id)-{r['review_id'] for r in old} == set(missing)
    rows = []
    for batch in state['batches']:
        rows.extend(normalized if batch['batch_number'] == 5 else read_jsonl(ROOT/batch['normalized_reviews']))
    validate_records(rows, public_cases('secondary'))
    cursor = read_jsonl(ROOT/CURSOR/'reviews.jsonl')
    validate_records(cursor, public_cases('cursor'))
    first = {r['review_id']: r for r in cursor}
    secondary = {r['review_id']: r for r in rows}
    mapping = json.loads((BASE/'private_mapping.json').read_text(encoding='utf8'))
    dataset = read_jsonl(ROOT/'stage_b0/dataset_manifest.jsonl')
    needed = second_review_required(dataset, cursor, mapping)
    assert needed <= set(secondary)
    adjudicated = []
    for m in mapping:
        rid = m['review_id']; a = first[rid]; b = secondary.get(rid)
        label = a['ai_label']; status = 'AI_SINGLE_REVIEW_PROVISIONAL'
        if rid in needed or b:
            if a['ai_label'] is not None and b['ai_label'] == a['ai_label']:
                status = 'AI_AGREEMENT_PROVISIONAL'
            else:
                label = None; status = 'UNRESOLVED'
        adjudicated.append({'review_id': rid, 'sample_id': m['sample_id'],
                            'text_sha256': m['text_sha256'], 'effective_label': label,
                            'status': status, 'cursor_label': a['ai_label'],
                            'secondary_review_present': b is not None,
                            'secondary_label': b['ai_label'] if b else None,
                            'label_basis': 'EXPLORATORY_AI_REVIEW_NOT_HUMAN_GOLD'})
    return normalized, changes, rows, adjudicated, state, needed


def verify(folder):
    normalized, changes, rows, adjudicated, state, needed = derive(folder)
    assert normalized == read_jsonl(folder/'batch005.complete.normalized.jsonl')
    assert changes == json.loads((folder/'normalization_audit.json').read_text(encoding='utf8'))
    assert rows == read_jsonl(folder/'reviews.jsonl')
    assert adjudicated == read_jsonl(folder/'adjudicated_labels.jsonl')
    metadata = json.loads((folder/'reviewer_metadata.json').read_text(encoding='utf8'))
    validate_metadata(metadata, 'secondary')
    assert metadata['user_statement'] == json.loads((PREVIOUS/'reviewer_metadata.json').read_text(encoding='utf8'))['user_statement']
    freeze = json.loads((folder/'exploratory_label_freeze.json').read_text(encoding='utf8'))
    assert freeze['gemini_substitution_policy_sha256'] == sha(BASE/'SECOND_REVIEW_GEMINI_20261023.md')
    for path, digest in freeze['review_file_sha256'].items():
        assert sha(ROOT/path) == digest, path
    effective = require_exploratory_label_freeze(ROOT/'stage_b0', folder/'exploratory_label_freeze.json')
    lookup = {r['sample_id']: r for r in adjudicated}
    per_group = []
    for domain in ['email', 'resume']:
        for split in ['development', 'exploratory_holdout']:
            for variant in ['ordinary', 'hard_benign', 'authority_spoof', 'output_manipulation', 'private_context_exfiltration']:
                group = [r for r in effective if r['domain'] == domain and r['split'] == split and r['variant'] == variant]
                if not group:
                    continue
                per_group.append({'domain': domain, 'split': split, 'variant': variant,
                                  'n': len(group), 'label_counts': dict(Counter(str(r['label']) for r in group)),
                                  'review_status_counts': dict(Counter(lookup[r['sample_id']]['status'] for r in group))})
    assert sum(g['n'] for g in per_group) == 400
    cursor = {r['review_id']: r for r in read_jsonl(ROOT/CURSOR/'reviews.jsonl')}
    return {'status': 'EXPLORATORY_AI_LABELS_FROZEN',
            'primary_reviews': 400, 'secondary_reviews': len(rows), 'mandatory_second_reviews': len(needed),
            'secondary_complete': True, 'resubmitted_batch5_previously_complete_records_unchanged': 19,
            'newly_completed_record': 'item-2ba621b87832e4b404a9',
            'secondary_label_agreement_n': sum(r['ai_label'] == cursor[r['review_id']]['ai_label'] for r in rows),
            'secondary_role_agreement_n': sum(r['role'] == cursor[r['review_id']]['role'] for r in rows),
            'secondary_agreement_denominator': len(rows), 'agreement_is_accuracy': False,
            'label_counts': dict(Counter(str(r['label']) for r in effective)),
            'label_status_counts': dict(Counter(r['status'] for r in adjudicated)),
            'effective_vs_proposed_disagreements': sum(r['label'] != r['proposed_label'] for r in effective),
            'per_group': per_group,
            'original_intake_total_evidence_normalizations': sum(len(json.loads((ROOT/b['normalization_audit']).read_text(encoding='utf8'))) for b in state['batches']),
            'resubmission_evidence_normalizations': len(changes),
            'old_partial_receipts_preserved': True, 'historical_hash_checks_passed': True,
            'existing_label_gate_passed': True, 'human_gold': False, 'human_review_complete': False,
            'independent_model_builds_verified': False, 'is_formal_paper_experiment': False,
            'detector_scores_computed': 0, 'main_modified': False}


def create(folder):
    normalized, changes, rows, adjudicated, state, needed = derive(folder)
    jsonl(folder/'batch005.complete.normalized.jsonl', normalized)
    write(folder/'normalization_audit.json', changes)
    jsonl(folder/'reviews.jsonl', rows)
    jsonl(folder/'adjudicated_labels.jsonl', adjudicated)
    metadata = json.loads((PREVIOUS/'reviewer_metadata.json').read_text(encoding='utf8'))
    metadata['applies_to'] = 'All six fixed secondary batches plus user-supplied completion of batch 005'
    metadata['completion_provenance'] = 'User response to missing-record request; same 20-row batch, first 19 records unchanged'
    write(folder/'reviewer_metadata.json', metadata)
    provenance = {'source_type': 'USER_PASTED_QUESTION_REPLY_TEXT',
                  'question_item_id': '["request_user_input_async","call_f978330c0f384378971fb46654ec4f3c",0]',
                  'raw_response_representation': 'Verbatim decoded user answer saved as UTF-8 text with line breaks; not original transport bytes',
                  'raw_response_sha256': sha(folder/'raw_response.txt'),
                  'repeated_complete_records_unchanged': 19, 'previously_truncated_record_completed': 'item-2ba621b87832e4b404a9',
                  'new_model_review_requested': False, 'previous_intake': rel(PREVIOUS),
                  'input_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
    write(folder/'provenance.json', provenance)
    paths = [folder/name for name in ['raw_response.txt', 'batch005.complete.normalized.jsonl', 'normalization_audit.json',
                                     'reviews.jsonl', 'adjudicated_labels.jsonl', 'reviewer_metadata.json', 'provenance.json']]
    paths += [ROOT/CURSOR/'reviews.jsonl', ROOT/CURSOR/'reviewer_metadata.json',
              PREVIOUS/'intake.json', PREVIOUS/'verification.json', PREVIOUS/'reviewer_metadata.json',
              BASE/'POLICY.md', BASE/'SECOND_REVIEW_GEMINI_20261023.md', BASE/'packet_freeze.json',
              BASE/'private_mapping.json', Path(__file__)]
    paths += [ROOT/name for name in state['file_sha256']]
    freeze = {'status': 'EXPLORATORY_AI_LABELS_FROZEN', 'created_utc': datetime.now(timezone.utc).isoformat(),
              'input_commit': provenance['input_commit'], 'is_formal_paper_experiment': False,
              'human_review_complete': False, 'detector_outputs_used_for_labeling': False,
              'dataset_manifest_sha256': sha(ROOT/'stage_b0/dataset_manifest.jsonl'),
              'protocol_v1_sha256': sha(ROOT/'stage_b0/protocol_v1.md'),
              'policy_sha256': sha(BASE/'POLICY.md'),
              'gemini_substitution_policy_sha256': sha(BASE/'SECOND_REVIEW_GEMINI_20261023.md'),
              'cursor_reviews': CURSOR+'/reviews.jsonl', 'cursor_metadata': CURSOR+'/reviewer_metadata.json',
              'secondary_reviews': rel(folder/'reviews.jsonl'), 'secondary_metadata': rel(folder/'reviewer_metadata.json'),
              'adjudicated_labels': rel(folder/'adjudicated_labels.jsonl'),
              'review_file_sha256': {rel(p): sha(p) for p in paths},
              'primary_model': 'Grok 4.7 (Cursor-reported)', 'secondary_model': 'Gemini 3.1 Pro (user-reported UI)',
              'independent_model_builds_verified': False,
              'limitations': ['Exploratory AI labels only; no human gold',
                             'Fixed secondary sample is enriched by design, not a random label accuracy audit',
                             'Shared synthetic author and wording families limit external validity',
                             'Blindness is declared and procedural, not independently enforced',
                             'No detector scores or performance claims are created by this freeze']}
    write(folder/'exploratory_label_freeze.json', freeze)
    result = verify(folder)
    write(folder/'verification.json', result)
    (folder/'REPORT.md').write_text(
        '# B0探索性AI标签冻结验收\n\n'
        '状态：EXPLORATORY_AI_LABELS_FROZEN。此状态仅验收本轮标签门，不等于B0检测实验完成。\n\n'
        '用户补回原第5批20条可见JSONL，原先完整的19条逐字段不变，末条完整补齐。'
        '补回文本按UTF-8保存，不声称取得原始传输字节；摘要、原文引文、标签/角色/schema全部通过。'
        '此前截断附件、119条汇总、旧pending元数据保持原样；没有重新请求模型裁决或选择更有利答案。\n\n'
        'Cursor/Grok 4.7一审400/400；Gemini 3.1 Pro二审固定120/120，标签及角色均一致120/120。'
        '界面名称由用户提供，精确服务构建号unknown，盲法为用户声明与流程约束。'
        '固定二审包括全部80条Hard-Benign及预先冻结的40条其他控制，并非随机准确率审计。\n\n'
        '最终追加层：120条AI_AGREEMENT_PROVISIONAL，280条AI_SINGLE_REVIEW_PROVISIONAL，'
        'UNRESOLVED为0；良性160、攻击240。没有改写原manifest或原预设标签。'
        '这只是AI一致性，不是准确率、人工金标或确认性论文证据。\n\n'
        '原47个准备文件、更早历史文件和盲审packet摘要通过；原label_gate.py已真实调用通过。'
        '冻结文件绑定原政策及Gemini替换政策、所有实际审核来源和标签覆盖层摘要。'
        '本轮未运行检测模型、未调阈值、未加载GPU、未接触5090工作区或main。\n\n'
        '下一步仍是B0既定可用性核验与评分准备；5090独立任务B0-5090-003的完成与否须以实际回执为准。'
        '本次二审接收不自动启动400条评分，不开发新算法。正式确认性研究仍需另行人工审核。\n\n'
        f'只读复核：`python stage_b0/ai_review_v2/freeze_gemini_labels.py --folder {rel(folder)} --check-only`\n',
        encoding='utf8', newline='\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'per_group'}, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--folder', type=Path, default=DEFAULT)
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()
    folder = args.folder.resolve()
    assert folder.is_relative_to(ROOT.resolve())
    if args.check_only:
        result = verify(folder)
        assert result == json.loads((folder/'verification.json').read_text(encoding='utf8'))
        print(result['status'], result['label_status_counts'])
    else:
        create(folder)


if __name__ == '__main__':
    main()
