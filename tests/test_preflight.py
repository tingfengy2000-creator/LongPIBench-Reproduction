import json
from pathlib import Path
import sys
from scripts import remote_preflight


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
