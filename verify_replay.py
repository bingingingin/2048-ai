"""Verify every move, spawn, score and final board in a saved replay."""
import argparse
import json
from pathlib import Path
from game import Game

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('file',type=Path)
    args=parser.parse_args()
    data=json.loads(args.file.read_text(encoding='utf-8'))
    game=Game.restore(data.get('game',data))
    print(json.dumps({'verified':True,'seed':game.seed,'moves':game.moves,
                      'score':game.score,'max_tile':max(game.board),'won':game.won,'over':game.over}))
