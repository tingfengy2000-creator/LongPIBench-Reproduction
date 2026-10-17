"""HEAD-only access checks for pinned HF configs; no weight download or inference."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]


def probe_configs(snapshots, *, make_url, fetch_metadata, token):
    # Validate the complete plan before sending any authenticated request.
    for spec in snapshots.values():
        if not re.fullmatch(r'[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+', spec['repo_id']):
            raise ValueError('Invalid HF repo ID')
        if not re.fullmatch(r'[0-9a-f]{40}', spec['revision']):
            raise ValueError('An immutable 40-character commit is required')
    results = []
    for role, spec in snapshots.items():
        row = {'role': role, **spec, 'filename': 'config.json'}
        try:
            url = make_url(spec['repo_id'], 'config.json', revision=spec['revision'],
                           endpoint='https://huggingface.co')
            metadata = fetch_metadata(url, token=token, timeout=15)
            row.update(resolved_revision=metadata.commit_hash, size_bytes=metadata.size,
                       etag=metadata.etag)
            row['status'] = ('PASS' if metadata.commit_hash == spec['revision']
                             and isinstance(metadata.size, int) and metadata.size > 0
                             else 'METADATA_MISMATCH_OR_INCOMPLETE')
        except Exception as exc:
            # Exception strings/URLs can contain credentials or signed redirects.
            # Keep only the exception class and HTTP status, never headers/token.
            response = getattr(exc, 'response', None)
            row.update(status='ACCESS_OR_NETWORK_ERROR', error_type=type(exc).__name__,
                       http_status=getattr(response, 'status_code', None))
        results.append(row)
    return results


def write_report(root, report):
    folder = root / 'coordination/returns' / report['run_id']
    folder.mkdir(parents=True, exist_ok=False)
    with (folder / 'model_access.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    return folder / 'model_access.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-id', default='R0-5090-005')
    parser.add_argument('--expected-host', default='DESKTOP-B5PNBNC')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', args.task_id):
        parser.error('Invalid task ID')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    report = {'schema_version': 1, 'task_id': args.task_id,
              'run_id': stamp + '-model-access-' + uuid.uuid4().hex[:8],
              'hostname': platform.node(), 'expected_host': args.expected_host,
              'timestamp_utc': datetime.now(timezone.utc).isoformat(),
              'phase': 'R0_CONFIG_ACCESS_ONLY', 'weight_download_executed': False,
              'model_load_verified': False, 'formal_inference_executed': False,
              'disk_free_bytes_at_repo': shutil.disk_usage(ROOT).free,
              'scope': 'Config HEAD access only; not weight access, download speed or full R0 acceptance'}
    head = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
                          capture_output=True, text=True, timeout=15)
    report['git_head'] = head.stdout.strip() if head.returncode == 0 else None
    if report['hostname'].casefold() != args.expected_host.casefold():
        report.update(status='BLOCKED_WRONG_HOST', results=[])
    else:
        from huggingface_hub import get_hf_file_metadata, get_token, hf_hub_url
        token = get_token()
        report['local_hf_credential_present'] = bool(token)
        lock = json.loads((ROOT / 'configs/upstream_lock.json').read_text(encoding='utf-8'))
        report['results'] = probe_configs(lock['model_snapshots_observed_at_audit'],
                                        make_url=hf_hub_url,
                                        fetch_metadata=get_hf_file_metadata,
                                        token=token if token else False)
        report['status'] = ('CONFIG_ACCESS_PASS_NOT_MODEL_ACCEPTANCE'
                            if all(row['status'] == 'PASS' for row in report['results'])
                            and report['results'] else 'BLOCKED_CONFIG_ACCESS')
    path = write_report(ROOT, report)
    print(json.dumps({'return_path': path.relative_to(ROOT).as_posix(), **report},
                     ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'CONFIG_ACCESS_PASS_NOT_MODEL_ACCEPTANCE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
