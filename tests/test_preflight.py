import json
from pathlib import Path
import sys
from scripts import remote_preflight
from scripts import gpu_runtime_probe


def test_required_hardware_blocks_before_any_torch_probe(tmp_path, monkeypatch):
    calls = []
    def probe(args, timeout=30):
        calls.append(args)
        if args[0] == 'nvidia-smi':
            return {'error': 'FileNotFoundError'}
        return {'returncode': 0, 'stdout': '', 'stderr': ''}
    monkeypatch.setattr(remote_preflight, 'ROOT', tmp_path)
    monkeypatch.setattr(remote_preflight, 'run', probe)
    monkeypatch.setattr(sys, 'argv', ['remote_preflight.py', '--require-gpu', 'RTX 5090', '--task-id', 'R0-5090-002'])
    assert remote_preflight.main() == 2
    report = json.loads(next((tmp_path / 'coordination/returns').rglob('preflight.json')).read_text(encoding='utf-8'))
    assert report['task_status'] == 'BLOCKED'
    assert report['torch_probe']['status'] == 'SKIPPED_HARDWARE_GATE_FAILED'
    assert report['task_id'] == 'R0-5090-002'
    assert not any('-c' in args for args in calls)


def test_gpu_probe_records_current_task_and_skips_runtime_on_missing_gpu(tmp_path, monkeypatch):
    calls = []
    def missing_gpu(args, timeout=30):
        calls.append(args)
        return {'error': 'No GPU in this synthetic contract test'}
    monkeypatch.setattr(gpu_runtime_probe, 'ROOT', tmp_path)
    monkeypatch.setattr(gpu_runtime_probe, 'run', missing_gpu)
    monkeypatch.setattr(sys, 'argv', ['gpu_runtime_probe.py', '--task-id', 'R0-5090-004'])
    assert gpu_runtime_probe.main() == 2
    report = json.loads(next((tmp_path / 'coordination/returns').rglob('gpu_runtime.json')).read_text(encoding='utf-8'))
    assert report['task_id'] == 'R0-5090-004'
    assert report['status'] == 'BLOCKED'
    assert report['runtime']['status'] == 'SKIPPED_HARDWARE_GATE_FAILED'
    assert not any('-c' in args for args in calls)
