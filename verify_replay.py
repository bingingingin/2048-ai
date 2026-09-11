"""Verify every move, spawn, score and final board in a saved replay."""
import argparse
import json
from pathlib import Path
from game import Game
from browser_replay import BrowserReplayGame

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('file',type=Path)
    args=parser.parse_args()
    data=json.loads(args.file.read_text(encoding='utf-8'))
    data=data.get('game',data)
    if data.get('version') not in (1,2):
        raise ValueError('不支持的对局版本')
    game=(BrowserReplayGame if data['version']==2 else Game).restore(data)
    print(json.dumps({'verified':True,'seed':game.seed,'moves':game.moves,
                      'score':game.score,'max_tile':max(game.board),'won':game.won,'over':game.over}))
