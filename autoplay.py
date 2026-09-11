"""Headless autoplay: python autoplay.py --games 10 --budget-ms 100."""
import argparse
import json
from pathlib import Path
import time
from game import Game
from solver import Solver

ROOT = Path(__file__).resolve().parent

def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)

def run(args):
    solver = Solver()
    directory = Path(args.output)
    directory.mkdir(parents=True, exist_ok=True)
    results = []
    attempt = 0
    while args.games == 0 or attempt < args.games:
        seed = args.seed + attempt
        attempt += 1
        game = Game(seed, args.target)
        start = time.monotonic()
        stopped = False
        try:
            while not game.won and not game.over and game.moves < args.max_moves:
                recommendation = solver.choose(game.board, args.budget_ms, args.depth, args.cutoff, game.target)
                if recommendation['direction'] is None:
                    raise RuntimeError('求解器在仍有合法移动时返回空方向')
                if not game.step(recommendation['direction']):
                    raise RuntimeError('求解器返回了无效移动')
                if game.moves % 1000 == 0:
                    print(json.dumps({'event':'progress','seed':seed,'moves':game.moves,
                                      'max_tile':max(game.board),'score':game.score,
                                      'seconds':round(time.monotonic()-start,1)}, ensure_ascii=False), flush=True)
                    atomic_json(directory / f'seed-{seed}.json', game.export())
        except KeyboardInterrupt:
            stopped = True
        atomic_json(directory / f'seed-{seed}.json', game.export())
        result = {'seed':seed,'moves':game.moves,'score':game.score,'max_tile':max(game.board),
                  'won':game.won,'over':game.over,'seconds':round(time.monotonic()-start,2),
                  'status':'interrupted' if stopped else 'won' if game.won else 'lost' if game.over else 'move_limit'}
        results.append(result)
        print(json.dumps({'event':'result',**result}), flush=True)
        atomic_json(directory / 'summary.json', {'config':vars(args),'results':results,
                    'wins':sum(r['won'] for r in results),'attempts':len(results)})
        if stopped or (game.won and args.until_target):
            break

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='标准随机规则下自动挑战 65536，并保存可重放记录')
    parser.add_argument('--games',type=int,default=1,help='局数，0 表示持续重试')
    parser.add_argument('--seed',type=int,default=20260911)
    parser.add_argument('--target',type=int,default=65536)
    parser.add_argument('--budget-ms',type=int,default=100)
    parser.add_argument('--depth',type=int,default=8)
    parser.add_argument('--cutoff',type=float,default=.0001)
    parser.add_argument('--max-moves',type=int,default=200000)
    parser.add_argument('--until-target',action='store_true',help='首次达到目标后停止后续对局')
    parser.add_argument('--output',default=str(ROOT/'runs'/'batch'))
    args = parser.parse_args()
    if args.games < 0 or args.max_moves < 1 or args.target < 4 or args.target > 2**30 or args.target & (args.target-1):
        parser.error('局数必须非负；步数必须为正；目标必须为 4 到 2^30 的 2 的幂')
    if not 1 <= args.budget_ms <= 60000 or not 1 <= args.depth <= 12 or not 1e-8 <= args.cutoff <= .01:
        parser.error('请检查思考时间、深度与概率阈值范围')
    run(args)
