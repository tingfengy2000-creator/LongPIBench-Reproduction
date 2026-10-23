"""Create collection config once, without model loads, data scoring or thresholds."""
import json
from pathlib import Path
from common import ROOT, PLAN, save, sha


def main():
    classifiers = {}
    for role in ['prompt_guard_1', 'piguard']:
        r = json.loads((ROOT/f'stage_b0/source_audit/{role}_load_probe.json').read_text(encoding='utf8'))
        classifiers[role] = {k: r[k] for k in ['repo_id', 'revision', 'files']}
    sources = [
        'stage_b0/dataset_manifest.jsonl', 'stage_b0/protocol_v1.md', 'stage_b0/evaluation.py', 'stage_b0/llm_prompts.json',
        'stage_b0/ai_review_v2/POLICY.md', 'stage_b0/ai_review_v2/SECOND_REVIEW_GEMINI_20261023.md',
        'stage_b0/ai_review_v2/label_gate.py', 'stage_b0/ai_review_v2/review_io.py',
        'stage_b0/source_audit/model_metadata.json', 'stage_b0/source_audit/prompt_guard_1_load_probe.json',
        'stage_b0/source_audit/piguard_load_probe.json', 'stage_b0/source_audit/custom_code_review.md',
        'stage_b0/availability_review_003/verify.py', 'stage_b0/availability_review_003/verification.json',
        'g0_resume_diagnosis/run_controls.py', 'g0_resume_diagnosis/audit_existing.py',
        'g0_resume_diagnosis/frozen_controls_v1/plan.json', 'repro/opi_loader.py', 'repro/locator_trace.py',
        'scripts/local_model_probe.py', 'configs/opi_core_sources.json', 'configs/upstream_lock.json',
        'configs/offline_transfer_manifest.json',
        'coordination/returns/20261017T160020Z-offline-hf-0a7c5a5d/hf_files.json',
        'coordination/returns/20261019T054409Z-g0-visibility-fd1beae5/g0_audit.json',
        'coordination/returns/20261023T013459Z-b0-availability-prompt_guard_2-570957a3/availability.json',
        'coordination/returns/20261023T013525Z-b0-availability-datasentinel-ef8859a0/availability.json',
        'coordination/returns/20261023T013847Z-b0-availability-llama-5c3f5d39/availability.json',
    ]
    sources += [p.relative_to(ROOT).as_posix() for p in PLAN.parent.glob('*.py')]
    label = 'coordination/returns/20261022T153529Z-b0-gemini-completion-2ba621b8/exploratory_label_freeze.json'
    sources.append(label)
    availability = json.loads((ROOT/'coordination/returns/20261023T013847Z-b0-availability-llama-5c3f5d39/availability.json').read_text(encoding='utf8'))
    save(PLAN, {
        'status': 'FROZEN_EXPLORATORY_COLLECTION_NOT_STARTED', 'task_id': 'B0-5090-004',
        'is_formal_paper_experiment': False, 'label_freeze': label,
        'availability_receipt_commit': '04cc5a879ed9e54800886ae4fc978e7020d71cbc',
        'classifiers': classifiers, 'serial_roles': ['piguard', 'prompt_guard_1', 'datasentinel', 'llama'],
        'planned_records': {'piguard': 400, 'prompt_guard_1': 400, 'datasentinel': 400, 'B4': 400, 'B5': 400},
        'excluded_unavailable': {'prompt_guard_2': 'Fixed revision HTTP403 in003; no substitute or repeated access attempt'},
        'llama_chat_template_sha256': availability['chat_template_sha256'],
        'target_files_receipt': 'coordination/returns/20261017T160020Z-offline-hf-0a7c5a5d/hf_files.json',
        'runtime_versions': {'torch': '2.7.1+cu128', 'transformers': '4.51.3', 'bitsandbytes': '0.46.1',
                             'accelerate': '1.6.0', 'peft': '0.15.2'},
        'window_policy': 'Native tokenizer specials per <=512 total tokens, nonoverlap full coverage, Max',
        'precision': {'classifiers': 'float32', 'datasentinel': 'original NF4 double_quant BF16 compute', 'llama': 'BF16 unquantized'},
        'thresholds_fitted_in_collection': False, 'holdout_metrics_computed_in_collection': False,
        'invalid_outputs': 'Preserve INVALID records, no retry or output repair',
        'fatal_runtime_failure': 'Preserve partial evidence and stop remaining roles; no dependency/code fixes on executor',
        'model_access_401_403': 'Record blocker and continue independent remaining roles',
        'latency_scope': 'Instrumented same5090 serial wall time including input processing and observation; load/warmup separate',
        'file_sha256': {name: sha(ROOT/name) for name in sorted(set(sources))},
    })
    print('Created frozen exploratory collector configuration:', sha(PLAN))


if __name__ == '__main__':
    main()
