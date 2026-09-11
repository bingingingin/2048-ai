'use strict';
const $ = id => document.getElementById(id);
const directions = ['up', 'down', 'left', 'right'];
const arrows = ['↑', '↓', '←', '→'];
const names = ['上', '下', '左', '右'];
const milestones = [2048, 4096, 8192, 16384, 32768, 65536];
let current = null, pending = false, toastTimer, previous = [], commandEpoch = 0;
const browserMode = document.querySelector('meta[name="2048-runtime"]').content === 'browser';
const transport = browserMode ? import('./browser/controller.mjs').then(m => m.createTransport()) : null;
if (browserMode) {
  $('runtime-note').textContent = '在线版 · 运算与存档保留在此浏览器；关闭页面停止，重开后暂停续存。后台标签页可能减速，请在一个标签页中运行。';
  transport.catch(error => toast(`引擎加载失败：${error.message}。请刷新重试。`));
}
for (let i = 0; i < 16; i++) {
  const tile = document.createElement('div');
  tile.className = 'tile'; tile.setAttribute('role', 'gridcell');
  $('board').appendChild(tile);
}
directions.forEach((d, i) => {
  const item = document.createElement('div');
  item.id = `direction-${d}`; item.className = 'direction';
  item.setAttribute('aria-label', names[i]);
  item.innerHTML = `<span class="arrow">${arrows[i]}</span><span class="value">—</span>`;
  $('direction-scores').appendChild(item);
});
milestones.forEach(v => {
  const el = document.createElement('span'); el.id = `milestone-${v}`; el.className = 'milestone';
  el.textContent = String(v); $('milestones').appendChild(el);
});
function toast(message) {
  $('toast').textContent = message; $('toast').hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 5000);
}
const number = v => v.toLocaleString('en-US');
function render(s) {
  current = s;
  [...$('board').children].forEach((el, i) => {
    const v = s.board[i];
    el.className = `tile${v ? ' filled' : ''}${v >= 16384 ? ' large' : ''}${v && v !== previous[i] ? ' changed' : ''}`;
    el.dataset.value = v; el.textContent = v || '';
    el.setAttribute('aria-label', `${Math.floor(i / 4) + 1} 行 ${i % 4 + 1} 列：${v || '空'}`);
  });
  previous = [...s.board];
  $('score').textContent = number(s.score); $('moves').textContent = number(s.moves);
  $('max-tile').textContent = number(s.max_tile); $('best').textContent = number(s.best);
  $('attempt').textContent = String(s.attempt).padStart(2, '0');
  const seconds = Math.floor(s.elapsed);
  $('elapsed').textContent = `${String(Math.floor(seconds / 60)).padStart(2,'0')}:${String(seconds % 60).padStart(2,'0')}`;
  $('game-status').textContent = ({running:'正在自动运行', paused:'已暂停 · 随时继续', thinking:'正在思考', won:'已达成 65536！', gameover:s.retry && s.running ? '本局结束 · 准备重试' : '本局结束', error:'运行出错'})[s.status];
  $('toggle').innerHTML = s.running ? '暂停自动运行 <span>Ⅱ</span>' : s.won ? '目标已达成 <span>✓</span>' : '开始自动运行 <span>↗</span>';
  $('toggle').disabled = s.won || (s.over && !s.retry);
  $('step').disabled = s.thinking || s.running || s.won || s.over;
  if (document.activeElement !== $('profile')) $('profile').value = s.profile;
  $('retry').checked = s.retry;
  $('profile-help').textContent = ({fast:'快速观察策略，较短的思考时间可能影响后期表现。',balanced:'兼顾搜索深度与对局速度，适合持续挑战。',deep:'为复杂局面留出更多搜索时间，每局耗时也会增加。'})[s.profile];
  const a = s.analysis;
  directions.forEach(d => {
    const el = $(`direction-${d}`), value = a?.values[d];
    el.className = `direction${a?.direction === d ? ' selected' : ''}${a && value === null ? ' illegal' : ''}`;
    el.querySelector('.value').textContent = value == null ? (a ? '不可移动' : '—') : value >= 1e12 ? '达成目标' : number(Math.round(value));
  });
  $('nodes').textContent = a ? number(a.nodes) : '—';
  $('search-time').textContent = a ? `${Math.round(a.elapsed_ms)} ms` : '—';
  $('depth-label').textContent = a ? `完整搜索 ${a.depth} 层` : '等待分析';
  let count = 0;
  milestones.forEach(v => { const done = s.max_tile >= v; count += done; $(`milestone-${v}`).className = `milestone${done ? ' done' : ''}`; });
  $('milestone-count').textContent = `${count} / 6`;
  $('history-panel').hidden = !s.results.length;
  $('history').replaceChildren(...s.results.slice(-8).reverse().map(r => {
    const el = document.createElement('div'); el.className = 'history-item';
    const reason = ({won:'目标达成',gameover:'对局结束',manual_restart:'手动重开'})[r.reason] || '对局结束';
    el.innerHTML = `<span>${reason}</span><strong>${number(r.max_tile)}</strong><span>${number(r.score)} 分 · ${number(r.moves)} 步</span>`;
    return el;
  }));
  if (s.error) { $('game-status').textContent = s.error; }
  $('storage-warning').hidden = !s.storage_warning;
  $('storage-warning').textContent = s.storage_warning || '';
}
async function request(path, data) {
  if (transport) return (await transport).request(path, data);
  const res = await fetch(`/api/${path}`, data === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || `请求失败 ${res.status}`);
  return body;
}
async function command(action, data = {}) {
  if (pending) return;
  commandEpoch++;
  pending = true;
  try { render(await request(action, data)); }
  catch (error) { toast(error.message); }
  finally { pending = false; }
}
async function poll() {
  try {
    if (!pending) {
      const epoch = commandEpoch;
      const state = await request('state');
      if (epoch === commandEpoch && !pending) render(state);
    }
    $('connection').className = 'connection online'; $('connection').innerHTML = browserMode ? '<i></i>浏览器引擎在线' : '<i></i>本地引擎在线';
  } catch (error) {
    $('connection').className = 'connection'; $('connection').innerHTML = '<i></i>引擎未连接';
  } finally { setTimeout(poll, 250); }
}
$('toggle').onclick = () => command(current?.running ? 'pause' : 'start');
$('step').onclick = () => command('step');
$('new-game').onclick = () => command('new');
$('profile').onchange = () => command('settings',{profile:$('profile').value});
$('retry').onchange = () => command('settings',{retry:$('retry').checked});
$('export').onclick = async () => {
  try {
    const replay = await request('replay');
    const url = URL.createObjectURL(new Blob([JSON.stringify(replay,null,2)],{type:'application/json'}));
    const a = document.createElement('a'); a.href = url; a.download = `2048-${replay.seed}-${replay.moves}.json`;
    a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { toast(error.message); }
};
document.addEventListener('keydown', event => {
  if (['INPUT','SELECT','TEXTAREA'].includes(event.target.tagName)) return;
  const d = {ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right'}[event.key];
  if (d) { event.preventDefault(); command('move',{direction:d}); }
  if (event.code === 'Space') { event.preventDefault(); command(current?.running ? 'pause' : 'start'); }
});
let touchStart;
$('board').addEventListener('pointerdown', e => {touchStart=[e.clientX,e.clientY]; $('board').setPointerCapture(e.pointerId);});
$('board').addEventListener('pointerup', e => {
  if (!touchStart) return;
  const dx=e.clientX-touchStart[0], dy=e.clientY-touchStart[1]; touchStart=null;
  if (Math.max(Math.abs(dx),Math.abs(dy)) < 25) return;
  command('move',{direction:Math.abs(dx)>Math.abs(dy) ? (dx>0?'right':'left') : (dy>0?'down':'up')});
});
$('board').addEventListener('pointercancel', () => { touchStart=null; });
poll();
