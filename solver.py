"""Small, reusable interface to the native Expectimax engine."""
import ctypes as C
import math
from build import build

DIRECTIONS = ('up', 'down', 'left', 'right')

def validate_board(board):
    if not isinstance(board, (list, tuple)) or len(board) != 16:
        raise ValueError('棋盘必须包含 16 个格子（按行排列）')
    for v in board:
        if type(v) is not int or v < 0 or v > 2**30 or (v and (v < 2 or v & (v-1))):
            raise ValueError('格子必须为 0 或 2 到 2^30 的 2 的幂')
    return board

class Solver:
    def __init__(self):
        self.lib = C.CDLL(str(build()))
        self.lib.ai_choose.argtypes = [C.POINTER(C.c_uint8), C.c_int, C.c_int, C.c_double, C.c_int,
                                       C.POINTER(C.c_double), C.POINTER(C.c_uint64)]
        self.lib.ai_choose.restype = C.c_int
        self.lib.ai_move.argtypes = [C.POINTER(C.c_uint8), C.c_int, C.POINTER(C.c_uint8)]
        self.lib.ai_move.restype = C.c_int

    @staticmethod
    def ranks(board):
        return (C.c_uint8 * 16)(*(v.bit_length()-1 if v else 0 for v in validate_board(board)))

    def choose(self, board, budget_ms=100, max_depth=8, cutoff=0.0001, target=65536):
        if type(budget_ms) is not int or not 1 <= budget_ms <= 60000:
            raise ValueError('budget_ms 必须为 1–60000 的整数')
        if type(max_depth) is not int or not 1 <= max_depth <= 12:
            raise ValueError('max_depth 必须为 1–12 的整数')
        if not isinstance(cutoff, (float, int)) or not math.isfinite(cutoff) or not 1e-8 <= cutoff <= .01:
            raise ValueError('cutoff 必须在 1e-8 到 0.01 之间')
        if type(target) is not int or target < 4 or target > 2**30 or target & (target-1):
            raise ValueError('target 必须为 4 到 2^30 的 2 的幂')
        scores, stats = (C.c_double * 4)(), (C.c_uint64 * 4)()
        d = self.lib.ai_choose(self.ranks(board), budget_ms, max_depth, cutoff, target.bit_length()-1, scores, stats)
        if d < -1:
            raise ValueError('棋盘超出求解器范围')
        return {'direction': DIRECTIONS[d] if d >= 0 else None,
                'values': {name: (scores[i] if scores[i] > -1e12 else None) for i, name in enumerate(DIRECTIONS)},
                'nodes': stats[0], 'cache_hits': stats[1], 'depth': stats[2], 'elapsed_ms': stats[3]/1000}

    def move(self, board, direction):
        output = (C.c_uint8 * 16)()
        changed = self.lib.ai_move(self.ranks(board), DIRECTIONS.index(direction), output)
        if changed < 0:
            raise ValueError('非法移动')
        return [2**v if v else 0 for v in output], bool(changed)
