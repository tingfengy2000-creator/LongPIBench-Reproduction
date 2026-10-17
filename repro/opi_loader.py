"""Load pinned OPI core without executing its SDK-heavy package initializers.

The ONLY source transformation is the documented absolute-to-relative import
in PromptLocate.py. No segmentation, search, recovery, scoring or model code
is replaced. Actual model construction still needs torch/transformers/PEFT/
bitsandbytes/spaCy and weight access, and is NOT validated by import-only tests.
"""
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = 'repro._pinned_opi'
OLD_IMPORT = 'from OpenPromptInjection.apps.DataSentinelDetector import DataSentinelDetector'
NEW_IMPORT = 'from .DataSentinelDetector import DataSentinelDetector'


@dataclass(frozen=True)
class OPICore:
    DataSentinelDetector: type
    PromptLocate: type
    provenance: dict


def validate_sources(checkout, manifest):
    base = Path(checkout) / 'OpenPromptInjection'
    if manifest.get('hash_policy') != 'CRLF_to_LF':
        raise ValueError('Unsupported source hash policy')
    for relative, expected in manifest['files'].items():
        path = base / relative
        actual = hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
        if actual != expected:
            raise ValueError('Pinned OPI source differs: ' + relative)
    return base


def load_opi_core(checkout=None):
    """Call explicitly in a prepared GPU environment; does not load weights."""
    checkout = Path(checkout or ROOT / 'upstream/Open-Prompt-Injection').resolve()
    manifest = json.loads((ROOT / 'configs/opi_core_sources.json').read_text(encoding='utf-8'))
    base = validate_sources(checkout, manifest)
    loaded = sys.modules.get(NAMESPACE)
    if loaded is not None:
        if Path(loaded.__file__) != base:
            raise RuntimeError('A different OPI checkout is already loaded')
        if hasattr(loaded, '_core'):
            return loaded._core
        raise RuntimeError('OPI import is already in progress')
    created = []

    def package(name, path):
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        module.__file__ = str(path)
        sys.modules[name] = module
        created.append(name)
        return module

    def module(name, relative, transform=False):
        path = base / relative
        spec = importlib.util.spec_from_file_location(name, path)
        instance = importlib.util.module_from_spec(spec)
        sys.modules[name] = instance
        created.append(name)
        if transform:
            source = path.read_text(encoding='utf-8')
            if source.count(OLD_IMPORT) != 1:
                raise ValueError('Expected exactly one known absolute OPI import')
            exec(compile(source.replace(OLD_IMPORT, NEW_IMPORT), str(path), 'exec'), instance.__dict__)
        else:
            spec.loader.exec_module(instance)
        return instance

    try:
        root_package = package(NAMESPACE, base)
        models = package(NAMESPACE + '.models', base / 'models')
        package(NAMESPACE + '.apps', base / 'apps')
        module(NAMESPACE + '.models.Model', 'models/Model.py')
        qlora = module(NAMESPACE + '.models.QLoraModel', 'models/QLoraModel.py')
        models.QLoraModel = qlora.QLoraModel
        detector = module(NAMESPACE + '.apps.DataSentinelDetector', 'apps/DataSentinelDetector.py')
        locator = module(NAMESPACE + '.apps.PromptLocate', 'apps/PromptLocate.py', transform=True)
        result = OPICore(detector.DataSentinelDetector, locator.PromptLocate,
                         {'upstream_commit': manifest['upstream_commit'], 'source_hashes': manifest['files'],
                          'source_hash_policy': manifest['hash_policy'],
                          'runtime_namespace': NAMESPACE, 'source_root': str(base),
                          'import_transform': {'before': OLD_IMPORT, 'after': NEW_IMPORT},
                          'method_behavior_modified': False, 'gpu_load_verified': False})
        root_package._core = result
        return result
    except BaseException:
        for name in reversed(created):
            sys.modules.pop(name, None)
        raise
