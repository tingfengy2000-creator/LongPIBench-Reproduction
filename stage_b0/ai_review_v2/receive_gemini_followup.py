"""Append-only intake of Gemini responses, including an explicitly truncated last row.

An incomplete row is retained as raw evidence and never promoted into a label.
Use --verify-return to replay parsing, quote normalization and cross-review checks.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid

from import_gemini_batch import normalize_evidence, packet, parse, sha, write
from review_io import public_cases, read_jsonl, validate_metadata, validate_records
from label_gate import second_review_required

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
FIRST = 'coordination/returns/20261022T152318Z-b0-gemini-batch001-459a34d6'
CURSOR = 'coordination/returns/20261020T153853Z-b0-cursor-label-review-83657036'


def available_records(raw):
    """Accept valid rows; recognize only one incomplete JSON string on the final line."""
    lines = [s for s in raw.decode('utf-8-sig').splitlines() if s.strip()]
    if lines and lines[0].strip() in ['```json', '```jsonl', '```']:
        assert lines[-1].strip() == '```', 'Incomplete code fence'
        lines = lines[1:-1]
    rows = []
    for index, line in enumerate(lines):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as error:
            if index != len(lines)-1 or not error.msg.startswith('Unterminated string'):
                raise
            rid = re.search(r'"review_id"\s*:\s*"([^"]+)"', line)
            digest = re.search(r'"text_sha256"\s*:\s*"([0-9a-f]{64})"', line)
            assert rid and digest, 'Truncated row lacks identifiable ID/hash'
            return rows, {'line_number': index+1, 'error': error.msg,
                          'review_id': rid.group(1), 'text_sha256': digest.group(1),
                          'accepted_as_review': False, 'raw_line': line}
    return rows, None


def identify(raw):
    rows, incomplete = available_records(raw)
    ids = {r['review_id'] for r in rows}
    assert len(ids) == len(rows), 'Duplicate review IDs'
    expected_ids = ids | ({incomplete['review_id']} if incomplete else set())
    matches = [i for i in range(1, 7) if set(packet(i)[1]) == expected_ids]
    assert len(matches) == 1, 'Response does not match one original batch'
    batch = matches[0]
    _, cases = packet(batch)
    if incomplete:
        assert incomplete['review_id'] not in ids
        assert incomplete['text_sha256'] == cases[incomplete['review_id']]['text_sha256']
    return batch, rows, incomplete


def check(folder):
    folder = Path(folder)
    state = json.loads((folder/'intake.json').read_text(encoding='utf8'))
    for name, digest in state['file_sha256'].items():
        assert sha(ROOT/name) == digest, name
    assert state['input_commit'] == subprocess.check_output(
        ['git', 'rev-parse', state['input_commit']], cwd=ROOT, text=True).strip()
    batches = []
    all_rows = []
    for entry in state['batches']:
        batch = entry['batch_number']
        _, cases = packet(batch)
        raw_path = ROOT/entry['raw_response']
        if batch == 1:
            original = parse(raw_path.read_bytes()); incomplete = None
        else:
            found, original, incomplete = identify(raw_path.read_bytes())
            assert found == batch
        normalized, changes = normalize_evidence(original, cases)
        assert normalized == read_jsonl(ROOT/entry['normalized_reviews'])
        assert changes == json.loads((ROOT/entry['normalization_audit']).read_text(encoding='utf8'))
        if batch != 1:
            assert incomplete == json.loads((ROOT/entry['parse_audit']).read_text(encoding='utf8'))
        validation = validate_records(normalized, cases, complete=incomplete is None)
        assert validation['n'] == entry['accepted_records']
        assert incomplete == entry['incomplete_record']
        all_rows.extend(normalized)
        batches.append({'batch_number': batch, 'accepted_records': len(normalized),
                        'literal_quote_repairs': len(changes),
                        'missing_review_id': incomplete['review_id'] if incomplete else None})
    assert sorted(x['batch_number'] for x in batches) == list(range(1, 7))
    assert all_rows == read_jsonl(folder/'reviews.available.jsonl')
    validation = validate_records(all_rows, public_cases('secondary'), complete=False)
    metadata = json.loads((folder/'reviewer_metadata.json').read_text(encoding='utf8'))
    declared = validate_metadata(metadata, 'secondary')
    cursor = read_jsonl(ROOT/CURSOR/'reviews.jsonl')
    validate_records(cursor, public_cases('cursor'))
    first = {r['review_id']: r for r in cursor}
    disagreements = []
    roles = []
    for r in all_rows:
        a = first[r['review_id']]
        if a['ai_label'] != r['ai_label']:
            disagreements.append({'review_id': r['review_id'], 'cursor_label': a['ai_label'],
                                  'gemini_label': r['ai_label']})
        if a['role'] != r['role']:
            roles.append({'review_id': r['review_id'], 'cursor_role': a['role'], 'gemini_role': r['role']})
    mapping = json.loads((BASE/'private_mapping.json').read_text(encoding='utf8'))
    needed = second_review_required(read_jsonl(ROOT/'stage_b0/dataset_manifest.jsonl'), cursor, mapping)
    missing = sorted(needed - {r['review_id'] for r in all_rows})
    for file, key in [('prepared_bundle_freeze.json', 'new_file_sha256'),
                      ('preparation_validation.json', 'existing_tracked_file_sha256')]:
        lock = json.loads((ROOT/'stage_b0'/file).read_text(encoding='utf8'))
        for name, digest in lock[key].items():
            assert sha(ROOT/name) == digest, 'Historical file changed: '+name
    return {'status': 'GEMINI_SECOND_REVIEW_INCOMPLETE' if missing else 'GEMINI_SECOND_REVIEW_RECEIVED_REVIEW_REQUIRED',
            'coverage': validation, 'batches': batches, 'mandatory_second_reviews': len(needed),
            'missing_review_ids': missing, 'label_disagreements': disagreements, 'role_disagreements': roles,
            'label_counts': dict(Counter(str(r['ai_label']) for r in all_rows)),
            'confidence_counts': dict(Counter(r['confidence'] for r in all_rows)),
            'label_agreement_n': len(all_rows)-len(disagreements), 'label_agreement_denominator': len(all_rows),
            'agreement_is_accuracy': False, 'blindness_user_declared': declared['blindness_declared'],
            'independent_model_build_verified': False, 'historical_hash_checks_passed': True,
            'exploratory_label_freeze_created': False, 'human_gold': False, 'detector_scores_computed': 0}


def receive(sources):
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-b0-gemini-intake-'+uuid.uuid4().hex[:8]
    folder = ROOT/'coordination/returns'/run_id
    folder.mkdir(parents=True, exist_ok=False)
    (folder/'.gitattributes').write_text('raw_response.txt -text -whitespace\n', encoding='utf8')
    meta = {'channel': 'secondary', 'annotation_type': 'AI_NOT_HUMAN',
            'reviewer_entrypoint': 'Gemini user-operated interface; web or Windows entrypoint unspecified',
            'model_name': 'Gemini 3.1 Pro', 'model_version': '3.1 Pro (displayed name; service build unknown)',
            'model_version_evidence': 'User reports UI displays 3.1pro; no independent build verification',
            'execution_mode': 'User-pasted visible batch responses',
            'proposed_labels_seen': False, 'other_reviewer_labels_seen': False,
            'detector_scores_seen': False, 'human_review_performed': False,
            'user_statement': 'gemini显示3.1pro 确认没有给它看过 Cursor 回答或预设标签。',
            'blindness_provenance': 'User declaration; not independently observed or technically enforced',
            'detector_score_provenance': 'Workflow: no B0 candidate detector scoring has been executed; no scores in blind packets',
            'statement_received_local_date': '2026-10-23', 'independent_model_build_verified': False}
    write(folder/'reviewer_metadata.json', meta)
    first = ROOT/FIRST
    entries = [{'batch_number': 1, 'raw_response': FIRST+'/raw_response.txt',
                'normalized_reviews': FIRST+'/reviews.normalized.jsonl',
                'normalization_audit': FIRST+'/normalization_audit.json',
                'accepted_records': 20, 'incomplete_record': None}]
    for source in sources:
        source = Path(source)
        raw = source.read_bytes()
        # Preserve the attachment before interpretation; never overwrite prior receipts.
        sub = folder/('attachment-'+source.parent.name)
        sub.mkdir(exist_ok=False)
        (sub/'raw_response.txt').write_bytes(raw)
        batch, rows, incomplete = identify(raw)
        normalized, changes = normalize_evidence(rows, packet(batch)[1])
        validate_records(normalized, packet(batch)[1], complete=incomplete is None)
        with (sub/'reviews.normalized.jsonl').open('x', encoding='utf8', newline='\n') as f:
            for r in normalized:
                f.write(json.dumps(r, ensure_ascii=False)+'\n')
        write(sub/'normalization_audit.json', changes)
        write(sub/'parse_audit.json', incomplete)
        prefix = sub.relative_to(ROOT).as_posix()
        entries.append({'batch_number': batch, 'source_attachment': str(source),
                        'raw_response': prefix+'/raw_response.txt',
                        'normalized_reviews': prefix+'/reviews.normalized.jsonl',
                        'normalization_audit': prefix+'/normalization_audit.json',
                        'parse_audit': prefix+'/parse_audit.json',
                        'accepted_records': len(normalized), 'incomplete_record': incomplete})
    entries.sort(key=lambda x: x['batch_number'])
    with (folder/'reviews.available.jsonl').open('x', encoding='utf8', newline='\n') as f:
        for entry in entries:
            for r in read_jsonl(ROOT/entry['normalized_reviews']):
                f.write(json.dumps(r, ensure_ascii=False)+'\n')
    paths = [folder/'reviews.available.jsonl', folder/'reviewer_metadata.json', Path(__file__),
             BASE/'SECOND_REVIEW_GEMINI_20261023.md', BASE/'packet_freeze.json',
             ROOT/CURSOR/'reviews.jsonl', ROOT/CURSOR/'reviewer_metadata.json']
    for entry in entries:
        paths.extend(ROOT/entry[key] for key in ['raw_response', 'normalized_reviews', 'normalization_audit'])
        if 'parse_audit' in entry:
            paths.append(ROOT/entry['parse_audit'])
    state = {'run_id': run_id, 'task_id': 'B0-GEMINI-001', 'batches': entries,
             'input_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
             'file_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in paths}}
    write(folder/'intake.json', state)
    result = check(folder)
    write(folder/'verification.json', result)
    (folder/'REPORT.md').write_text(
        '# Gemini固定二审回传核验（追加）\n\n'
        f"状态：{result['status']}。已接收有效完整记录{result['coverage']['n']}/120。\n\n"
        '用户确认界面显示Gemini 3.1 Pro，并未向其提供Cursor回答或预设标签。此为用户声明，'
        '服务端构建号unknown，未独立验证模型身份或盲法。第一批旧pending元数据保留，本目录追加本次确认。\n\n'
        '所有附件原字节保留。仅对引文中额外一层反斜杠引号按既有规则作机械规范化，'
        '修正后完整引文必须在冻结输入中恰好出现一次；标签、角色、理由、信心均不改。'
        '第五批最后一条JSON字符串截断，不补齐、不使用其中残缺标签；见parse_audit.json。\n\n'
        f"已完成条目与Cursor的标签一致{result['label_agreement_n']}/{result['label_agreement_denominator']}，"
        f"角色分歧{len(result['role_disagreements'])}条。此为AI间一致性，不是准确率或人工金标。\n\n"
        f"缺失完整审核：{', '.join(result['missing_review_ids'])}。等待从原对话补回完整记录，"
        '不要求重审其余条目。未生成最终标签冻结，未运行B0检测评分或新算法。原47文件与更早历史文件摘要均通过。\n\n'
        f'只读复核：`python stage_b0/ai_review_v2/receive_gemini_followup.py --verify-return {folder.relative_to(ROOT).as_posix()}`\n',
        encoding='utf8', newline='\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(folder.relative_to(ROOT).as_posix())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', nargs='+', type=Path)
    ap.add_argument('--verify-return', type=Path)
    args = ap.parse_args()
    if args.verify_return:
        result = check(args.verify_return)
        assert result == json.loads((args.verify_return/'verification.json').read_text(encoding='utf8'))
        print(result['status'], result['coverage'])
    else:
        assert args.source
        receive(args.source)


if __name__ == '__main__':
    main()
