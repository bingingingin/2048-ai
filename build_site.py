"""Build the standalone GitHub Pages site using Emscripten 4.0.15."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent


def build():
    compiler = shutil.which('em++')
    if not compiler:
        raise SystemExit('Activate Emscripten 4.0.15 before building this site.')
    destination = ROOT / 'dist'
    destination.mkdir(exist_ok=True)
    shutil.copytree(ROOT / 'web', destination, dirs_exist_ok=True)
    index = destination / 'index.html'
    index.write_text(index.read_text(encoding='utf-8').replace(
        'name="2048-runtime" content="local"', 'name="2048-runtime" content="browser"'), encoding='utf-8')
    subprocess.run([compiler, str(ROOT / 'engine/solver.cpp'), '-O3', '-std=c++17',
                    '--no-entry', '-fexceptions', '-sDISABLE_EXCEPTION_CATCHING=0',
                    '-sMODULARIZE=1', '-sEXPORT_ES6=1', '-sENVIRONMENT=web,worker,node',
                    '-sALLOW_MEMORY_GROWTH=1', '-sINITIAL_MEMORY=67108864',
                    '-sFILESYSTEM=0', '-sSINGLE_FILE=1',
                    '-sEXPORTED_FUNCTIONS=["_ai_choose","_ai_move","_malloc","_free"]',
                    '-sEXPORTED_RUNTIME_METHODS=["HEAPU8"]',
                    '-o', str(destination / 'solver.mjs')], check=True)
    for name in ('LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md'):
        shutil.copyfile(ROOT / name, destination / name)
    # Redistribute the actual SDK's notices alongside its linked runtime code.
    sdk = Path(os.environ['EMSDK']) / 'upstream/emscripten'
    licenses = {
        'EMSCRIPTEN-LICENSE.txt': 'LICENSE',
        'LIBCXX-LICENSE.txt': 'system/lib/libcxx/LICENSE.TXT',
        'LIBCXXABI-LICENSE.txt': 'system/lib/libcxxabi/LICENSE.TXT',
        'MUSL-COPYRIGHT.txt': 'system/lib/libc/musl/COPYRIGHT',
        'COMPILER-RT-LICENSE.txt': 'system/lib/compiler-rt/LICENSE.TXT',
    }
    (destination / 'licenses').mkdir(exist_ok=True)
    for name, source in licenses.items():
        shutil.copyfile(sdk / source, destination / 'licenses' / name)
    (destination / '.nojekyll').touch()
    (destination / 'build-info.json').write_text(json.dumps({
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'engine_sha256': hashlib.sha256((ROOT / 'engine/solver.cpp').read_bytes()).hexdigest(),
        'emscripten': subprocess.check_output([compiler, '--version'], text=True).splitlines()[0],
    }, indent=2) + '\n', encoding='utf-8')
    print(f'Built {destination}')


if __name__ == '__main__':
    build()
