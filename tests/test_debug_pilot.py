import hashlib
import json
from pathlib import Path
import sys

import pytest

from scripts import run_debug_pilot as pilot


def test_write_case_is_immutable_and_references_exact_raw_bytes(tmp_path):
    record = {'case_id': 'email-000-no', 'validity': 'F6_DEBUG', 'raw_response': None}
    summary = pilot.write_case(tmp_path, record)
    assert summary['evidence_sha256'] == hashlib.sha256(Path(summary['evidence_path']).read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        pilot.write_case(tmp_path, record)


def test_wrong_host_never_runs_benchmark_or_models(tmp_path, monkeypatch):
    monkeypatch.setattr(pilot, 'ROOT', tmp_path)
    monkeypatch.setattr(pilot.platform, 'node', lambda: 'cloud-vm')
    monkeypatch.setattr(pilot.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(pilot, 'git_head', lambda: 'input-head')
    monkeypatch.setattr(pilot, 'make_plan', lambda *a: pytest.fail('Wrong host cannot start real sample work'))
    monkeypatch.setattr(sys, 'argv', ['run_debug_pilot.py', '--stage', 'all'])
    assert pilot.main() == 2
    report = json.loads(next((tmp_path / 'coordination/returns').rglob('pilot_stage.json')).read_text())
    assert report['status'] == 'FAILED'
    assert report['benchmark_samples_used'] is False and report['asr_computed'] is False


def test_plan_outside_runs_is_rejected_before_reading(tmp_path, monkeypatch):
    monkeypatch.setattr(pilot, 'ROOT', tmp_path)
    path = tmp_path / 'untrusted.json'
    path.write_text('{}')
    with pytest.raises(ValueError, match='inside runs'):
        pilot.load_plan(path, {})
