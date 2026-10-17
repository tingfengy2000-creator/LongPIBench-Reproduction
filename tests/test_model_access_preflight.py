from types import SimpleNamespace
import pytest
from scripts.model_access_preflight import probe_configs, write_report


def test_access_error_never_archives_token_or_signed_url(tmp_path):
    def fail(*args, **kwargs):
        exc = RuntimeError('credential-secret https://redirect/?signature=secret')
        exc.response = SimpleNamespace(status_code=401)
        raise exc
    rows = probe_configs({'target': {'repo_id': 'org/model', 'revision': 'a' * 40}},
                         make_url=lambda *a, **k: 'https://huggingface.co/example',
                         fetch_metadata=fail, token='credential-secret')
    path = write_report(tmp_path, {'run_id': 'redaction-check', 'results': rows})
    saved = path.read_text(encoding='utf-8')
    assert 'credential-secret' not in saved and 'signature=' not in saved
    assert rows[0]['http_status'] == 401
    assert rows[0]['status'] == 'ACCESS_OR_NETWORK_ERROR'


def test_moving_revision_rejected_before_network():
    def forbidden(*args, **kwargs):
        pytest.fail('A non-pinned plan must not access the network')
    with pytest.raises(ValueError, match='immutable'):
        probe_configs({'target': {'repo_id': 'org/model', 'revision': 'main'}},
                      make_url=forbidden, fetch_metadata=forbidden, token=False)


def test_resolved_revision_mismatch_is_not_a_pass():
    rows = probe_configs({'target': {'repo_id': 'org/model', 'revision': 'a' * 40}},
                         make_url=lambda *a, **k: 'https://huggingface.co/example',
                         fetch_metadata=lambda *a, **k: SimpleNamespace(
                             commit_hash='b' * 40, size=100, etag='etag'), token=False)
    assert rows[0]['status'] == 'METADATA_MISMATCH_OR_INCOMPLETE'
