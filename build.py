"""Build the native solver with a local C++17 compiler; no Python packages needed."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
LIBRARY = ROOT / 'build' / ('solver.dll' if os.name == 'nt' else 'libsolver.so')

def build(force=False):
    source = ROOT / 'engine' / 'solver.cpp'
    if not force and LIBRARY.exists() and LIBRARY.stat().st_mtime >= source.stat().st_mtime:
        return LIBRARY
    compiler = os.environ.get('CXX') or shutil.which('g++') or shutil.which('clang++')
    if not compiler:
        raise RuntimeError('需要 C++17 编译器：安装 MinGW-w64 或设置 CXX 后运行 python build.py')
    LIBRARY.parent.mkdir(exist_ok=True)
    args = [compiler, '-O3', '-std=c++17', '-shared', str(source), '-o', str(LIBRARY)]
    if os.name == 'nt':
        args += ['-static', '-static-libgcc', '-static-libstdc++']
    else:
        args += ['-fPIC', '-pthread']
    subprocess.run(args, check=True)
    return LIBRARY

if __name__ == '__main__':
    print(build('--force' in sys.argv))
