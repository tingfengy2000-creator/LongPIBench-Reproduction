import json
from pathlib import Path
import sys
import pytest
from scripts import local_model_probe as probe


def test_rendered_target_chat_does_not_duplicate_bos():
    class Tokenizer:
        chat_template = '<BOS>chat'

        def apply_chat_template(self, messages, **kwargs):
            return '<BOS>system user assistant'

        def __call__(self, prompt, return_tensors, add_special_tokens=True):
            ids = ([128000] if prompt.startswith('<BOS>') else []) + [42]
            if add_special_tokens:
                ids.insert(0, 128000)
            return {'input_ids': ids}

    tokenizer = Tokenizer()
    # Reproduce the observed original 009 failure before checking the repair.
    assert tokenizer('<BOS>system user assistant', return_tensors='pt')['input_ids'][:2] == [128000, 128000]
    report = {}
    inputs = probe.tokenize_synthetic_prompt(tokenizer, 'target', report)
    assert inputs['input_ids'] == [128000, 42]
    assert report['tokenization']['add_special_tokens'] is False
    # Plain-text helper/base inputs retain their existing tokenizer defaults.
    assert probe.tokenize_synthetic_prompt(tokenizer, 'detector_base', {})['input_ids'] == [128000, 42]


@pytest.mark.parametrize('correct_host', [False, True])
def test_hardware_or_host_gate_prevents_model_runtime(tmp_path, monkeypatch, correct_host):
    calls = []
    def inventory(args, timeout=30):
        calls.append(args)
        if args[0] == 'git':
            return {'returncode': 0, 'stdout': 'a' * 40 + '\n'}
        return {'returncode': 127, 'stderr': 'No GPU in this synthetic guard test'}
    monkeypatch.setattr(probe, 'ROOT', tmp_path)
    monkeypatch.setattr(probe, 'run', inventory)
    monkeypatch.setattr(probe.platform, 'node', lambda: 'DESKTOP-B5PNBNC' if correct_host else 'cloud-vm')
    monkeypatch.setattr(probe.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(probe, 'probe_runtime', lambda *a: pytest.fail('Runtime must not run before hardware acceptance'))
    monkeypatch.setattr(probe, 'local_spec', lambda *a: pytest.fail('File plan must not run before hardware acceptance'))
    monkeypatch.setattr(sys, 'argv', ['local_model_probe.py', '--role', 'target'])
    assert probe.main() == 2
    row = json.loads(next((tmp_path / 'coordination/returns').rglob('model_load.json')).read_text(encoding='utf-8'))
    assert row['status'] == ('BLOCKED_HARDWARE' if correct_host else 'BLOCKED_WRONG_HOST_OR_SHELL')
    assert row['model_load_verified'] is False
    assert row['formal_inference_executed'] is False
    if not correct_host:
        assert not any('nvidia-smi' in str(arg) for args in calls for arg in args)


def test_model_path_uses_current_repo_cache_not_old_receipt_path(tmp_path):
    (tmp_path / 'configs').mkdir()
    revision = 'a' * 40
    files = [{'filename': 'config.json', 'size_bytes': 3}]
    model = {'role': 'helper', 'repo_id': 'org/model', 'revision': revision, 'files': files}
    (tmp_path / 'configs/offline_transfer_manifest.json').write_text(json.dumps({'hf_models': [model]}))
    (tmp_path / 'configs/upstream_lock.json').write_text(json.dumps({
        'model_snapshots_observed_at_audit': {'helper': {'repo_id': 'org/model', 'revision': revision}}}))
    receipt_path = tmp_path / probe.PUBLIC_RECEIPT
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text(json.dumps({'results': [{'role': 'helper', 'repo_id': 'org/model',
        'revision': revision, 'status': 'FILES_VERIFIED_NOT_MODEL_LOADED',
        'snapshot_path': 'Z:\\unavailable-on-linux\\old-cache'}]}))
    actual = tmp_path / 'models/hf-cache/models--org--model/snapshots' / revision
    actual.mkdir(parents=True)
    (actual / 'config.json').write_bytes(b'{}\n')
    result = probe.local_spec(tmp_path, 'helper')
    assert Path(result['resolved_path']) == actual.resolve()
    (actual / 'config.json').write_bytes(b'changed size')
    with pytest.raises(ValueError, match='size differs'):
        probe.local_spec(tmp_path, 'helper')
