import hashlib
import json
import sys
from types import SimpleNamespace
import zipfile

import pytest

from scripts import aux_runtime_probe as probe


def test_exported_base_embedding_does_not_imply_unsaved_adapter_tensor():
    lora = {'layer.lora_A.weight', 'layer.lora_B.weight'}
    saved = lora | {'lm_head.base_layer.weight'}
    report = {}
    extra = probe.validate_adapter_keys(saved, saved | {probe.BASE_INPUT_EMBEDDING}, lora, report)
    assert extra == {probe.BASE_INPUT_EMBEDDING}
    assert report['tensor_key_audit']['base_extra_verified'] is False
    # Classification is conditional: runtime must still prove equality to base.
    assert report['tensor_key_audit']['active_adapter_keys_absent_from_file'] == []
    assert probe.validate_adapter_keys(saved, saved, lora, {}) == set()


@pytest.mark.parametrize('fault', ['missing_saved', 'missing_active', 'extra_lora', 'unknown_base', 'empty'])
def test_key_audit_still_rejects_incomplete_or_unexplained_weights(fault):
    required = {'layer.lora_A.weight', 'layer.lora_B.weight'}
    saved = required | {'lm_head.base_layer.weight'}
    exported = saved | {probe.BASE_INPUT_EMBEDDING}
    if fault == 'missing_saved':
        exported.remove('lm_head.base_layer.weight')
    elif fault == 'missing_active':
        saved.remove('layer.lora_B.weight')
    elif fault == 'extra_lora':
        exported.add('other.lora_B.weight')
    elif fault == 'unknown_base':
        exported.add('some_other_base.weight')
    else:
        saved = set()
    with pytest.raises(ValueError):
        probe.validate_adapter_keys(saved, exported, required, {})


@pytest.mark.parametrize('fault', [None, 'wrong_module', 'changed_base_value'])
def test_extra_embedding_requires_module_identity_and_fixed_base_values(tmp_path, monkeypatch, fault):
    class Tensor:
        shape = (1, 2)
        dtype = 'float16'
        device = 'cuda:0'

        def __init__(self, values, pointer=10):
            self.values = values
            self.pointer = pointer

        def data_ptr(self):
            return self.pointer

        def detach(self):
            return self

        def cpu(self):
            return self

        def to(self, dtype):
            return self

    loaded = Tensor([1, 2])
    actual_input = Tensor([1, 2], pointer=99 if fault == 'wrong_module' else 10)
    expected = Tensor([1, 9] if fault == 'changed_base_value' else [1, 2])

    class Archive:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get_tensor(self, key):
            assert key == 'model.embed_tokens.weight'
            return expected

    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(equal=lambda a, b: a.values == b.values))
    monkeypatch.setitem(sys.modules, 'safetensors', SimpleNamespace(safe_open=lambda *a, **k: Archive()))
    monkeypatch.setattr(probe, 'ROOT', tmp_path)
    base = tmp_path / 'snapshot'
    base.mkdir()
    shard_name = 'model-00001-of-00002.safetensors'
    (base / shard_name).write_bytes(b'data')
    (base / 'model.safetensors.index.json').write_text(json.dumps({
        'weight_map': {'model.embed_tokens.weight': shard_name}}))
    (tmp_path / 'configs').mkdir()
    (tmp_path / 'configs/offline_transfer_manifest.json').write_text(json.dumps({
        'hf_models': [{'role': 'detector_base', 'files': [{'filename': shard_name, 'size_bytes': 4}]}]}))
    model = SimpleNamespace(get_input_embeddings=lambda: SimpleNamespace(weight=actual_input))
    report = {'tensor_key_audit': {'base_extra_verified': False}}
    if fault:
        with pytest.raises(ValueError):
            probe.verify_base_input_embedding(model, {probe.BASE_INPUT_EMBEDDING: loaded}, base, report)
        assert report['tensor_key_audit']['base_extra_verified'] is False
    else:
        probe.verify_base_input_embedding(model, {probe.BASE_INPUT_EMBEDDING: loaded}, base, report)
        assert report['tensor_key_audit']['base_extra_verified'] is True
        assert report['base_input_embedding_check']['equals_base_after_dtype_cast'] is True


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
