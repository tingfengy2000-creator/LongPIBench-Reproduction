"""Verify official adapter ZIPs and a spaCy wheel without extracting or executing them."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest_stream(stream):
    result = hashlib.sha256()
    while chunk := stream.read(8 * 1024 * 1024):
        result.update(chunk)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-dir', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'configs/offline_transfer_manifest.json').read_text(encoding='utf-8'))
    results = []
    for pack in manifest['aux_archives']:
        path = args.download_dir / pack['filename']
        row = {'filename': path.name, 'source_url': pack['url'], 'files': [],
               'author_published_sha256_available': False}
        try:
            if path.stat().st_size != pack['observed_size_bytes']:
                raise ValueError('Archive size differs from audit snapshot')
            with path.open('rb') as stream:
                row['archive_sha256_first_observed'] = digest_stream(stream)
            with zipfile.ZipFile(path) as archive:
                for item in pack['inference_files']:
                    info = archive.getinfo(item['name'])
                    if info.file_size != item['bytes']:
                        raise ValueError('Adapter file size differs from audit')
                    with archive.open(info) as stream:
                        # Reading to EOF also verifies ZIP member CRC.
                        sha256 = digest_stream(stream)
                    if item['name'].endswith('/adapter_config.json'):
                        actual = json.loads(archive.read(info))
                        if actual != pack['adapter_configs'][item['name']]:
                            raise ValueError('Adapter config differs from audit')
                    row['files'].append({'member': item['name'], 'size_bytes': info.file_size,
                                         'sha256_first_observed': sha256, 'zip_crc_verified': True})
            row['status'] = 'SOURCE_SIZE_CONFIG_AND_CRC_CHECKED'
        except Exception as exc:
            row.update(status='FAILED', error_type=type(exc).__name__)
        results.append(row)
    wheel = manifest['spacy_model']
    path = args.download_dir / wheel['filename']
    row = {'filename': path.name, 'source_url': wheel['url'],
           'author_published_sha256_available': bool(wheel.get('digest'))}
    try:
        if path.stat().st_size != wheel['size_bytes']:
            raise ValueError('Wheel size differs from official release metadata')
        with path.open('rb') as stream:
            sha256 = digest_stream(stream)
        row['sha256_first_observed'] = sha256
        if wheel.get('digest') and wheel['digest'] != 'sha256:' + sha256:
            raise ValueError('Wheel digest mismatch')
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError('Wheel CRC error')
            metadata = archive.read('en_core_web_sm-3.8.0.dist-info/METADATA').decode('utf-8')
            if 'Version: 3.8.0' not in metadata.splitlines():
                raise ValueError('Unexpected spaCy model version')
        row['status'] = 'SOURCE_SIZE_VERSION_AND_CRC_CHECKED'
    except Exception as exc:
        row.update(status='FAILED', error_type=type(exc).__name__)
    results.append(row)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-aux-downloads-' + uuid.uuid4().hex[:8]
    report = {'schema_version': 1, 'task_id': 'R0-5090-007', 'run_id': run_id,
              'model_load_verified': False, 'formal_inference_executed': False,
              'scope': 'Observed hashes are not independently author-published digests; no extraction or pickle loading',
              'download_dir': str(args.download_dir.resolve()), 'results': results,
              'status': 'FILES_CHECKED_NOT_MODEL_LOADED' if all(row['status'] != 'FAILED' for row in results) else 'PARTIAL_OR_FAILED'}
    folder = ROOT / 'coordination/returns' / run_id
    folder.mkdir(parents=True, exist_ok=False)
    output = folder / 'aux_downloads.json'
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'return_path': output.relative_to(ROOT).as_posix(), 'status': report['status'],
                      'results': results}, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'FILES_CHECKED_NOT_MODEL_LOADED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
