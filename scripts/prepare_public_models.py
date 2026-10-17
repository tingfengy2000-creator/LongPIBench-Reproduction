"""Download only pinned Mistral/GPT-2 files and verify official blob hashes.

No Llama access, adapter selection, model loading or benchmark inference.
Without --download, validate and print the local plan only.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]


class IntegrityError(ValueError):
    def __init__(self, filename, reason):
        super().__init__(reason)
        self.filename = filename
        self.reason = reason


def validate_plan(plan, lock):
    models = plan['models']
    if {model['role'] for model in models} != {'helper', 'detector_base'} or len(models) != 2:
        raise ValueError('Plan must contain only GPT-2 and detector base')
    for model in models:
        fixed = lock['model_snapshots_observed_at_audit'][model['role']]
        if model['repo_id'] != fixed['repo_id'] or model['revision'] != fixed['revision']:
            raise ValueError('Model plan differs from upstream lock')
        if not re.fullmatch(r'[0-9a-f]{40}', model['revision']):
            raise ValueError('Immutable revision required')
        seen = set()
        for item in model['files']:
            name = item['filename']
            if (PurePosixPath(name).name != name or name in {'.', '..'}
                    or '\\' in name or ':' in name or name in seen):
                raise ValueError('Unsafe or repeated filename')
            seen.add(name)
            if type(item['size_bytes']) is not int or item['size_bytes'] < 0:
                raise ValueError('Invalid expected file size')
            digest = item.get('lfs_sha256') or item['git_blob_sha1']
            length = 64 if item.get('lfs_sha256') else 40
            if not re.fullmatch('[0-9a-f]{' + str(length) + '}', digest):
                raise ValueError('Expected official file hash required')
        if 'config.json' not in seen or not any(n.endswith('.safetensors') for n in seen):
            raise ValueError('Config and safetensors required')
    return {model['role']: model for model in models}


def verify_file(path, item):
    size = path.stat().st_size
    if size != item['size_bytes']:
        raise IntegrityError(item['filename'], 'File size mismatch; refusing replacement')
    sha256 = hashlib.sha256()
    git_sha1 = hashlib.sha1(('blob ' + str(size) + '\0').encode('ascii'))
    with path.open('rb') as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            sha256.update(chunk)
            git_sha1.update(chunk)
    expected = item.get('lfs_sha256') or item['git_blob_sha1']
    actual = sha256.hexdigest() if item.get('lfs_sha256') else git_sha1.hexdigest()
    if actual != expected:
        raise IntegrityError(item['filename'], 'File hash mismatch; refusing replacement')
    return {'filename': item['filename'], 'size_bytes': size, 'sha256': sha256.hexdigest(),
            'verified_against': 'lfs_sha256' if item.get('lfs_sha256') else 'git_blob_sha1'}


def download_one(model, cache, fetch_file):
    snapshot = cache / ('models--' + model['repo_id'].replace('/', '--')) / 'snapshots' / model['revision']
    verified = []
    for item in model['files']:
        expected_path = snapshot / item['filename']
        if expected_path.exists():
            # A mismatched existing file must not be overwritten by the downloader.
            verified.append(verify_file(expected_path, item))
            continue
        downloaded = Path(fetch_file(repo_id=model['repo_id'], filename=item['filename'],
                                    revision=model['revision'], cache_dir=str(cache),
                                    endpoint='https://huggingface.co', token=False))
        if downloaded.absolute() != expected_path.absolute():
            raise IntegrityError(item['filename'], 'Unexpected cache snapshot path')
        verified.append(verify_file(downloaded, item))
    index_path = snapshot / 'model.safetensors.index.json'
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding='utf-8'))
        known = {item['filename'] for item in model['files']}
        if not set(index['weight_map'].values()).issubset(known):
            raise IntegrityError(index_path.name, 'Safetensors index references an unplanned shard')
    return {'role': model['role'], 'repo_id': model['repo_id'], 'revision': model['revision'],
            'snapshot_path': str(snapshot), 'files': verified, 'status': 'FILES_VERIFIED_NOT_MODEL_LOADED'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--roles', nargs='+', choices=['helper', 'detector_base'],
                        default=['helper', 'detector_base'])
    args = parser.parse_args()
    plan_path = ROOT / 'configs/public_model_files.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8-sig'))
    lock = json.loads((ROOT / 'configs/upstream_lock.json').read_text(encoding='utf-8'))
    models = validate_plan(plan, lock)
    roles = list(dict.fromkeys(args.roles))
    planned_bytes = sum(item['size_bytes'] for role in roles for item in models[role]['files'])
    report = {'schema_version': 1, 'task_id': 'R0-5090-006',
              'run_id': datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-public-models-' + uuid.uuid4().hex[:8],
              'hostname': platform.node(), 'formal_inference_executed': False,
              'model_load_verified': False, 'weight_download_requested': args.download,
              'file_plan_sha256': hashlib.sha256(plan_path.read_bytes()).hexdigest(),
              'planned_bytes': planned_bytes, 'disk_free_bytes': shutil.disk_usage(ROOT).free,
              'scope': 'Public base/helper files only; DataSentinel checkpoint remains unknown', 'results': []}
    if not args.download:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    stamp = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
                           capture_output=True, text=True, timeout=15)
    report['git_head'] = stamp.stdout.strip() if stamp.returncode == 0 else None
    if platform.node().casefold() != 'desktop-b5pnbnc':
        report['status'] = 'BLOCKED_WRONG_HOST'
    elif report['disk_free_bytes'] < planned_bytes + 3 * 1024**3:
        report['status'] = 'BLOCKED_DISK_HEADROOM'
    else:
        from huggingface_hub import hf_hub_download
        cache = ROOT / 'models/hf-cache'
        for role in roles:
            print('Preparing ' + role + ': ' + models[role]['revision'], flush=True)
            try:
                report['results'].append(download_one(models[role], cache, hf_hub_download))
            except Exception as exc:
                report['results'].append({'role': role, 'status': 'FAILED',
                    'error_type': type(exc).__name__,
                    'integrity_error_filename': exc.filename if isinstance(exc, IntegrityError) else None,
                    'integrity_error_reason': exc.reason if isinstance(exc, IntegrityError) else None,
                    'http_status': getattr(getattr(exc, 'response', None), 'status_code', None)})
        report['status'] = ('FILES_VERIFIED_NOT_MODEL_LOADED'
                            if all(row['status'] == 'FILES_VERIFIED_NOT_MODEL_LOADED'
                                   for row in report['results']) else 'PARTIAL_OR_FAILED')
    folder = ROOT / 'coordination/returns' / report['run_id']
    folder.mkdir(parents=True, exist_ok=False)
    with (folder / 'public_models.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'return_path': (folder / 'public_models.json').relative_to(ROOT).as_posix(),
                      'status': report['status'], 'results': [
                          {key: value for key, value in row.items() if key != 'files'}
                          for row in report['results']]}, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'FILES_VERIFIED_NOT_MODEL_LOADED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
