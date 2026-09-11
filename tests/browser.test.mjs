import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {Game, Random, slide, DIRECTIONS} from '../web/browser/game.mjs';
import {Controller} from '../web/browser/controller.mjs';

const storage = () => {
  const data = new Map();
  return {getItem: key => data.get(key), setItem: (key, value) => data.set(key, value)};
};
const result = board => ({direction: DIRECTIONS.find(d => slide(board, d).changed)});
const fake = {choose: async board => result(board)};
const turn = () => new Promise(resolve => setTimeout(resolve, 5));

test('merge once, score, high ranks and invalid moves', () => {
  const b = [32768, 32768, 65536, 65536, ...Array(12).fill(0)];
  assert.deepEqual(slide(b, 'left'), {board: [65536, 131072, 0, 0, ...Array(12).fill(0)], gained: 196608, changed: true});
  const g = new Game(12);
  g.board = [2, ...Array(15).fill(0)];
  const before = g.export(), state = g.rng.state;
  assert.equal(g.step('left'), false);
  assert.equal(g.rng.state, state);
  assert.deepEqual(g.export(), before);
});

test('version-2 replay matches independent Python rules and RNG', () => {
  for (const seed of [0, 1, 20260911, 0xffffffff]) {
    const game = new Game(seed), policy = new Random(seed + 42);
    for (let i = 0; i < 500 && !game.over; i++) game.step(DIRECTIONS[policy.integer(4)]);
    const data = game.export(), restored = Game.restore(data);
    assert.deepEqual(restored.export(), data);
    const check = spawnSync('python', ['-c',
      'import sys,json; from browser_replay import BrowserReplayGame; d=json.load(sys.stdin); g=BrowserReplayGame.restore(d); print(json.dumps(g.board))'],
    {input: JSON.stringify(data), encoding: 'utf8'});
    assert.equal(check.status, 0, check.stderr);
    assert.deepEqual(JSON.parse(check.stdout), game.board);
    for (const d of DIRECTIONS) { game.step(d); restored.step(d); }
    assert.deepEqual(restored.export(), game.export());
    const broken = structuredClone(data); broken.history[0].spawn.value = 65536;
    assert.throws(() => Game.restore(broken), /落子/);
    const badScore = structuredClone(data); badScore.score++;
    assert.throws(() => Game.restore(badScore), /score/);
  }
});

test('pause and restart discard an in-flight result', async () => {
  for (const action of ['pause', 'new']) {
    let resolve;
    const c = new Controller({choose: () => new Promise(r => { resolve = r; })}, storage());
    c.running = true;
    const old = [...c.game.board], pending = c.tick();
    c.command(action, action === 'new' ? {seed: 99} : {});
    const next = c.game.export();
    resolve(result(old)); await pending;
    assert.deepEqual(c.game.export(), next);
    assert.equal(c.running, false);
    c.close();
  }
});

test('one AI step persists and restores paused with RNG continuation', async () => {
  const store = storage(), c = new Controller(fake, store);
  c.command('step'); await turn();
  assert.equal(c.game.moves, 1); assert.equal(c.running, false);
  c.close();
  const restored = new Controller(fake, store);
  assert.equal(restored.running, false);
  assert.deepEqual(restored.game.export(), c.game.export());
  for (const d of DIRECTIONS) { restored.game.step(d); c.game.step(d); }
  assert.deepEqual(restored.game.export(), c.game.export());
  restored.close();
});

test('automatic retry starts a fresh game; retry off stops', async () => {
  const dead = [2,4,2,4,4,2,4,2,2,4,2,4,4,2,4,2];
  for (const retry of [false, true]) {
    const c = new Controller(fake, storage());
    c.game.board = dead; c.running = true; c.retry = retry;
    await c.tick();
    assert.equal(c.attempt, retry ? 2 : 1);
    assert.equal(c.game.moves, retry ? 1 : 0);
    assert.equal(c.running, retry);
    c.close();
  }
});

test('reaching target stops before automatic retry', async () => {
  const c = new Controller({choose: async () => ({direction: 'left'})}, storage());
  c.game.board = [32768,32768,...Array(14).fill(0)]; c.running = true;
  await c.tick();
  assert.equal(c.game.won, true); assert.equal(c.running, false);
  assert.equal(c.results.at(-1).reason, 'won');
  c.command('start'); await turn();
  assert.equal(c.game.moves, 1); assert.equal(c.attempt, 1);
  c.close();
});

test('corrupt or unavailable storage does not disable gameplay', async () => {
  const c = new Controller(fake, {getItem: () => '{broken', setItem() { throw new Error('quota'); }});
  assert.match(c.state().storage_warning, /无法读取/);
  c.steps = 1; await c.tick();
  assert.equal(c.game.moves, 1);
  assert.match(c.state().storage_warning, /存储/);
  c.close();
});

test('solver error stops automatic execution', async () => {
  const c = new Controller({choose: async () => { throw new Error('worker failed'); }}, storage());
  c.running = true; await c.tick();
  assert.equal(c.running, false); assert.equal(c.state().error, 'worker failed');
  assert.equal(c.game.moves, 0); c.close();
});
