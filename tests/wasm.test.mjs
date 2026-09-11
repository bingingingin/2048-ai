import test from 'node:test';
import assert from 'node:assert/strict';
import factory from '../dist/solver.mjs';
import {createSolver} from '../web/browser/wasm-client.mjs';
import {Game, Random, slide, DIRECTIONS} from '../web/browser/game.mjs';

const solver = await createSolver(factory);
test.after(() => solver.dispose());

test('83,521 row layouts agree with independent JS rules', () => {
  for (let n = 0; n < 17 ** 4; n++) {
    let code = n;
    const board = Array(16).fill(0);
    for (let i = 0; i < 4; i++) { const rank = code % 17; code = Math.floor(code / 17); board[i] = rank ? 2 ** rank : 0; }
    const expected = slide(board, 'left');
    assert.deepEqual(solver.move(board, 'left'), {board: expected.board, changed: expected.changed});
  }
});

test('6,000 whole-board moves including high ranks agree', () => {
  const rng = new Random(42);
  for (let i = 0; i < 1500; i++) {
    const board = Array.from({length:16}, () => { const rank = rng.integer(18); return rank ? 2 ** rank : 0; });
    for (const d of DIRECTIONS) {
      const expected = slide(board, d);
      assert.deepEqual(solver.move(board, d), {board: expected.board, changed: expected.changed});
    }
  }
});

test('65536 merge is selected, and dead board has no action', () => {
  const board = [32768,32768,...Array(14).fill(0)];
  const choice = solver.choose(board, {budget_ms: 10});
  assert.ok(Math.max(...slide(board, choice.direction).board) >= 65536);
  const dead = [2,4,2,4,4,2,4,2,2,4,2,4,4,2,4,2];
  assert.equal(solver.choose(dead, {budget_ms: 1}).direction, null);
});

test('timeouts unwind correctly and a 200-step run replays', () => {
  const g = new Game(20260911);
  for (let i = 0; i < 200 && !g.over; i++) {
    const decision = solver.choose(g.board, {budget_ms: 1, max_depth: 12, cutoff: 1e-8});
    assert.ok(decision.direction);
    assert.ok(g.step(decision.direction));
    assert.ok(Number.isFinite(decision.elapsed_ms));
  }
  assert.equal(g.moves, 200);
  assert.deepEqual(Game.restore(g.export()).export(), g.export());
});
