# 2048 → 65536

一个标准 4 × 4 2048 自动挑战器。C++ Expectimax 负责决策，提供浏览器独立运行和 Python 本地服务两种方式。默认目标是 **65536**；失败可自动开新局，达到目标自动停止。原创代码与文档以 **Apache-2.0** 开源，上游 MIT 及运行库声明完整保留。

**[打开在线版 →](https://bingingingin.github.io/2048-ai/)** · [Apache-2.0 许可](LICENSE) · [验证记录](VALIDATION.md)

完整技术说明见 [全部原理与实现逻辑](PRINCIPLES_AND_IMPLEMENTATION.md)，涵盖编码、移动查表、评估公式、Expectimax、时间预算、缓存、自动控制、存档和前后端实现。

## 在线使用

打开 [GitHub Pages 在线版](https://bingingingin.github.io/2048-ai/)，等待“浏览器引擎在线”，点击“开始自动运行”，无需安装 Python 或编译器。同一份 C++ 源码编译成 WebAssembly，在 Web Worker 中搜索，界面保持可操作。

在线版在当前设备计算，每 50 步及暂停、重开、终局、页面隐藏时保存到浏览器。关闭页面会停止；重新打开后恢复为暂停状态。后台标签页可能被浏览器限速，清除站点数据会删除存档，建议及时“导出对局”。同一浏览器请只在一个标签页运行，避免多个标签页覆盖共同的存档。这里不提供服务器持续托管对局。

在线版使用明确标识的 `version: 2` 回放与 Mulberry32 随机数，本地版是 `version: 1` 与 Python Random；两者都采用均匀空位和 90% / 10% 落子规则，**相同种子不代表跨版本相同对局**。两种导出均可用 `python verify_replay.py <文件>` 独立验证。

## 本地启动

Windows 下双击 `start.cmd`，或在项目目录运行：

```powershell
python server.py
```

打开 <http://127.0.0.1:2048>，点击“开始自动运行”。关闭网页不会中断后台对局；关闭服务会结束运行并保存。再次启动会恢复棋盘，保持暂停，点击开始即可继续。

需要 Python 3.10+ 和支持 C++17 的 `g++` / `clang++`。**没有第三方 Python 包或前端包依赖**。首次启动自动编译 `build/solver.dll`（Linux 为 `libsolver.so`）。当前 Windows 环境已编译和验证；其他平台尚未实测。

若修改了 C++ 源码，先停止所有使用求解器的进程，再运行 `python build.py --force`。可通过 `CXX` 指定编译器。端口被占用时运行 `python server.py --port 2049`。

## 自动运行

- **均衡**：每步最多约 100 ms，最多 8 层。
- **深思**：每步最多约 500 ms，最多 10 层，并降低概率截断阈值。
- **快速**：每步最多约 10 ms，最多 5 层，适合观察运行过程。
- AI 单步、暂停、方向键或滑动接管、自动重试开关、对局导出。
- 本地服务每 50 步以及暂停、重开、终局时保存。异常退出最多丢失当前局最近 49 步；正常 Ctrl+C 退出保存当前状态。
- 本地存档位于 `runs/live/session.json`，历史完整对局位于同一目录。新开一局会先归档当前对局。在线版使用浏览器存储，仅保留当前完整存档、最近一份归档及最多 100 条结果摘要。

思考时间是软预算，按搜索节点间隔检查。只使用**四个方向均完成评估**的最后一轮搜索；预算极小时退回合法的一步评估，不采用偏向先搜索方向的不完整结果。“完整搜索 N 层”表示完成该深度的一轮概率截断搜索，不表示所有概率分支均展开至 N 层。

## 命令行批量挑战

不打开浏览器也可以运行，使用本地版的规则执行器与随机数：

```powershell
# 从指定种子开始运行 10 局
python autoplay.py --games 10 --seed 65536 --budget-ms 100

# 一直重试，首次达到 65536 时退出；Ctrl+C 可提前停止并保留记录
python autoplay.py --games 0 --until-target --budget-ms 500 --depth 10 --cutoff 0.00003

# 更短的功能验证，目标为 2048
python autoplay.py --games 1 --target 2048 --budget-ms 10 --output runs/quick
```

默认单局步数上限为 200,000，可用 `--max-moves` 修改。结果保存在 `runs/batch/summary.json`，每局完整记录为 `seed-<种子>.json`。不同批次请使用不同的 `--output`，避免覆盖同种子的旧结果。

实际使用时间预算会受到 CPU 负载影响，同一种子不保证选出完全相同的行动序列；已导出的**行动与落子记录**则可以精确重放。随机种子只用于复现落子，不向求解器暴露未来随机数。

## 接入自己的游戏

```python
from solver import Solver

solver = Solver()  # 复用实例，不要每一步重新加载
board = [
    2, 4, 8, 16,
    0, 2, 4, 8,
    0, 0, 2, 4,
    0, 0, 0, 2,
]
decision = solver.choose(board, budget_ms=100, max_depth=8)
print(decision['direction'])  # up / down / left / right；无合法移动时为 None
print(decision['depth'], decision['nodes'], decision['elapsed_ms'])
```

棋盘按行排列，空格填 `0`，其他格子填写实际方块值。`Solver.move()` 仅移动与合并，不生成新方块；游戏环境应在一次**有效移动后**生成随机方块。

本项目带有自己的游戏，未接入第三方网站的页面控制。要驱动已有网页，可以调用上述接口，再由网页适配器读取棋盘、执行方向和识别新方块。

## 算法与目标边界

参考 [nneonneo/2048-ai](https://github.com/nneonneo/2048-ai) 的行查表与 Expectimax。玩家节点选择评分最高的合法方向；机会节点在每个空格分别考虑生成 2 和 4，概率为 90% 和 10%。评估考虑空格、可合并链、行列单调性和方块等级。

本项目处理了面向 65536 的几个关键问题：

1. **每格 5 位、每行 20 位**，不再使用参考源码的 4 位饱和编码，正确计算 `32768 + 32768 = 65536`。
2. 区分非法方向、终局惩罚和可为负的棋盘评估，避免高等级棋盘被错误判成无路可走，也避免过大的死亡惩罚淹没正常策略。
3. 迭代加深、时间预算、置换缓存。缓存核对完整棋盘、深度和累计概率，避免复用不同截断条件下的评估值。
4. 标准随机规则与可验证记录，不修改落子概率、不回滚挑选落子、不预览未来随机数。
5. 可立即合成目标时优先执行；接近目标时将达成目标作为搜索终点。

根据项目作者截至 **2026-09-11** 对已有全部**无撤回测试**的汇总观察：

| 模式 | 观察到的最大方块表现 |
| --- | --- |
| 快速（10 ms / 步，最多 5 层） | 通常结束在 **8192 或 16384** |
| 深思（500 ms / 步，最多 10 层） | **通常能稳定到达 32768** |

这是作者的实际使用反馈，未附总局数、逐局种子和完整记录，因此不换算为成功率，也不表示每局必达。此反馈来自此前本地版本，不直接作为新上线 WebAssembly 版本的成绩。仓库另有 3 局可核查的测试摘要（10 ms / 步、深度上限 **8**，与快速预设不同），分别达到 16384、16384、8192。**目前没有提供从空盘达到 65536 的成功对局证据。** 详细来源与边界见 [VALIDATION.md](VALIDATION.md) 和 [使用观察数据](validation/user-observations.json)。

## 验证

```powershell
python -m unittest discover -s tests -v
python verify_replay.py runs/batch/seed-65536.json
node --test tests/browser.test.mjs
```

测试包括 83,521 种行布局穷举、随机整盘四方向与独立规则实现对照、高位合并、合并计分、合法行动、无效移动不落子、记录重放、暂停竞态、续存、自动重试与目标停止。

## 网页构建与部署

GitHub Pages 适合这个无需后端的浏览器版本，并能直接使用当前公共仓库的 Actions 发布。工作流 [pages.yml](.github/workflows/pages.yml) 在 `main` 更新时测试、编译并部署，站点使用相对资源路径，支持 `/2048-ai/` 子路径。

如需本地构建，安装并激活 [Emscripten SDK](https://emscripten.org/docs/getting_started/downloads.html) **4.0.15**，在其环境中执行（还需要 Python 3.10+、Node.js 22+）：

```sh
python build_site.py
node --test tests/wasm.test.mjs
python -m http.server 2049 --directory dist
```

构建结果位于 `dist/`，包含单文件 `solver.mjs`（内嵌 WebAssembly）、网页、许可证和 `build-info.json`。不要直接以 `file://` 打开模块页面。`dist/` 不提交到 Git，由 Actions 构建后发布。WebAssembly 规则对照、超时与重放测试通过后才进入部署步骤。

## 文件

| 文件 | 职责 |
| --- | --- |
| `engine/solver.cpp` | C++ 查表、评估、Expectimax 搜索 |
| `solver.py` | Python / ctypes 调用接口 |
| `game.py` | 标准规则、随机落子与对局重放 |
| `server.py` | 本地 HTTP 服务、自动运行控制与存档 |
| `autoplay.py` | 无界面批量运行 |
| `web/` | 实时棋盘与控制界面 |
| `web/browser/` | 在线版规则、工作线程、WASM 调用与浏览器存档 |
| `browser_replay.py` | 用独立 Python 规则核验在线版记录 |
| `build_site.py`、`.github/workflows/pages.yml` | 静态站点构建、回归与 GitHub Pages 发布 |
| `tests/test_engine.py` | 引擎及自动控制回归 |

## 开源许可

本项目原创代码与文档以 [Apache License 2.0](LICENSE) 发布，归属说明见 [NOTICE](NOTICE)。改编自 nneonneo/2048-ai 的部分继续保留 MIT 许可；WebAssembly 中的 Emscripten、C/C++ 运行库适用各自许可。完整说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，在线构建另附 `licenses/` 原始许可文本。
