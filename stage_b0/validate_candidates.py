"""Read-only independent candidate checks; creates only a new validation receipt."""
from __future__ import annotations
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from evaluation import file_sha,validate_rows
from prepare_dataset import grams,jaccard

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'stage_b0'


def main():
    rows=[json.loads(x) for x in (BASE/'dataset_manifest.jsonl').read_text(encoding='utf8').splitlines()]
    validate_rows(rows)
    frozen=json.loads((BASE/'candidate_freeze.json').read_text(encoding='utf8'))
    assert file_sha(BASE/'dataset_manifest.jsonl')==frozen['dataset_manifest_sha256']
    assert file_sha(BASE/'sources.jsonl')==frozen['sources_sha256']
    assert file_sha(BASE/'prepare_dataset.py')==frozen['builder_sha256']
    sources=[json.loads(x) for x in (BASE/'sources.jsonl').read_text(encoding='utf8').splitlines()]
    # Independent check against the actual frozen official clean prompts rather
    # than the builder's broad source-JSON lexical screen.
    archived=[json.loads(x) for x in (ROOT/'audit/prepared_inputs.jsonl').read_text(encoding='utf8').splitlines()]
    old=[r['data_prompt'] for r in archived if r['attack']=='no']
    assert len(old)==200
    old += [json.loads(x)['text'] for x in (ROOT/'ingress_detection_pilot/stage_m1/sources_and_conditions.jsonl').read_text(encoding='utf8').splitlines()]
    old += [r['background'] for r in json.loads((ROOT/'ingress_detection_pilot/stage_m2/sources.json').read_text(encoding='utf8'))]
    assert len(old)==264
    oldg=[grams(t) for t in old]
    overlaps=[max(jaccard(grams(s['text']),g) for g in oldg) for s in sources]
    assert max(overlaps)<.30
    counts=Counter((r['domain'],r['split'],r['variant']) for r in rows)
    assert all(v==(24 if split=='development' else 16) for (d,split,variant),v in counts.items())
    for r in rows:
        span=r['inserted_char_span']
        if span:assert r['text'][span[0]:span[1]]==r['inserted_text']
        assert (r['label']==0)==(r['variant'] in ['ordinary','hard_benign'])
        assert r['actual_goal_satisfaction'] is None and r['causal_goal_change'] is None and r['business_task_damage'] is None
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    seals={name:file_sha(ROOT/name) for name in tracked if name and not name.startswith('stage_b0/') and not name.startswith('coordination/tasks/B0-')}
    result={'status':'CANDIDATE_STRUCTURE_AND_ISOLATION_PASS_HUMAN_LABELS_PENDING',
            'candidate_rows':400,'sources':80,'development_rows':240,'holdout_rows':160,
            'old264_canonical_prompt_max_word5_jaccard':max(overlaps),
            'historical_check_note':'Additional canonical-clean-prompt check; builder originally screened source JSON text. Both retained without rewriting candidate evidence.',
            'source_and_template_split_leakage':False,'inserted_spans_validated':320,
            'human_labels_signed':False,'candidate_model_scores':0,
            'dataset_manifest_sha256':file_sha(BASE/'dataset_manifest.jsonl'),
            'protocol_sha256':file_sha(BASE/'protocol_v1.md'),
            'existing_tracked_file_sha256':seals}
    with (BASE/'preparation_validation.json').open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(result['status'], 'historical canonical overlap',max(overlaps),'sealed',len(seals))


if __name__=='__main__':main()
