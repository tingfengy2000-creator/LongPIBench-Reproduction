"""Immutable per-attempt evidence files. No overwrite or implicit resume."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import uuid


def json_bytes(value):
    # Reject NaN/Infinity before creating any evidence file.
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode('utf-8')


class RunArchive:
    def __init__(self, root, config, *, run_kind, run_id=None):
        if run_kind not in {'debug', 'formal'}:
            raise ValueError('run_kind must be explicit: debug or formal')
        self.config = json.loads(json_bytes(config))  # detach caller-owned state
        self.config_sha256 = hashlib.sha256(json_bytes(self.config)).hexdigest()
        self.run_kind = run_kind
        self.run_id = run_id or (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:12])
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', self.run_id):
            raise ValueError('Unsafe run ID')
        self.path = Path(root) / self.run_id
        self.path.mkdir(parents=True, exist_ok=False)
        self._write('manifest.json', {'schema_version': 1, 'run_id': self.run_id,
                    'run_kind': run_kind, 'config_sha256': self.config_sha256,
                    'config': self.config, 'created_utc': datetime.now(timezone.utc).isoformat(),
                    'note': 'Manifest creation does not assert completion or valid model inference'})

    def _write(self, name, value):
        blob = json_bytes(value)
        with (self.path / name).open('xb') as stream:
            stream.write(blob)

    def write_attempt(self, *, suite, item_id, condition, attempt, evidence):
        if suite not in {'email', 'resume'} or type(item_id) is not int or not 0 <= item_id < 100:
            raise ValueError('Invalid sample identity')
        if condition not in {'no_defense', 'promptlocate'} or type(attempt) is not int or attempt < 1:
            raise ValueError('Invalid condition or attempt')
        name = f'{suite}-{item_id:03d}-{condition}-attempt-{attempt:03d}.json'
        # Identity fields cannot be overridden by the evidence payload.
        record = {'run_id': self.run_id, 'run_kind': self.run_kind,
                  'config_sha256': self.config_sha256, 'suite': suite, 'item_id': item_id,
                  'condition': condition, 'attempt': attempt, 'evidence': evidence}
        self._write(name, record)
        return self.path / name
