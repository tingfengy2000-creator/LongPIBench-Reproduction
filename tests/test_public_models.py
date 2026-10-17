import hashlib
import pytest
from scripts.prepare_public_models import download_one, validate_plan, verify_file


def file_spec(name, data, lfs=True):
    return {'filename': name, 'size_bytes': len(data),
            'lfs_sha256': hashlib.sha256(data).hexdigest() if lfs else None,
            'git_blob_sha1': hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()}


def test_existing_corrupt_weight_is_never_replaced(tmp_path):
    model = {'role': 'helper', 'repo_id': 'org/model', 'revision': 'a' * 40,
             'files': [file_spec('model.safetensors', b'good')]}
    snapshot = tmp_path / 'models--org--model/snapshots' / ('a' * 40)
    snapshot.mkdir(parents=True)
    weight = snapshot / 'model.safetensors'
    weight.write_bytes(b'evil')
    def forbidden(**kwargs):
        pytest.fail('Must not replace an existing corrupt weight')
    with pytest.raises(ValueError, match='hash mismatch'):
        download_one(model, tmp_path, forbidden)
    assert weight.read_bytes() == b'evil'


def test_git_blob_and_lfs_hashes_are_distinctly_validated(tmp_path):
    path = tmp_path / 'config.json'
    path.write_bytes(b'{}\n')
    record = verify_file(path, file_spec(path.name, path.read_bytes(), lfs=False))
    assert record['verified_against'] == 'git_blob_sha1'
    assert record['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    wrong = file_spec(path.name, path.read_bytes())
    wrong['lfs_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='hash mismatch'):
        verify_file(path, wrong)


def test_plan_cannot_silently_substitute_target_model():
    plan = {'models': [{'role': 'target'}]}
    with pytest.raises(ValueError, match='only GPT-2'):
        validate_plan(plan, {})
