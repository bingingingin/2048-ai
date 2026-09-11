"""Independent Python verification of the browser's version-2 replay format."""
from game import Game


class BrowserRandom:
    def __init__(self, seed):
        self.state = seed

    def next(self):
        mask = 0xffffffff
        self.state = (self.state + 0x6d2b79f5) & mask
        t = self.state
        t = ((t ^ (t >> 15)) * (t | 1)) & mask
        t = (t ^ (t + (((t ^ (t >> 7)) * (t | 61)) & mask))) & mask
        return (t ^ (t >> 14)) & mask

    def integer(self, n):
        limit = (2**32 // n) * n
        value = self.next()
        while value >= limit:
            value = self.next()
        return value % n


class BrowserReplayGame(Game):
    def __init__(self, seed, target=65536):
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError('Invalid browser seed')
        if type(target) is not int or not 4 <= target <= 2**30 or target & (target - 1):
            raise ValueError('Invalid browser target')
        self.seed, self.target = seed, target
        self.rng = BrowserRandom(seed)
        self.board = [0] * 16
        self.score = self.moves = 0
        self.history = []
        self.spawn(); self.spawn()
        self.initial = self.board.copy()

    def spawn(self):
        empty = [i for i, v in enumerate(self.board) if not v]
        if not empty:
            return None
        index = empty[self.rng.integer(len(empty))]
        value = 2 if self.rng.integer(10) < 9 else 4
        self.board[index] = value
        return {'index': index, 'value': value}

    @classmethod
    def restore(cls, data):
        if (data.get('version') != 2 or data.get('runtime') != 'browser-wasm'
                or data.get('rng') != 'mulberry32-rejection-v1'):
            raise ValueError('Unsupported browser replay format')
        if not isinstance(data.get('history'), list) or len(data['history']) > 200000:
            raise ValueError('Invalid replay history')
        return super().restore(data)
