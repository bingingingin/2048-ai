import itertools
import json
import random
import tempfile
import threading
import time
import unittest
from pathlib import Path
from game import Game, slide
from solver import Solver, DIRECTIONS
from server import Controller


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.solver = Solver()

    def test_merge_once_and_score(self):
        result, score, changed = slide([2,2,2,2]+[0]*12,'left')
        self.assertEqual(result[:4],[4,4,0,0])
        self.assertEqual(score,8)
        self.assertTrue(changed)
        result, score, _ = slide([4,4,8,0]+[0]*12,'left')
        self.assertEqual(result[:4],[8,8,0,0])
        self.assertEqual(score,8)

    def test_65536_and_higher_merges_all_directions(self):
        for rank in range(1,30):
            for d in DIRECTIONS:
                board = [0]*16
                ids = (0,1) if d in ('left','right') else (0,4)
                for i in ids: board[i] = 2**rank
                actual, changed = self.solver.move(board,d)
                expected, score, _ = slide(board,d)
                self.assertEqual(actual,expected,(rank,d))
                self.assertEqual(score,2**(rank+1))
                self.assertTrue(changed)

    def test_all_rows_through_target(self):
        # Exhaust every possible line using ranks 0..16, including two 32768s.
        for ranks in itertools.product(range(17), repeat=4):
            board = [2**v if v else 0 for v in ranks]+[0]*12
            expected, _, changed = slide(board,'left')
            actual, actual_changed = self.solver.move(board,'left')
            self.assertEqual((actual,actual_changed),(expected,changed),ranks)

    def test_random_boards_all_directions(self):
        rng = random.Random(42)
        for _ in range(1500):
            board = [2**v if v else 0 for v in (rng.randrange(18) for _ in range(16))]
            for d in DIRECTIONS:
                expected, _, changed = slide(board,d)
                actual, actual_changed = self.solver.move(board,d)
                self.assertEqual((actual,actual_changed),(expected,changed))
                self.assertEqual(sum(board),sum(actual))

    def test_game_over_and_negative_high_rank_scores(self):
        dead = [2,4,2,4,4,2,4,2,2,4,2,4,4,2,4,2]
        self.assertIsNone(self.solver.choose(dead,budget_ms=5)['direction'])
        board = [32768,32768,4,2,16384,8192,2,4,4096,2048,4,2,1024,512,2,4]
        answer = self.solver.choose(board,budget_ms=30,max_depth=3)
        self.assertIn(answer['direction'],('left','right'))
        moved, _ = self.solver.move(board,answer['direction'])
        self.assertEqual(max(moved),65536)

    def test_timeout_returns_legal_move(self):
        board = [2,4,8,16,32,64,128,256,512,1024,2048,4096,8192,16384,0,0]
        answer = self.solver.choose(board,budget_ms=1,max_depth=12,cutoff=1e-8)
        self.assertTrue(slide(board,answer['direction'])[2])
        self.assertLess(answer['elapsed_ms'],250)

    def test_immediate_goal_is_prioritized(self):
        board=[32768,32768,0,0]+[0]*12
        answer=self.solver.choose(board,budget_ms=1)
        self.assertIn(answer['direction'],('left','right'))
        self.assertEqual(max(self.solver.move(board,answer['direction'])[0]),65536)
        board=[1024,1024,0,0]+[0]*12
        answer=self.solver.choose(board,budget_ms=1,target=2048)
        self.assertEqual(max(self.solver.move(board,answer['direction'])[0]),2048)

    def test_seed_replay_resume_and_noop(self):
        game = Game(42)
        for _ in range(100):
            for d in DIRECTIONS:
                if game.step(d): break
        data = json.loads(json.dumps(game.export()))
        restored = Game.restore(data)
        self.assertEqual(restored.export(),game.export())
        for d in DIRECTIONS:
            game.step(d); restored.step(d)
        self.assertEqual(restored.export(),game.export())
        game.board = [2]+[0]*15
        old_rng = game.rng.getstate()
        moves = game.moves
        self.assertFalse(game.step('left'))
        self.assertEqual(game.rng.getstate(),old_rng)
        self.assertEqual(game.moves,moves)
        data['score'] += 4
        with self.assertRaises(ValueError): Game.restore(data)

    def test_invalid_inputs(self):
        for board in ([0]*15,[1]+[0]*15,[3]+[0]*15,[-2]+[0]*15,[True]+[0]*15):
            with self.assertRaises(ValueError): self.solver.choose(board)


class ControllerTests(unittest.TestCase):
    def test_single_step_pause_and_resume_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            c = Controller(directory)
            try:
                c.command('settings',{'profile':'fast'})
                c.command('step',{})
                deadline = time.monotonic()+3
                while c.state()['moves']==0 and time.monotonic()<deadline: time.sleep(.01)
                self.assertEqual(c.state()['moves'],1)
                self.assertFalse(c.state()['running'])
                c.command('start',{})
                time.sleep(.1)
                s = c.command('pause',{})
                time.sleep(.1)
                self.assertEqual(c.state()['moves'],s['moves'])
                self.assertFalse(c.state()['running'])
            finally: c.close()
            restored = Controller(directory)
            try:
                self.assertEqual(restored.state()['board'],s['board'])
                self.assertEqual(restored.state()['score'],s['score'])
                self.assertFalse(restored.state()['running'])
            finally: restored.close()

    def test_pause_discards_inflight_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            c = Controller(directory)
            entered, release = threading.Event(), threading.Event()
            original = c.solver.choose
            def slow(*args):
                entered.set(); release.wait(3)
                return original(*args)
            c.solver.choose=slow
            try:
                c.command('start',{})
                self.assertTrue(entered.wait(2))
                before = c.command('pause',{})
                release.set(); time.sleep(.2)
                self.assertEqual(c.state()['board'],before['board'])
                self.assertEqual(c.state()['moves'],0)
            finally:
                release.set(); c.close()

    def test_goal_stops_and_failure_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            c = Controller(directory)
            try:
                c.command('settings',{'profile':'fast'})
                with c.lock:
                    c.game.board=[32768,32768,4,2,16384,8192,2,4,4096,2048,4,2,1024,512,2,4]
                c.command('start',{})
                deadline=time.monotonic()+3
                while not c.state()['won'] and time.monotonic()<deadline: time.sleep(.01)
                self.assertTrue(c.state()['won'])
                self.assertFalse(c.state()['running'])
                self.assertEqual(c.state()['max_tile'],65536)
                with c.lock:
                    c.game=Game(0)
                    c.game.board=[2,4,2,4,4,2,4,2,2,4,2,4,4,2,4,2]
                c.command('start',{})
                deadline=time.monotonic()+3
                while c.state()['attempt']==1 and time.monotonic()<deadline: time.sleep(.01)
                c.command('pause',{})
                self.assertEqual(c.state()['attempt'],2)
            finally: c.close()

if __name__=='__main__': unittest.main()
