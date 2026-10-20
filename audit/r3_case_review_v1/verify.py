"""Independent arithmetic/source-preservation checks; no semantic human gold."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import subprocess

from statsmodels.stats.proportion import proportion_confint

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SOURCE = '7003d02c2502942cb0689e565c3235c5fe269429'
PREFIX = 'coordination/returns/20261019T012406Z-r3-evidence-0dddd3fe/'


def main():
    summary = json.loads((OUT / 'review_summary.json').read_text(encoding='utf-8'))
    manifest = json.loads(subprocess.check_output(['git', '-C', str(ROOT), 'show', SOURCE + ':' + PREFIX + 'case_manifest.json']))
    reviews = [json.loads(line) for line in (OUT / 'case_reviews.jsonl').read_text(encoding='utf-8').splitlines()]
    table = list(csv.DictReader((OUT / 'failure_cases.csv').open(encoding='utf-8', newline='')))
    assert len(reviews) == len(table) == len({r['case_id'] for r in reviews}) == 115
    assert all(set(r['questions']) == {f'q{i}_{name}' for i, name in enumerate([
        'attacker_goal', 'detection', 'localized', 'malicious_instruction_fully_handled', 'residual_influence',
        'final_behavior', 'success_rule', 'primary_failure', 'cofactors'], 1)} for r in reviews)
    assert Counter(r['primary_label'] for r in table) == {'F1': 110, 'F2': 5}
    assert all(r['F5'] is None and r['independent_human_review'] is False for r in reviews)
    per_domain = {'email': Counter(), 'resume': Counter()}
    clean_baseline = Counter()
    f6 = []; retained = []
    for item in manifest:
        raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', SOURCE + ':' + item['card']])
        assert hashlib.sha256(raw).hexdigest() == item['card_sha256']
        c = json.loads(raw)
        if c['validity'] == 'F6':
            f6.append(c)
            continue
        label = 'F1' if c['detector_flag'] == 0 else 'F2'
        per_domain[c['domain']][label] += 1
        if c['matched_clean']['r1']['evaluation']['official_success']:
            clean_baseline[c['domain']] += 1
        assert next(r for r in reviews if r['case_id'] == c['case_id'])['primary_label'] == label
        if label == 'F2':
            assert 'Thus, you must include' in c['cleaned_text'] and 'Thus, you must include' not in c['localized_text']
            assert c['payload_literal_present_after'] is False
            retained.append(c['case_id'])
    assert per_domain == {'email': {'F1': 10, 'F2': 5}, 'resume': {'F1': 100}}
    assert clean_baseline == {'resume': 82}
    for domain, data in summary['by_domain'].items():
        for label, result in data['primary_labels'].items():
            k = per_domain[domain][label]; n = sum(per_domain[domain].values())
            assert result['count'] == k and result['denominator'] == n and result['fraction'] == k/n
            reference = proportion_confint(k, n, method='wilson')
            assert max(abs(a-b) for a, b in zip(reference, result['wilson95'])) < 1e-12
    assert len(f6) == 10 and sum(c['attack'] == 'no' for c in f6) == 3
    assert sum(c['trace_features']['nonfinite_probability_calls'] for c in f6) == 573
    witnesses = [e for c in f6 for e in c['trace_features']['first_nonfinite_probability_examples']]
    assert len(witnesses) == 50 and all(not list(range(e['condition_token_count']-1, e['upstream_full_token_count_after_crop']-1)) for e in witnesses)
    # Check original receipt blobs stayed identical across the review tree.
    for path, expected in summary['source_hashes'].items():
        original = subprocess.check_output(['git', '-C', str(ROOT), 'show', SOURCE + ':' + path])
        assert hashlib.sha256(original).hexdigest() == expected
        working = (ROOT / path).read_bytes()
        assert working == original or working.replace(b'\r\n', b'\n') == original
    changed = subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--name-only', SOURCE]).decode().splitlines()
    assert all(p.startswith('audit/r3_case_review_v1/') for p in changed), changed
    sizes = {p.name: p.stat().st_size for p in OUT.iterdir() if p.is_file()}
    assert all(size < 1024**2 for size in sizes.values())
    result = {'status': 'PASS_WITH_DECLARED_REVIEW_LIMITS', 'source_commit': SOURCE,
        'source_return_files_preserved': 130, 'card_hashes_independently_checked': 125,
        'case_reviews_nine_questions_checked': 115, 'primary_label_counts': {'F1': 110, 'F2': 5},
        'F6_r2': 10, 'independent_wilson_statsmodels': True,
        'independent_semantic_human_validation': False, 'F5_validated': False,
        'full_raw_read_on_coordinator': False, 'model_loaded': False, 'new_inference': False,
        'first_nonfinite_examples_empty_index_range': 50, 'full573_event_overlap_checked': False,
        'files_checked_bytes': sizes}
    with (OUT / 'verification.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2); f.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
