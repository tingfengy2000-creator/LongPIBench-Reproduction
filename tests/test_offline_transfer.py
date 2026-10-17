import builtins
import hashlib
import json
import sys
import zipfile
import pytest
from scripts import offline_hf_bundle, verify_aux_downloads


@pytest.mark.parametrize('coordination_report', [False, True])
def test_hf_offline_verification_needs_no_hub_or_credentials(tmp_path, monkeypatch, coordination_report):
    config = tmp_path / 'configs'
    config.mkdir()
    data = b'{}\n'
    item = {'filename': 'config.json', 'size_bytes': len(data), 'lfs_sha256': None,
            'git_blob_sha1': hashlib.sha1(b'blob 3\0' + data).hexdigest()}
    model = {'role': 'helper', 'repo_id': 'org/model', 'revision': 'a' * 40,
             'bundle_subdir': 'hf/helper', 'files': [item]}
    (config / 'offline_transfer_manifest.json').write_text(json.dumps({'hf_models': [model]}))
    (config / 'upstream_lock.json').write_text(json.dumps({
        'model_snapshots_observed_at_audit': {'helper': {'repo_id': 'org/model', 'revision': 'a' * 40}}}))
    bundle = tmp_path / 'bundle'
    folder = bundle / 'hf/helper'
    folder.mkdir(parents=True)
    (folder / 'config.json').write_bytes(data)
    original_import = builtins.__import__
    def guard(name, *args, **kwargs):
        if name.startswith(('huggingface_hub', 'torch', 'transformers')):
            pytest.fail('Offline verification must not import network/model runtimes')
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guard)
    monkeypatch.setattr(offline_hf_bundle, 'ROOT', tmp_path)
    argv = ['offline_hf_bundle.py', '--roles', 'helper', '--bundle-dir', str(bundle)]
    if coordination_report:
        argv += ['--task-id', 'R0-5090-008', '--report-root', str(tmp_path / 'coordination/returns')]
    monkeypatch.setattr(sys, 'argv', argv)
    assert offline_hf_bundle.main() == 0
    report_path = (next((tmp_path / 'coordination/returns').rglob('hf_files.json'))
                   if coordination_report else next(bundle.glob('*offline-hf-*.json')))
    result = json.loads(report_path.read_text(encoding='utf-8'))
    if coordination_report:
        assert result['task_id'] == 'R0-5090-008'
        assert 'git_head' in result
        assert report_path.parent.name == result['run_id']
    assert result['mode'] == 'offline_verify_only'
    assert result['status'] == 'FILES_VERIFIED_NOT_MODEL_LOADED'
    assert result['formal_inference_executed'] is False


@pytest.mark.parametrize('corrupt', [False, True])
def test_aux_crc_catches_corruption_without_loading_training_state(tmp_path, monkeypatch, corrupt):
    resource = tmp_path / 'resources'
    resource.mkdir()
    config_bytes = b'{"r":32}'
    weight = b'synthetic-weight-content'
    archive_path = resource / 'DataSentinel_Models.zip'
    config_member = 'checkpoint/adapter_config.json'
    weight_member = 'checkpoint/adapter_model.safetensors'
    with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(config_member, config_bytes)
        archive.writestr(weight_member, weight)
        archive.writestr('checkpoint/optimizer.pt', b'must never be deserialized')
    size = archive_path.stat().st_size
    if corrupt:
        blob = archive_path.read_bytes()
        assert blob.count(weight) == 1
        archive_path.write_bytes(blob.replace(weight, b'X' + weight[1:]))
    wheel_path = resource / 'en_core_web_sm-3.8.0-py3-none-any.whl'
    with zipfile.ZipFile(wheel_path, 'w') as archive:
        archive.writestr('en_core_web_sm-3.8.0.dist-info/METADATA', 'Metadata-Version: 2.1\nVersion: 3.8.0\n')
    manifest = {'aux_archives': [{'filename': archive_path.name, 'url': 'https://example.invalid/archive',
        'observed_size_bytes': size, 'adapter_configs': {config_member: {'r': 32}},
        'inference_files': [{'name': config_member, 'bytes': len(config_bytes)},
                            {'name': weight_member, 'bytes': len(weight)}]}],
        'spacy_model': {'filename': wheel_path.name, 'url': 'https://example.invalid/wheel',
                        'size_bytes': wheel_path.stat().st_size, 'digest': None}}
    (tmp_path / 'configs').mkdir()
    (tmp_path / 'configs/offline_transfer_manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(verify_aux_downloads, 'ROOT', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['verify_aux_downloads.py', '--download-dir', str(resource)])
    assert verify_aux_downloads.main() == (2 if corrupt else 0)
    report = json.loads(next((tmp_path / 'coordination/returns').rglob('aux_downloads.json')).read_text(encoding='utf-8'))
    assert report['results'][0]['status'] == ('FAILED' if corrupt else 'SOURCE_SIZE_CONFIG_AND_CRC_CHECKED')
    assert report['results'][0]['author_published_sha256_available'] is False
    assert report['model_load_verified'] is False
    assert set(resource.iterdir()) == {archive_path, wheel_path}
