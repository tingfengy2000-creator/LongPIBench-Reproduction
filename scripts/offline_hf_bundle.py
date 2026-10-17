"""Download or offline-verify the three original HF models for file transfer.

Download must run under a collaborator's own legitimate access and applicable
redistribution terms. Does not change any experiment configuration or load models.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_public_models import IntegrityError, verify_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle-dir', type=Path, default=ROOT / 'models/offline-bundle')
    parser.add_argument('--roles', nargs='+', choices=['target', 'detector_base', 'helper'],
                        default=['target', 'detector_base', 'helper'])
    parser.add_argument('--download', action='store_true', help='Otherwise verify offline only')
    args = parser.parse_args()
    manifest_path = ROOT / 'configs/offline_transfer_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    lock = json.loads((ROOT / 'configs/upstream_lock.json').read_text(encoding='utf-8'))
    models = {model['role']: model for model in manifest['hf_models']}
    roles = list(dict.fromkeys(args.roles))
    # Validate the full transfer plan before any network or file operation.
    for role, model in models.items():
        fixed = lock['model_snapshots_observed_at_audit'][role]
        if model['repo_id'] != fixed['repo_id'] or model['revision'] != fixed['revision']:
            raise ValueError('Offline model differs from the original upstream lock')
        if model['bundle_subdir'] != 'hf/' + role:
            raise ValueError('Unsafe bundle subdirectory')
        for item in model['files']:
            name = item['filename']
            if PurePosixPath(name).name != name or name in {'.', '..'} or '\\' in name or ':' in name:
                raise ValueError('Unsafe filename')
    if args.download:
        from huggingface_hub import snapshot_download
    root = args.bundle_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    report = {'schema_version': 1, 'run_id': datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
              + '-offline-hf-' + uuid.uuid4().hex[:8],
              'mode': 'download_and_verify' if args.download else 'offline_verify_only',
              'transfer_manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              'model_load_verified': False, 'formal_inference_executed': False, 'results': []}
    for role in roles:
        model = models[role]
        folder = root / model['bundle_subdir']
        row = {'role': role, 'repo_id': model['repo_id'], 'revision': model['revision'],
               'folder': str(folder), 'files': []}
        try:
            # Refuse to replace any completed file whose bytes differ from the lock.
            for item in model['files']:
                if (folder / item['filename']).exists():
                    verify_file(folder / item['filename'], item)
            if args.download and any(not (folder / item['filename']).exists() for item in model['files']):
                print('Downloading ' + role + ' @ ' + model['revision'], flush=True)
                snapshot_download(repo_id=model['repo_id'], revision=model['revision'],
                                  local_dir=str(folder), allow_patterns=[item['filename'] for item in model['files']],
                                  max_workers=2, endpoint='https://huggingface.co')
            for item in model['files']:
                row['files'].append(verify_file(folder / item['filename'], item))
            index = folder / 'model.safetensors.index.json'
            if index.exists():
                shards = set(json.loads(index.read_text(encoding='utf-8'))['weight_map'].values())
                if not shards.issubset({item['filename'] for item in model['files']}):
                    raise IntegrityError(index.name, 'Index references an unplanned shard')
            row['status'] = 'FILES_VERIFIED_NOT_MODEL_LOADED'
        except Exception as exc:
            row.update(status='FAILED', error_type=type(exc).__name__,
                       http_status=getattr(getattr(exc, 'response', None), 'status_code', None),
                       integrity_filename=exc.filename if isinstance(exc, IntegrityError) else None,
                       integrity_reason=exc.reason if isinstance(exc, IntegrityError) else None)
        report['results'].append(row)
    report['status'] = ('FILES_VERIFIED_NOT_MODEL_LOADED'
                        if all(row['status'] == 'FILES_VERIFIED_NOT_MODEL_LOADED' for row in report['results'])
                        else 'PARTIAL_OR_FAILED')
    output = root / (report['run_id'] + '.json')
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'report_path': str(output), 'status': report['status'], 'results': [
        {key: value for key, value in row.items() if key != 'files'} for row in report['results']]},
        ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'FILES_VERIFIED_NOT_MODEL_LOADED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
