import hashlib
import json
import sys
import zipfile

import pytest

from scripts import aux_runtime_probe as probe


def fixture_archive(tmp_path, corrupt=False):
    config = b'{"r":32}'
    weight = b'synthetic-safetensors-placeholder'
    path = tmp_path / 'adapter.zip'
    members = {'checkpoint/adapter_config.json': config, 'checkpoint/adapter_model.safetensors': weight}
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
        archive.writestr('checkpoint/optimizer.pt', b'not for inference')
        archive.writestr('../outside.txt', b'must never be extracted')
    if corrupt:
        path.write_bytes(path.read_bytes().replace(weight, b'X' + weight[1:]))
    pack = {'inference_files': [{'name': name, 'bytes': len(data)} for name, data in members.items()],
            'adapter_configs': {'checkpoint/adapter_config.json': {'r': 32}}}
    row = {'files': [{'member': name, 'sha256_first_observed': hashlib.sha256(data).hexdigest()}
                     for name, data in members.items()]}
    return path, pack, row


def test_only_inference_files_extracted_and_no_overwrite(tmp_path):
    path, pack, row = fixture_archive(tmp_path)
    destination = tmp_path / 'output'
    destination.mkdir()
    copied = probe.extract_inference(path, pack, row, destination)
    assert len(copied) == 2
    assert {p.name for p in destination.rglob('*') if p.is_file()} == {
        'adapter_config.json', 'adapter_model.safetensors'}
    assert not (tmp_path / 'outside.txt').exists()
    with pytest.raises(FileExistsError):
        probe.extract_inference(path, pack, row, destination)


@pytest.mark.parametrize('fault', ['crc', 'hash', 'traversal'])
def test_corruption_or_unapproved_destination_is_rejected(tmp_path, fault):
    path, pack, row = fixture_archive(tmp_path, corrupt=fault == 'crc')
    if fault == 'hash':
        row['files'][0]['sha256_first_observed'] = '0' * 64
    if fault == 'traversal':
        pack['inference_files'][0]['name'] = '../adapter_config.json'
        row['files'][0]['member'] = '../adapter_config.json'
    destination = tmp_path / 'output'
    destination.mkdir()
    with pytest.raises((ValueError, zipfile.BadZipFile)):
        probe.extract_inference(path, pack, row, destination)
    assert not (tmp_path / 'adapter_config.json').exists()


def test_wrong_host_records_failure_without_prepare_or_gpu(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, 'ROOT', tmp_path)
    monkeypatch.setattr(probe.platform, 'node', lambda: 'cloud-vm')
    monkeypatch.setattr(probe.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(probe, 'run', lambda args: {'stdout': 'input-head'})
    monkeypatch.setattr(probe, 'prepare', lambda *a: pytest.fail('Wrong host cannot install/extract'))
    monkeypatch.setattr(probe, 'gpu_gate', lambda *a: pytest.fail('Wrong host cannot check CUDA'))
    monkeypatch.setattr(sys, 'argv', ['aux_runtime_probe.py', '--stage', 'prepare'])
    assert probe.main() == 2
    result = json.loads(next((tmp_path / 'coordination/returns').rglob('aux_runtime.json')).read_text())
    assert result['status'] == 'FAILED' and result['stage'] == 'host_gate'
    assert result['formal_inference_executed'] is False
    assert result['adapter_loaded_verified'] is False
