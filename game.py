"""Standard 4×4 2048 rules, seeded spawning, and fully verifiable replays."""
import random
from solver import DIRECTIONS, validate_board

def slide(board, direction):
    validate_board(board)
    if direction not in DIRECTIONS:
        raise ValueError('未知方向')
    result = list(board)
    gained = 0
    for line in range(4):
        ids = ([line*4+i for i in range(4)] if direction in ('left','right')
               else [i*4+line for i in range(4)])
        if direction in ('right','down'):
            ids.reverse()
        values = [board[i] for i in ids if board[i]]
        merged = []
        i = 0
        while i < len(values):
            if i+1 < len(values) and values[i] == values[i+1]:
                merged.append(values[i]*2)
                gained += values[i]*2
                i += 2
            else:
                merged.append(values[i]); i += 1
        for index, value in zip(ids, merged + [0]*(4-len(merged))):
            result[index] = value
    return result, gained, result != list(board)

class Game:
    def __init__(self, seed=None, target=65536):
        self.seed = random.SystemRandom().randrange(2**32) if seed is None else seed
        self.rng = random.Random(self.seed)
        self.target = target
        self.board = [0]*16
        self.score = self.moves = 0
        self.history = []
        self.spawn(); self.spawn()
        self.initial = self.board.copy()

    def spawn(self):
        empty = [i for i,v in enumerate(self.board) if not v]
        if not empty:
            return None
        index = self.rng.choice(empty)
        value = 2 if self.rng.random() < .9 else 4
        self.board[index] = value
        return {'index': index, 'value': value}

    @property
    def won(self):
        return max(self.board) >= self.target

    @property
    def over(self):
        return not any(slide(self.board, d)[2] for d in DIRECTIONS)

    def step(self, direction):
        board, gained, changed = slide(self.board, direction)
        if not changed:
            return False
        self.board = board
        self.score += gained
        self.moves += 1
        spawned = self.spawn()
        self.history.append({'direction': direction, 'spawn': spawned})
        return True

    def export(self):
        return {'version': 1, 'seed': self.seed, 'target': self.target, 'initial': self.initial,
                'board': self.board.copy(), 'score': self.score, 'moves': self.moves,
                'max_tile': max(self.board), 'won': self.won, 'over': self.over,
                'history': self.history.copy()}

    @classmethod
    def restore(cls, data):
        game = cls(data['seed'], data['target'])
        if game.initial != data['initial']:
            raise ValueError('初始棋盘与随机种子不一致')
        for record in data['history']:
            if not game.step(record['direction']) or game.history[-1] != record:
                raise ValueError('对局记录包含非法移动或不一致的随机方块')
        if any(game.export()[k] != data[k] for k in ('board','score','moves','max_tile','won','over')):
            raise ValueError('对局结果与逐步重放不一致')
        return game
