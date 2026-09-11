"""Local-only game controller. Autoplay continues when the browser is hidden."""
import argparse
import json
import mimetypes
from pathlib import Path
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from autoplay import atomic_json
from game import Game
from solver import Solver, DIRECTIONS

ROOT = Path(__file__).resolve().parent
PROFILES = {'fast':(10,5,.0001), 'balanced':(100,8,.0001), 'deep':(500,10,.00003)}

class Controller:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.stopping = False
        self.solver = Solver()
        self.game = Game()
        self.running = self.thinking = False
        self.steps = self.revision = 0
        self.profile, self.retry = 'balanced', True
        self.attempt = 1
        self.best = 0
        self.results = []
        self.analysis = None
        self.error = None
        self.started = time.monotonic()
        self.elapsed_base = 0
        checkpoint = self.directory/'session.json'
        if checkpoint.exists():
            try:
                data = json.loads(checkpoint.read_text(encoding='utf-8'))
                self.game = Game.restore(data['game'])
                self.profile = data.get('profile','balanced')
                if self.profile not in PROFILES: self.profile='balanced'
                self.retry = bool(data.get('retry',True))
                self.attempt = data.get('attempt',1)
                self.best = data.get('best',max(self.game.board))
                self.results = data.get('results',[])
                self.elapsed_base = data.get('elapsed',0)
            except (ValueError, KeyError, TypeError, OSError) as exc:
                self.error = f'存档读取失败，已保留原文件：{exc}'
                checkpoint.rename(self.directory/f'session-invalid-{time.time_ns()}.json')
        self.worker = threading.Thread(target=self.loop,daemon=True)
        self.worker.start()

    def state(self):
        with self.lock:
            g = self.game
            status = ('error' if self.error else 'won' if g.won else 'gameover' if g.over
                      else 'running' if self.running else 'thinking' if self.thinking or self.steps else 'paused')
            return {'board':g.board.copy(),'score':g.score,'moves':g.moves,'seed':g.seed,
                    'max_tile':max(g.board),'target':g.target,'won':g.won,'over':g.over,
                    'status':status,'running':self.running,'thinking':self.thinking,
                    'profile':self.profile,'retry':self.retry,'attempt':self.attempt,
                    'best':max(self.best,max(g.board)),'results':self.results[-8:],
                    'analysis':self.analysis,'error':self.error,
                    'elapsed':round(self.elapsed_base+time.monotonic()-self.started,1)}

    def save(self):
        atomic_json(self.directory/'session.json', {
            'game':self.game.export(),'profile':self.profile,'retry':self.retry,
            'attempt':self.attempt,'best':max(self.best,max(self.game.board)),
            'results':self.results[-100:], 'elapsed':self.elapsed_base+time.monotonic()-self.started})

    def archive(self, reason):
        g = self.game
        atomic_json(self.directory/f'game-{g.seed}-{time.time_ns()}.json', g.export())
        self.best = max(self.best,max(g.board))
        self.results.append({'seed':g.seed,'max_tile':max(g.board),'score':g.score,'moves':g.moves,'reason':reason})

    def command(self, action, data):
        with self.lock:
            if action == 'start':
                if self.game.won: return self.state()
                if self.game.over and not self.retry: return self.state()
                self.running = True
                self.error = None
            elif action == 'pause':
                self.running = False; self.steps = 0; self.revision += 1
                self.save()
            elif action == 'step':
                if not self.game.won and not self.game.over and not self.thinking:
                    self.running = False; self.steps = 1; self.revision += 1
            elif action == 'move':
                direction = data.get('direction')
                if direction not in DIRECTIONS: raise ValueError('未知方向')
                self.running = False; self.steps = 0; self.revision += 1
                if not self.game.won:
                    self.game.step(direction)
                    self.analysis = None
                    self.save()
            elif action == 'new':
                seed = data.get('seed')
                if seed is not None and (type(seed) is not int or not 0<=seed<2**53):
                    raise ValueError('种子必须是 0 到 2^53-1 的整数')
                self.archive('manual_restart')
                self.game = Game(seed)
                self.attempt += 1
                self.running = False; self.steps = 0; self.revision += 1
                self.analysis = self.error = None
                self.elapsed_base = 0; self.started = time.monotonic()
                self.save()
            elif action == 'settings':
                profile = data.get('profile',self.profile)
                retry = data.get('retry',self.retry)
                if profile not in PROFILES or type(retry) is not bool: raise ValueError('设置无效')
                self.profile, self.retry = profile, retry
                self.revision += 1
                self.save()
            else:
                raise ValueError('未知操作')
            self.wake.set()
            return self.state()

    def loop(self):
        while not self.stopping:
            self.wake.wait(.2)
            self.wake.clear()
            with self.lock:
                if not (self.running or self.steps): continue
                if self.game.won:
                    self.running=False; self.steps=0; self.save(); continue
                if self.game.over:
                    if self.running and self.retry:
                        self.archive('gameover')
                        self.game=Game(); self.attempt+=1
                        self.analysis=None; self.revision+=1
                        self.elapsed_base=0; self.started=time.monotonic()
                        self.save()
                    else:
                        self.running=False; self.steps=0; self.save(); continue
                board=self.game.board.copy()
                revision=self.revision
                config=PROFILES[self.profile]
                self.thinking=True
            try:
                result=self.solver.choose(board,*config)
                with self.lock:
                    self.thinking=False
                    if revision!=self.revision: self.wake.set(); continue
                    self.analysis=result
                    if result['direction'] is None or not self.game.step(result['direction']):
                        raise RuntimeError('求解器未返回合法移动')
                    self.steps=max(0,self.steps-1)
                    self.best=max(self.best,max(self.game.board))
                    if self.game.won:
                        self.running=False; self.steps=0; self.archive('won'); self.save()
                    elif self.game.moves%50==0 or not self.running or self.game.over:
                        self.save()
                    if self.running or self.steps: self.wake.set()
            except Exception as exc:
                traceback.print_exc()
                with self.lock:
                    self.thinking=False; self.running=False; self.steps=0
                    self.error=str(exc)

    def close(self):
        with self.lock:
            self.stopping=True; self.running=False; self.revision+=1
            self.save()
        self.wake.set()
        self.worker.join(timeout=3)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        if '/api/state' not in str(args): super().log_message(format,*args)

    def send(self, status, data, content_type='application/json; charset=utf-8'):
        if not isinstance(data,bytes): data=json.dumps(data,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers()
        try: self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError): pass

    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/api/state': self.send(200,self.server.controller.state())
        elif path=='/api/replay':
            with self.server.controller.lock: self.send(200,self.server.controller.game.export())
        elif path in ('/','/app.js','/style.css','/favicon.svg'):
            file=ROOT/'web'/('index.html' if path=='/' else path[1:])
            self.send(200,file.read_bytes(),mimetypes.guess_type(str(file))[0] or 'text/plain')
        else: self.send(404,{'error':'未找到'})

    def do_POST(self):
        origin=self.headers.get('Origin')
        allowed={f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}
        if origin and origin not in allowed:
            self.send(403,{'error':'只接受本地页面的操作'}); return
        if self.headers.get_content_type()!='application/json':
            self.send(415,{'error':'需要 application/json'}); return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=4096: raise ValueError('请求长度无效')
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict): raise ValueError('需要 JSON 对象')
            path=urlparse(self.path).path
            if not path.startswith('/api/'): self.send(404,{'error':'未找到'}); return
            self.send(200,self.server.controller.command(path[5:],data))
        except (ValueError,TypeError) as exc: self.send(400,{'error':str(exc)})

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=2048)
    parser.add_argument('--data-dir',default=str(ROOT/'runs'/'live'))
    args=parser.parse_args()
    controller=Controller(args.data_dir)
    try:
        server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    except OSError:
        controller.close(); raise
    server.controller=controller
    print(f'2048 → 65536 已启动：http://127.0.0.1:{args.port}  （Ctrl+C 退出并保存）',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: controller.close(); server.server_close()

if __name__=='__main__': main()
