"""Explicit D/E cache-path compatibility shim; frozen inference functions unchanged.

Fixes the B0-001 assumption that the parent models folder itself must be a
symlink. On5090 only its existing children are links into E. No links are moved.
No implicit retry: invoking this file is a separate task/run, preserving v1.
"""
import argparse
import os
from pathlib import Path,PurePosixPath
import platform
import sys


def allowed_cache(path):
    path=PurePosixPath(path)
    return path.is_absolute() and '..' not in path.parts and any(path.is_relative_to(PurePosixPath(root)) for root in ['/mnt/e','/mnt/d'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-root',type=Path,required=True)
    parser.add_argument('--role',choices=['prompt_guard_2','datasentinel','llama'],required=True)
    args=parser.parse_args()
    import remote_availability as original
    def configure_v2():
        assert platform.system()=='Linux' and platform.node().casefold()=='desktop-b5pnbnc'
        resolved=args.cache_root.resolve(strict=False)
        assert allowed_cache(str(resolved)),'Actual cache target must resolve within /mnt/e or /mnt/d'
        # Check the final resolved path, not the models parent or a lexical prefix.
        resolved.mkdir(parents=True,exist_ok=True)
        assert args.cache_root.resolve(strict=True)==resolved
        for key,part in [('HF_HUB_CACHE','hub'),('HF_XET_CACHE','xet'),('HF_ASSETS_CACHE','assets'),('HF_MODULES_CACHE','modules'),('TORCH_HOME','torch'),('TEMP','temp'),('TMP','temp')]:
            p=resolved/part;p.mkdir(exist_ok=True);os.environ[key]=str(p)
        return resolved
    # Only the storage preflight is replaced; original pg2/datasentinel/llama
    # functions, model constructors, precision and control strings are untouched.
    original.configure=configure_v2
    sys.argv=[sys.argv[0],'--role',args.role]
    return original.main()


if __name__=='__main__':raise SystemExit(main())
