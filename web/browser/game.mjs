// SPDX-License-Identifier: Apache-2.0
export const DIRECTIONS = ['up', 'down', 'left', 'right'];
export const PROFILES = {
  fast: {budget_ms: 10, max_depth: 5, cutoff: 0.0001},
  balanced: {budget_ms: 100, max_depth: 8, cutoff: 0.0001},
  deep: {budget_ms: 500, max_depth: 10, cutoff: 0.00003},
};

export function validateBoard(board) {
  if (!Array.isArray(board) || board.length !== 16 || board.some(v =>
    !Number.isInteger(v) || v < 0 || v > 2 ** 30 || (v !== 0 && (v < 2 || (v & (v - 1)) !== 0)))) {
    throw new Error('棋盘必须是 16 个空格或合法的 2 的幂');
  }
}

export function slide(board, direction) {
  validateBoard(board);
  if (!DIRECTIONS.includes(direction)) throw new Error('未知方向');
  const result = [...board];
  let gained = 0;
  for (let line = 0; line < 4; line++) {
    const ids = Array.from({length: 4}, (_, i) =>
      direction === 'left' || direction === 'right' ? line * 4 + i : i * 4 + line);
    if (direction === 'right' || direction === 'down') ids.reverse();
    const values = ids.map(i => board[i]).filter(Boolean), merged = [];
    for (let i = 0; i < values.length; i++) {
      if (i + 1 < values.length && values[i] === values[i + 1]) {
        merged.push(values[i] * 2); gained += values[i] * 2; i++;
      } else merged.push(values[i]);
    }
    ids.forEach((index, i) => { result[index] = merged[i] || 0; });
  }
  return {board: result, gained, changed: result.some((v, i) => v !== board[i])};
}

// All arithmetic is modulo 2^32. Integer sampling uses rejection to avoid
// modulo bias, for both empty-square selection and the 9:1 tile distribution.
export class Random {
  constructor(seed) { this.state = seed >>> 0; }
  next() {
    this.state = (this.state + 0x6d2b79f5) >>> 0;
    let t = this.state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return (t ^ (t >>> 14)) >>> 0;
  }
  integer(n) {
    const limit = Math.floor(2 ** 32 / n) * n;
    let value;
    do { value = this.next(); } while (value >= limit);
    return value % n;
  }
}

export function newSeed() { return crypto.getRandomValues(new Uint32Array(1))[0]; }

export class Game {
  constructor(seed = newSeed(), target = 65536) {
    if (!Number.isInteger(seed) || seed < 0 || seed > 0xffffffff) throw new Error('种子必须为 32 位无符号整数');
    if (!Number.isInteger(target) || target < 4 || target > 2 ** 30 || (target & (target - 1))) throw new Error('目标无效');
    this.seed = seed; this.target = target; this.rng = new Random(seed);
    this.board = Array(16).fill(0); this.score = 0; this.moves = 0; this.history = [];
    this.spawn(); this.spawn(); this.initial = [...this.board];
  }
  spawn() {
    const empty = this.board.map((v, i) => v === 0 ? i : -1).filter(i => i >= 0);
    if (!empty.length) return null;
    const index = empty[this.rng.integer(empty.length)], value = this.rng.integer(10) < 9 ? 2 : 4;
    this.board[index] = value;
    return {index, value};
  }
  get won() { return Math.max(...this.board) >= this.target; }
  get over() { return !DIRECTIONS.some(d => slide(this.board, d).changed); }
  step(direction) {
    const next = slide(this.board, direction);
    if (!next.changed) return false;
    this.board = next.board; this.score += next.gained; this.moves++;
    this.history.push({direction, spawn: this.spawn()});
    return true;
  }
  export() {
    return {version: 2, runtime: 'browser-wasm', rng: 'mulberry32-rejection-v1',
      seed: this.seed, target: this.target, initial: [...this.initial], board: [...this.board],
      score: this.score, moves: this.moves, max_tile: Math.max(...this.board),
      won: this.won, over: this.over, history: this.history.map(r => ({direction: r.direction, spawn: {...r.spawn}}))};
  }
  static restore(data) {
    if (data?.version !== 2 || data.runtime !== 'browser-wasm' || data.rng !== 'mulberry32-rejection-v1' || !Array.isArray(data.history)) {
      throw new Error('不支持的浏览器存档格式');
    }
    if (data.history.length > 200000) throw new Error('存档步数超出支持范围');
    const game = new Game(data.seed, data.target);
    if (JSON.stringify(game.initial) !== JSON.stringify(data.initial)) throw new Error('初始棋盘与种子不一致');
    for (const record of data.history) {
      if (!game.step(record.direction)) throw new Error('存档含无效移动');
      const spawned = game.history.at(-1).spawn;
      if (!record.spawn || spawned.index !== record.spawn.index || spawned.value !== record.spawn.value) {
        throw new Error('存档随机落子不一致');
      }
    }
    const actual = game.export();
    for (const key of ['board', 'score', 'moves', 'max_tile', 'won', 'over']) {
      if (JSON.stringify(actual[key]) !== JSON.stringify(data[key])) throw new Error(`存档 ${key} 与重放不一致`);
    }
    return game;
  }
}
