// SPDX-License-Identifier: Apache-2.0
import {Game, PROFILES, DIRECTIONS} from './game.mjs';

const STORAGE_KEY = '2048-ai.browser.session.v2';
const ARCHIVE_KEY = '2048-ai.browser.archive.v2';

async function workerSolver() {
  const worker = new Worker(new URL('./solver.worker.mjs', import.meta.url), {type: 'module'});
  let serial = 0, failure = null;
  const pending = new Map();
  let readyResolve, readyReject;
  const ready = new Promise((resolve, reject) => { readyResolve = resolve; readyReject = reject; });
  let readyTimer = setTimeout(() => fail('引擎加载超时，请刷新重试'), 60000);
  function fail(message) {
    failure = new Error(message);
    clearTimeout(readyTimer);
    readyReject(new Error(message));
    for (const request of pending.values()) request.reject(new Error(message));
    pending.clear(); worker.terminate();
  }
  worker.onerror = event => fail(event.message || '浏览器工作线程出错');
  worker.onmessage = ({data}) => {
    if (data.ready) { clearTimeout(readyTimer); readyResolve(); return; }
    if (data.fatal) { fail(data.fatal); return; }
    const request = pending.get(data.id);
    if (!request) return;
    pending.delete(data.id);
    if (data.error) request.reject(new Error(data.error)); else request.resolve(data.result);
  };
  await ready;
  return {choose(board, options) {
    if (failure) return Promise.reject(failure);
    return new Promise((resolve, reject) => {
      const id = ++serial;
      pending.set(id, {resolve, reject});
      worker.postMessage({id, board, options});
    });
  }, close() { fail('引擎已关闭'); }};
}

export class Controller {
  constructor(solver, storage = localStorage) {
    this.solver = solver; this.storage = storage;
    this.game = new Game(); this.running = false; this.thinking = false;
    this.steps = 0; this.revision = 0; this.profile = 'balanced'; this.retry = true;
    this.attempt = 1; this.best = 0; this.results = []; this.analysis = null; this.error = null;
    this.storageWarning = null; this.started = Date.now(); this.elapsedBase = 0;
    this.inFlight = false; this.timer = null; this.disposed = false;
    try {
      const raw = storage.getItem(STORAGE_KEY);
      if (raw) {
        const data = JSON.parse(raw);
        this.game = Game.restore(data.game);
        this.profile = Object.hasOwn(PROFILES, data.profile) ? data.profile : 'balanced';
        this.retry = data.retry !== false;
        this.attempt = Number.isInteger(data.attempt) && data.attempt > 0 ? data.attempt : 1;
        this.best = Math.max(Number(data.best) || 0, ...this.game.board);
        this.results = Array.isArray(data.results) ? data.results.slice(-100).filter(r =>
          Number.isFinite(r.max_tile) && Number.isFinite(r.moves) && Number.isFinite(r.score)) : [];
        this.elapsedBase = Number(data.elapsed) || 0;
      }
    } catch (error) {
      this.storageWarning = `存档无法读取，当前使用新局：${error.message}`;
    }
  }
  state() {
    const g = this.game;
    return {board: [...g.board], score: g.score, moves: g.moves, seed: g.seed,
      max_tile: Math.max(...g.board), target: g.target, won: g.won, over: g.over,
      status: this.error ? 'error' : g.won ? 'won' : g.over ? 'gameover' : this.running ? 'running' : this.thinking || this.steps ? 'thinking' : 'paused',
      running: this.running, thinking: this.thinking, profile: this.profile, retry: this.retry,
      attempt: this.attempt, best: Math.max(this.best, ...g.board), results: this.results.slice(-8),
      analysis: this.analysis, error: this.error, storage_warning: this.storageWarning,
      elapsed: Math.round((this.elapsedBase + (Date.now() - this.started) / 1000) * 10) / 10};
  }
  save() {
    try {
      this.storage.setItem(STORAGE_KEY, JSON.stringify({game: this.game.export(), profile: this.profile,
        retry: this.retry, attempt: this.attempt, best: Math.max(this.best, ...this.game.board),
        results: this.results.slice(-100), elapsed: this.state().elapsed}));
    } catch {
      this.storageWarning = '浏览器存储空间不足或不可用，请及时导出当前对局。';
    }
  }
  archive(reason) {
    const g = this.game;
    this.best = Math.max(this.best, ...g.board);
    this.results.push({seed: g.seed, max_tile: Math.max(...g.board), score: g.score, moves: g.moves, reason});
    this.results = this.results.slice(-100);
    try { this.storage.setItem(ARCHIVE_KEY, JSON.stringify(g.export())); }
    catch { this.storageWarning = '最近对局未能保存，请导出当前对局。'; }
  }
  schedule() {
    if (this.disposed || this.timer !== null) return;
    this.timer = setTimeout(() => { this.timer = null; this.tick(); }, 0);
  }
  async tick() {
    if (this.disposed || this.inFlight || !(this.running || this.steps)) return;
    if (this.game.won) { this.running = false; this.steps = 0; this.save(); return; }
    if (this.game.over) {
      if (!(this.running && this.retry)) { this.running = false; this.steps = 0; this.save(); return; }
      this.archive('gameover'); this.game = new Game(); this.attempt++; this.revision++;
      this.analysis = null; this.started = Date.now(); this.elapsedBase = 0; this.save();
    }
    const revision = this.revision, board = [...this.game.board];
    this.thinking = true; this.inFlight = true;
    try {
      const result = await this.solver.choose(board, {...PROFILES[this.profile], target: this.game.target});
      if (revision !== this.revision || this.disposed) return;
      if (!result.direction || !this.game.step(result.direction)) throw new Error('求解器未返回合法移动');
      this.analysis = result; this.steps = Math.max(0, this.steps - 1);
      this.best = Math.max(this.best, ...this.game.board);
      if (this.game.won) { this.running = false; this.steps = 0; this.archive('won'); }
      if (this.game.moves % 50 === 0 || !this.running || this.game.over) this.save();
    } catch (error) {
      if (revision === this.revision && !this.disposed) {
        this.error = error.message; this.running = false; this.steps = 0;
      }
    } finally {
      this.thinking = false; this.inFlight = false;
      if (this.running || this.steps) this.schedule();
    }
  }
  command(action, data = {}) {
    if (action === 'start') {
      if (this.game.won || (this.game.over && !this.retry)) return this.state();
      this.running = true; this.error = null;
    } else if (action === 'pause') {
      this.running = false; this.steps = 0; this.revision++; this.save();
    } else if (action === 'step') {
      if (!this.game.won && !this.game.over && !this.thinking) {
        this.running = false; this.steps = 1; this.revision++;
      }
    } else if (action === 'move') {
      if (!DIRECTIONS.includes(data.direction)) throw new Error('未知方向');
      this.running = false; this.steps = 0; this.revision++;
      if (!this.game.won) { this.game.step(data.direction); this.analysis = null; this.save(); }
    } else if (action === 'new') {
      const next = new Game(data.seed);
      this.archive('manual_restart'); this.game = next; this.attempt++;
      this.running = false; this.steps = 0; this.revision++;
      this.analysis = this.error = null; this.started = Date.now(); this.elapsedBase = 0; this.save();
    } else if (action === 'settings') {
      const profile = data.profile ?? this.profile, retry = data.retry ?? this.retry;
      if (!Object.hasOwn(PROFILES, profile) || typeof retry !== 'boolean') throw new Error('设置无效');
      this.profile = profile; this.retry = retry; this.revision++; this.save();
    } else throw new Error('未知操作');
    this.schedule(); return this.state();
  }
  close() {
    this.running = false; this.steps = 0; this.revision++; this.save();
    this.disposed = true;
    if (this.timer !== null) clearTimeout(this.timer);
  }
}

export async function createTransport() {
  const solver = await workerSolver();
  let storage;
  try { storage = localStorage; } catch { storage = {getItem: () => null, setItem() { throw new Error('存储不可用'); }}; }
  const controller = new Controller(solver, storage);
  const save = () => controller.save();
  window.addEventListener('pagehide', save);
  document.addEventListener('visibilitychange', () => { if (document.hidden) save(); });
  return {async request(path, data) {
    if (path === 'state') return controller.state();
    if (path === 'replay') return controller.game.export();
    return controller.command(path, data);
  }};
}
