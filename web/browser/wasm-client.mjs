// SPDX-License-Identifier: Apache-2.0
import {DIRECTIONS, validateBoard} from './game.mjs';

export async function createSolver(factory) {
  const module = await factory();
  const cells = module._malloc(16), output = module._malloc(16);
  const values = module._malloc(32), stats = module._malloc(32);
  if (!cells || !output || !values || !stats) throw new Error('无法分配求解器内存');
  function encode(board) {
    validateBoard(board);
    // Re-read the view: native calls may grow WebAssembly linear memory.
    module.HEAPU8.set(board.map(v => v ? Math.log2(v) : 0), cells);
  }
  function move(board, direction) {
    if (!DIRECTIONS.includes(direction)) throw new Error('未知方向');
    encode(board);
    const changed = module._ai_move(cells, DIRECTIONS.indexOf(direction), output);
    if (changed < 0) throw new Error('原生移动失败');
    return {board: [...module.HEAPU8.slice(output, output + 16)].map(r => r ? 2 ** r : 0), changed: Boolean(changed)};
  }
  function choose(board, options = {}) {
    const {budget_ms = 100, max_depth = 8, cutoff = 0.0001, target = 65536} = options;
    if (!Number.isInteger(budget_ms) || budget_ms < 1 || budget_ms > 60000 ||
        !Number.isInteger(max_depth) || max_depth < 1 || max_depth > 12 ||
        !Number.isFinite(cutoff) || cutoff < 1e-8 || cutoff > 0.01 ||
        !Number.isInteger(target) || target < 4 || target > 2 ** 30 || (target & (target - 1))) throw new Error('求解参数无效');
    encode(board);
    const direction = module._ai_choose(cells, budget_ms, max_depth, cutoff, Math.log2(target), values, stats);
    if (direction < -1) throw new Error('求解器拒绝棋盘');
    const memory = new DataView(module.HEAPU8.buffer);
    const scores = DIRECTIONS.map((_, i) => memory.getFloat64(values + i * 8, true));
    const counters = Array.from({length: 4}, (_, i) => Number(memory.getBigUint64(stats + i * 8, true)));
    return {direction: direction < 0 ? null : DIRECTIONS[direction],
      values: Object.fromEntries(DIRECTIONS.map((d, i) => [d, scores[i] > -1e12 ? scores[i] : null])),
      nodes: counters[0], cache_hits: counters[1], depth: counters[2], elapsed_ms: counters[3] / 1000};
  }
  move(Array(16).fill(0), 'left'); // Initialize lookup tables before reporting ready.
  return {choose, move, dispose() { [cells, output, values, stats].forEach(p => module._free(p)); }};
}
