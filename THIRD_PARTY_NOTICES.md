# Third-party notices

Original contributions to this repository are licensed under Apache-2.0;
see [LICENSE](LICENSE) and [NOTICE](NOTICE). The third-party portions below
retain their own licenses. The root license does not replace their notices.

## nneonneo/2048-ai

- Source: https://github.com/nneonneo/2048-ai
- Inspected commit: `41e298f4571a9505e421e3a19af7a1cb372a368c`
- License: MIT
- Used in: `engine/solver.cpp`
- Scope: Expectimax design, lookup-table approach, row monotonicity / empty-cell / merge / rank-sum heuristic and its weights. The 80-bit board layout, move tables, iterative time-bounded search, probability-sensitive cache, Python integration, standard-rule game runner, replay format, and UI are implemented for this project.
- The upstream source uses four bits per cell and saturates `32768 + 32768` at `32768`. This project uses five bits per cell and preserves the resulting `65536` tile.

The following notice applies to the adapted portions:

MIT License

Copyright (c) 2014-2019 Robert Xiao <nneonneo@gmail.com> and contributors.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Browser distribution: Emscripten and C/C++ runtimes

The same C++ source is compiled with **Emscripten 4.0.15** to a JavaScript /
WebAssembly module. This compiled distribution incorporates SDK runtime code:

| Component | Source | License / notice in the deployed site |
| --- | --- | --- |
| Emscripten JavaScript runtime | https://github.com/emscripten-core/emscripten/tree/4.0.15 | MIT or University of Illinois/NCSA, `licenses/EMSCRIPTEN-LICENSE.txt` |
| libc++ | Emscripten `system/lib/libcxx` | LLVM Apache-2.0 with LLVM exceptions and retained notices, `licenses/LIBCXX-LICENSE.txt` |
| libc++abi | Emscripten `system/lib/libcxxabi` | LLVM Apache-2.0 with LLVM exceptions and retained notices, `licenses/LIBCXXABI-LICENSE.txt` |
| musl libc | Emscripten `system/lib/libc/musl` | MIT and file-specific notices, `licenses/MUSL-COPYRIGHT.txt` |
| compiler-rt | Emscripten `system/lib/compiler-rt` | LLVM Apache-2.0 with LLVM exceptions and retained notices, `licenses/COMPILER-RT-LICENSE.txt` |

`build_site.py` copies these license files directly from the pinned SDK into
the published artifact. Refer to those complete notices for component-specific
copyright holders and exceptions; this table is a summary, not a substitute.
The SDK itself is a build dependency and is not committed to this repository.
