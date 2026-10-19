"""Read-only R4 receipt validation; only creates this additive review's output.

Does not load a model, rerun historical writers, or alter the remote receipt.
Run from any directory. Use --check-only to compare with the saved verification.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
INPUT = "1e3f56506a7736fec745936d85c6ed75e71dab11"
RECEIPT = "a7e5e4eea4ea7c800e8f983a6e31928464b2e136"
RETURN = "coordination/returns/20261019T152826Z-r4-summary-b6255840"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def read_json(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def rows(name):
    with (ROOT / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def wilson(s, n):
    z = 1.959963984540054
    p = s / n
    denominator = 1 + z*z/n
    center = (p + z*z/(2*n)) / denominator
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denominator
    return [max(0, center-half), min(1, center+half)]


def verify():
    expected_files = sorted(f"{RETURN}/{name}" for name in
                            ["R4_REPORT.md", "RESULT_TABLES.md", "OPEN_ITEMS.md", "REPORT.md"])
    git("merge-base", "--is-ancestor", INPUT, RECEIPT)
    assert git("rev-parse", RECEIPT + "^").decode().strip() == INPUT
    delta = git("diff", "--name-status", INPUT, RECEIPT).decode().splitlines()
    assert sorted(delta) == sorted("A\t" + p for p in expected_files)
    receipt_hashes = {}
    texts = {}
    for name in expected_files:
        blob = git("show", f"{RECEIPT}:{name}")
        local = (ROOT / name).read_bytes()
        assert local.replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n")
        receipt_hashes[name] = hashlib.sha256(blob).hexdigest()
        texts[Path(name).name] = blob.decode("utf-8")

    r2 = read_json("audit/r2_receipt_review_v1/receipt_review.json")
    r3 = read_json("audit/r3_case_review_v1/review_summary.json")
    g0 = read_json("g0_resume_diagnosis/final_review_v1/analysis.json")
    # Verify retained provenance hashes without invoking any historical writer.
    source_hashes = {}
    for source, field in [(r2, "source_file_sha256"), (r3, "source_hashes"),
                          (g0, "source_return_file_sha256")]:
        for name, expected in source[field].items():
            actual = hashlib.sha256(git("show", f"{RECEIPT}:{name}")).hexdigest()
            assert actual == expected, name
            source_hashes[name] = actual

    paired = rows("audit/r2_receipt_review_v1/paired_cases.csv")
    assert len(paired) == 400 and len({r['case_id'] for r in paired}) == 400
    groups = {}
    intervals = {}
    for entry in r2['rates']:
        group = entry['group']
        domain, attack = group.split(':')
        subset = [r for r in paired if r['domain'] == domain and r['attack'] == attack]
        assert len(subset) == 100
        record = {"planned": len(subset)}
        intervals[group] = {}
        for stage in ('r1', 'r2'):
            valid = [r for r in subset if r[f'{stage}_validity'] == 'VALID']
            success = sum(r[f'{stage}_official_success'] == 'True' for r in valid)
            assert (success, len(valid)) == (entry[stage]['successes'], entry[stage]['evaluable'])
            assert math.isclose(success / len(valid), entry[stage]['rate'])
            ci = wilson(success, len(valid))
            assert all(abs(a-b) < 1e-12 for a,b in zip(ci, entry[stage]['wilson95']))
            record[stage] = {'hits': success, 'valid': len(valid), 'F6': 100-len(valid)}
            intervals[group][stage] = entry[stage]['wilson95']
        common = [r for r in subset if r['r1_validity'] == r['r2_validity'] == 'VALID']
        p = next(p for p in r2['paired'] if p['group'] == group)
        transitions = Counter((r['r1_official_success'] == 'True',
                               r['r2_official_success'] == 'True') for r in common)
        assert len(common) == p['common_valid_n']
        for key, pair in [('success_to_failure', (True, False)),
                          ('failure_to_success', (False, True)),
                          ('both_success', (True, True)), ('both_failure', (False, False))]:
            assert transitions[pair] == p[key]
        drop = 100*(transitions[(True,False)]-transitions[(False,True)])/len(common)
        assert abs(drop-p['absolute_drop_pp']) < 1e-12
        assert sorted(r['case_id'] for r in subset if r not in common) == sorted(p['excluded_pair_ids'])
        record['paired'] = {'n':len(common), 'r1_hits':sum(k[0]*v for k,v in transitions.items()),
                            'r2_hits':sum(k[1]*v for k,v in transitions.items()),
                            'drop_pp':drop, 'success_to_failure':transitions[(True,False)],
                            'failure_to_success':transitions[(False,True)]}
        groups[group] = record
    assert 2**(-73) == next(p for p in r2['paired'] if p['group']=='email:authority_spoof')['mcnemar_exact_two_sided_p']

    # Compare all formal table cells (not merely totals) against the row recount.
    lines = texts['RESULT_TABLES.md'].splitlines()
    table1 = [l for l in lines if l.startswith('| ') and ' | 100 | ' in l][:4]
    labels = ['Email clean','Resume clean','Email attack','Resume attack']
    for line, label, (group, r) in zip(table1, labels, groups.items()):
        cells = [c.strip() for c in line.strip('|').split('|')]
        assert cells[0] == label and int(cells[1]) == 100
        assert [int(cells[i]) for i in (2,3,4,6,7,8)] == [r['r1']['valid'],r['r1']['hits'],r['r1']['F6'],r['r2']['valid'],r['r2']['hits'],r['r2']['F6']]
        for stage, col in [('r1',5),('r2',9)]:
            assert cells[col].startswith(f"{r[stage]['hits']}/{r[stage]['valid']}")
    assert len(table1) == 4
    section2 = texts['RESULT_TABLES.md'].split('## 表 2.')[1].split('## 表 3.')[0]
    table2 = [line for line in section2.splitlines() if line.startswith('| Email') or line.startswith('| Resume')]
    assert len(table2) == 4
    for line, label, r in zip(table2, labels, groups.values()):
        cells = [c.strip() for c in line.strip('|').split('|')]
        p = r['paired']
        assert cells[0] == label and int(cells[1]) == p['n']
        assert cells[2].startswith(f"{p['r1_hits']}/{p['n']}")
        assert cells[3].startswith(f"{p['r2_hits']}/{p['n']}")
        assert cells[4] == f"{p['drop_pp']:.2f} 个百分点"
        assert (int(cells[5]), int(cells[6])) == (p['success_to_failure'],p['failure_to_success'])

    failures = rows('audit/r3_case_review_v1/failure_cases.csv')
    remaining_ids = {r['case_id'] for r in paired if r['attack'] != 'no' and r['r2_validity']=='VALID' and r['r2_official_success']=='True'}
    assert len(failures) == 115 and {r['case_id'] for r in failures} == remaining_ids
    primary = Counter(r['primary_label'] for r in failures)
    assert dict(primary) == r3['primary_labels'] == {'F1':110, 'F2':5}
    assert all(r['F5']=='unknown' and r['independent_human_review']=='False' for r in failures)
    by_domain = {d:dict(Counter(r['primary_label'] for r in failures if r['domain']==d)) for d in ['email','resume']}
    assert by_domain == {'email':{'F2':5,'F1':10},'resume':{'F1':100}}
    section3 = texts['RESULT_TABLES.md'].split('## 表 3.')[1].split('## 表 4.')[0]
    table3 = [line for line in section3.splitlines() if line.startswith(('| Email','| Resume','| 合计'))]
    assert len(table3) == 3
    for line, expected in zip(table3,[(15,10,5,0,0,0),(100,100,0,0,0,0),(115,110,5,0,0,0)]):
        cells = [c.strip() for c in line.strip('|').split('|')]
        assert tuple(int(c.split('（')[0]) for c in cells[1:]) == expected
    loc = read_json('audit/r3_case_review_v1/localization_case_evidence.json')
    assert {r['case_id'] for r in loc} == {r['case_id'] for r in failures if r['primary_label']=='F2'}
    assert len(loc)==5 and all(not r['full_payload_literal_present'] and 'must include' in r['retained_directive_exact'] for r in loc)
    assert sum(r['insertion_source_coverage'] is None for r in loc)==4
    assert next(r for r in loc if r['case_id']=='email-041-authority_spoof')['insertion_source_coverage']==0

    f6 = rows('audit/r3_case_review_v1/f6_cases.csv')
    assert len(f6)==10 and sum(r['attack']=='no' for r in f6)==3
    assert {r['case_id'] for r in f6} == {r['case_id'] for r in paired if r['r2_validity']!='VALID'}
    nonfinite = sum(int(r['nonfinite_probability_calls']) for r in f6)
    crop = sum(int(r['condition_exceeds_crop_calls']) for r in f6)
    examples = sum(int(r['individually_checked_nonfinite_examples']) for r in f6)
    assert (nonfinite,crop,examples)==(573,573,50)
    assert r3['F5']['value'] is None and not r3['independent_human_review']
    visibility = rows('g0_resume_diagnosis/final_review_v1/resume100_visibility.csv')
    assert len(visibility)==100 and len({r['case_id'] for r in visibility})==100
    assert all(r['root_category']=='B' and r['payload_complete_in_actual_input']=='True' and r['binary_flag']=='0' and r['truncation_direction']=='none' for r in visibility)
    assert (min(int(r['actual_detector_input_tokens']) for r in visibility),max(int(r['actual_detector_input_tokens']) for r in visibility)) == (339,1037)
    controls = rows('g0_resume_diagnosis/final_review_v1/all26_controls.csv')
    assert len(controls)==26 and sum(r['binary_flag']=='1' for r in controls)==4
    assert not g0['full_npz_arrays_independently_read_on_coordinator']
    assert g0['source_document_count']==4 and not g0['algorithm_development_go']
    assert all(r['full_npz_read_on_coordinator']=='False' for r in controls)

    # Exact wording boundaries are also reviewed manually in REPORT.md.
    combined = '\n'.join(texts.values())
    for phrase in ['82/100','unknown','573','50','115','110','339–1037','8,320,000']:
        assert phrase in combined
    assert '独立人工复核尚未进行' in texts['OPEN_ITEMS.md']
    assert '不表示 R0–R4 整体验收完成' in texts['R4_REPORT.md']
    assert '2026-10-20' in texts['R4_REPORT.md']
    return {
        'status':'PASS_R4_DESCRIPTIVE_DELIVERABLE_WITH_DECLARED_LIMITS',
        'input_commit':INPUT,'receipt_commit':RECEIPT,
        'receipt_file_git_sha256':receipt_hashes,
        'only_four_additions_no_prior_file_changes':True,
        'retained_source_hashes_verified':len(source_hashes),
        'formal_rows_independently_recounted':400,'groups':groups,
        'existing_wilson95_reconciled':intervals,
        'r3_primary_counts':dict(primary),'r3_by_domain':by_domain,
        'F6':{'r1_parse':1,'r2_upstream':10,'nonfinite_calls':nonfinite,
              'crop_calls':crop,'prior_individually_checked_examples':examples},
        'resume_visibility_B':100,'controls_separate_n':26,'control_sources':4,
        'F5_validated':False,'independent_human_review':False,
        'full573_callwise_overlap_verified':False,'full_remote_raw_locally_read':False,
        'full_npz_locally_read':False,'new_model_forward':0,
        'new_statistical_test':False,'algorithm_development_authorized':False,
        'strict_paper_reproduction':False,'R0_R4_overall_acceptance':False,
        'nonblocking_presentation_note':'Existing Wilson intervals are referenced by R4 rather than printed. Numeric intervals are retained here for convenient checking; clean table columns denote goal hits, not task accuracy.',
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    actual=verify()
    target=OUT/'verification.json'
    if args.check_only:
        assert json.loads(target.read_text(encoding='utf-8'))==actual
    else:
        with target.open('x',encoding='utf-8') as f:
            json.dump(actual,f,ensure_ascii=False,indent=2)
            f.write('\n')
    print(actual['status'])
    print('400 formal rows; 115 labels; 10 F6; 100 visibility rows; 26 separate controls.')


if __name__=='__main__':
    main()
