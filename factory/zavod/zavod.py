"""Контент-завод РЕНВИКС: собирает рилс из сцен библиотеки по reel.json.
  python3 zavod.py check  reels/<id>.json            — автопроверка кадров
  python3 zavod.py stills reels/<id>.json            — превью кадров в /tmp/zv_<id>/
  python3 zavod.py render reels/<id>.json OUT_DIR    — mp4 + scenes.json + обложки сцен
"""
import json, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import *
from scenes import LIBRARY

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))   # корень репозитория
BRAND = dict(name='РЕНВИКС', tagline='ремонт квартир под ключ', contact='@renviks_moscow', logo='factory/brand/logo.jpg')
TR = 0.4   # длительность перехода zoom-blur
CAP_Y, CAP_X, CAP_W, CAP_SIZE, CAP_CHARS = 1190, LOW_CX, 820, 78, 17   # субтитры по словам: ниже середины, левее кнопок Instagram
import re
LOOP = 0.45
def norm(w): return re.sub(r'[^\wё]', '', w.lower().replace('ё', 'е'))

def resolve(spec):
    for k in ('img', 'before', 'after'):
        if k in spec and not os.path.isabs(spec[k]): spec[k] = os.path.join(ROOT, spec[k])
    return spec

class Reel:
    def __init__(self, path, variant=None):
        self.cfg = json.load(open(path)); self.id = self.cfg.get('id', os.path.splitext(os.path.basename(path))[0])
        if variant is not None:                       # вариант крючка: подменяет поля первой сцены (для Trial Reels / A-B)
            self.cfg['scenes'][0].update(self.cfg['hooks'][variant]); self.id += f'-h{variant + 1}'
        brand = dict(BRAND, **self.cfg.get('brand', {}))
        if brand.get('logo') and not os.path.isabs(brand['logo']): brand['logo'] = os.path.join(ROOT, brand['logo'])
        if brand.get('logo') and not os.path.exists(brand['logo']): brand['logo'] = None
        ctx = dict(brand=brand, root=ROOT)
        self.words = self.load_words()
        specs = [resolve(dict(s)) for s in self.cfg['scenes']]
        self.timeline(specs)
        self.scenes, self.starts, t = [], [], 0.0
        for i, s in enumerate(specs):
            sc = LIBRARY[s['type']](s, ctx)
            sc.enter = s.get('enter', 'flash' if s['type'] in ('photo', 'lens') else 'cut'); sc.idx = i
            self.scenes.append(sc); self.starts.append(t); t += sc.dur
        self.total = t
        self.chunks = self.make_chunks() if self.cfg.get('captions') and self.words else []

    # ---------- голос → слова → тайминг сцен ----------
    def load_words(self):
        vo = self.cfg.get('voice')
        if not vo: return []
        wp = vo.get('words') or os.path.splitext(vo['file'])[0] + '.words.json'
        wp = wp if os.path.isabs(wp) else os.path.join(ROOT, wp)
        if not os.path.exists(wp): return []
        k = 1 / vo.get('tempo', 1.0); off = vo.get('offset', 0.0)
        return [dict(w=w['w'], start=w['start'] * k + off, end=w['end'] * k + off) for w in json.load(open(wp))['words']]

    def find(self, phrase, i0):
        key = [norm(x) for x in phrase.split()]
        for i in range(i0, len(self.words) - len(key) + 1):
            if [norm(self.words[i + j]['w']) for j in range(len(key))] == key: return i
        raise SystemExit(f'фраза «{phrase}» не найдена в голосе после слова {i0}')

    def timeline(self, specs):
        """сцена с 'from': «фраза» начинается чуть раньше этой фразы в голосе; длительности считаются сами"""
        if not self.words or not any('from' in s for s in specs): return
        starts, i0 = [], 0
        for k, s in enumerate(specs):
            if k == 0: starts.append(0.0); continue
            if 'from' in s:
                i = self.find(s['from'], i0); i0 = i + 1; starts.append(max(0.0, self.words[i]['start'] - s.get('lead', 0.12)))
            else: starts.append(None)
        for k, s in enumerate(specs):
            if starts[k] is None: continue
            j = next((j for j in range(k + 1, len(specs)) if starts[j] is not None), None)
            if j is not None:
                s['dur'] = round(starts[j] - starts[k] - sum(specs[m].get('dur', 1.5) for m in range(k + 1, j)), 3)
            elif s.get('to_end'):
                s['dur'] = round(self.words[-1]['end'] - starts[k] + s.get('tail', 1.2), 3)

    def make_chunks(self):
        out, cur = [], []
        for w in self.words:
            if cur and len(' '.join(x['w'] for x in cur + [w])) > CAP_CHARS: out.append(cur); cur = []
            cur.append(w)
            if w['w'][-1:] in '.?!,:' or len(cur) >= 3: out.append(cur); cur = []
        if cur: out.append(cur)
        res = []
        for k, c in enumerate(out):
            st = c[0]['start'] - 0.05; en = out[k + 1][0]['start'] - 0.05 if k + 1 < len(out) else c[-1]['end'] + 0.4
            if en - c[-1]['end'] > 0.6: en = c[-1]['end'] + 0.35
            res.append(dict(words=c, start=st, end=en))
        return res

    def caption(self, out, t):
        sc = self.scenes[self.at(t)[0]]
        if sc.s.get('captions') is False: return out
        ch = next((c for c in self.chunks if c['start'] <= t < c['end']), None)
        if not ch: return out
        pop = clamp((t - ch['start']) / 0.12)
        size = int(CAP_SIZE * (0.86 + 0.14 * back(pop))); f = font(size, 'Black'); sp = tlen(' ', f)
        ws = [w['w'].upper() for w in ch['words']]; widths = [tlen(w, f) for w in ws]
        while sum(widths) + sp * (len(ws) - 1) > CAP_W and size > 44:
            size -= 4; f = font(size, 'Black'); sp = tlen(' ', f); widths = [tlen(w, f) for w in ws]
        x = CAP_X - (sum(widths) + sp * (len(ws) - 1)) / 2
        d = ImageDraw.Draw(out)
        for w, wd, wo in zip(ws, widths, ch['words']):
            active = wo['start'] - 0.04 <= t < wo['end'] + 0.04 or (t >= wo['end'] and w is ws[-1])
            spoken = t >= wo['start'] - 0.04
            col = GOLD if active else (WHITE if spoken else (205, 205, 205))
            d.text((x, CAP_Y), w, font=f, fill=col + (255,), anchor='lm', stroke_width=10, stroke_fill=(0, 0, 0, 255))
            x += wd + sp
        return out

    def progress(self, out, t):
        n = self.cfg.get('progress')
        if not n: return out
        i, lt = self.at(t); step = self.scenes[i].s.get('step')
        if step is None: return out
        d = ImageDraw.Draw(out); x0, x1, y = 60, 1020, 212; gap = 14; w = (x1 - x0 - gap * (n - 1)) / n
        for k in range(n):
            xa = x0 + k * (w + gap); d.rounded_rectangle([xa, y, xa + w, y + 14], radius=7, fill=(255, 255, 255, 90))
            fill = 1 if k < step - 1 else (ease(lt / 0.5) if k == step - 1 else 0)
            if fill > 0: d.rounded_rectangle([xa, y, xa + w * fill, y + 14], radius=7, fill=GOLD + (255,))
        return out

    def at(self, t):
        for i in range(len(self.scenes) - 1, -1, -1):
            if t >= self.starts[i]: return i, t - self.starts[i]
        return 0, t

    def frame(self, t):
        i, lt = self.at(min(t, self.total - 1e-3)); sc = self.scenes[i]
        if sc.enter == 'zoomblur' and i > 0 and lt < TR / 2:              # уход предыдущей сцены с размытием
            prev = self.scenes[i - 1]; p = lt / (TR / 2)
            return zoom_blur(prev.frame(prev.dur - 1 / FPS).convert('RGB'), 1.04 + 0.5 * ease(p), 0.22 * ease(p))
        out = sc.frame(lt).convert('RGB')
        if sc.enter == 'zoomblur' and i > 0 and lt < TR:                  # влёт новой сцены
            p = (lt - TR / 2) / (TR / 2); out = zoom_blur(out, 1.22 - 0.2 * ease_out(p), 0.22 * (1 - ease_out(p)))
        if sc.enter == 'flash' and lt < 0.12:
            out = Image.blend(out, Image.new('RGB', (W, H), WHITE), 0.6 * (1 - lt / 0.12))
        if self.cfg.get('loop') and t > self.total - LOOP:      # петля: конец плавно перетекает в первый кадр
            out = Image.blend(out, self.scenes[0].frame(0.5).convert('RGB'), ease((t - self.total + LOOP) / LOOP))
            return out
        if self.chunks or self.cfg.get('progress'):
            o = out.convert('RGBA'); self.progress(o, t)
            if self.chunks: self.caption(o, t)
            out = o.convert('RGB')
        return out

    # ---------- автопроверка ----------
    def check(self):
        problems = []
        for sc in self.scenes:
            name = f"сцена {sc.idx + 1} ({sc.s['type']})"; bg = sc.bg(sc.settled()); boxes = sc.texts()
            for tb in boxes:
                x0, y0, x1, y1 = tb['box']; w = tb['what'][:30]
                if not safe_ok(tb['box']):
                        problems.append(f"{name}: «{w}» выходит из безопасной зоны {tuple(tb['box'])}")
                if tb['size'] < MIN_TEXT: problems.append(f"{name}: «{w}» слишком мелко ({tb['size']}px)")
                if not tb['panel']:
                    reg = np.asarray(bg.crop((max(0, x0), max(0, y0), min(W, x1), min(H, y1))).convert('RGB'), dtype=np.float32)
                    if reg.size:
                        mean = tuple(reg.reshape(-1, 3).mean(0)); c = contrast(tb['color'], mean)
                        if c < 3.0: problems.append(f"{name}: «{w}» плохо читается (контраст {c:.1f})")
            for a in range(len(boxes)):
                for b in range(a + 1, len(boxes)):
                    A, B = boxes[a]['box'], boxes[b]['box']
                    if A[0] < B[2] - 4 and B[0] < A[2] - 4 and A[1] < B[3] - 4 and B[1] < A[3] - 4:
                        problems.append(f"{name}: наложение «{boxes[a]['what'][:20]}» и «{boxes[b]['what'][:20]}»")
        for c in self.chunks:
            i = self.at((c['start'] + c['end']) / 2)[0]; sc = self.scenes[i]
            if sc.s.get('captions') is False: continue
            for tb in sc.texts():
                x0, y0, x1, y1 = tb['box']
                if y0 < CAP_Y + 50 and y1 > CAP_Y - 50:
                    problems.append(f"субтитр «{' '.join(w['w'] for w in c['words'])}» наезжает на «{tb['what'][:20]}» (сцена {i + 1})"); break
        if self.words and self.words[-1]['end'] > self.total: problems.append(f"голос ({self.words[-1]['end']:.1f} с) длиннее видео ({self.total:.1f} с)")
        if self.total > 60: problems.append(f'длина {self.total:.1f} с — больше 60 с')
        return problems

    # ---------- звук ----------
    def audio(self, path):
        buf = np.zeros(int((self.total + 0.6) * SR))
        def add(s, at, g=1.0):
            i = max(0, int(at * SR)); seg = s[:max(0, len(buf) - i)] * g; buf[i:i + len(seg)] += seg
        if self.cfg.get('ambient'): add(sfx('room')[:len(buf)], 0)
        vo = self.cfg.get('voice'); duck = 1.0
        if vo:
            src = vo['file'] if os.path.isabs(vo['file']) else os.path.join(ROOT, vo['file'])
            raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', src, '-af', f"atempo={vo.get('tempo', 1.0)}", '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'],
                                 capture_output=True, check=True).stdout
            v = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768 * vo.get('gain', 1.0)
            if len(v) > len(buf): buf = np.concatenate([buf, np.zeros(len(v) - len(buf))])
            add(v / max(1e-6, np.abs(v).max()) * 0.95, vo.get('offset', 0.0)); duck = vo.get('sfx_gain', 0.45)
        for sc, st in zip(self.scenes, self.starts):
            if sc.enter in ('flash', 'zoomblur') and st > 0: add(sfx('whoosh_long' if sc.enter == 'zoomblur' else 'whoosh'), st - 0.25, duck)
            if sc.enter == 'zoomblur' and st > 0: add(sfx('boom'), st + 0.15, 0.8 * duck)
            for t, name, g in sc.events(): add(sfx(name), st + t, g * duck)
        buf = np.tanh(buf * 1.1)
        with wave.open(path, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((buf * 30000).astype(np.int16).tobytes())

    def render(self, out_dir):
        os.makedirs(out_dir, exist_ok=True); wav = os.path.join(out_dir, '_sfx.wav'); mp4 = os.path.join(out_dir, 'reel.mp4')
        self.audio(wav)
        p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
                              '-i', '-', '-i', wav, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p',
                              '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', mp4], stdin=subprocess.PIPE)
        for fi in range(int(self.total * FPS)): p.stdin.write(self.frame(fi / FPS).tobytes())
        p.stdin.close(); p.wait(); os.remove(wav)
        meta = []
        for sc, st in zip(self.scenes, self.starts):
            th = f'scene{sc.idx + 1:02d}.jpg'; self.frame(st + sc.settled()).resize((240, 427)).save(os.path.join(out_dir, th), quality=78)
            meta.append(dict(n=sc.idx + 1, type=sc.s['type'], start=round(st, 2), end=round(st + sc.dur, 2),
                             label=sc.s.get('text') or ' / '.join(sc.s.get('lines', [])) or sc.s.get('title') or sc.s.get('line1', '') or sc.s['type'], thumb=th))
        json.dump(dict(id=self.id, title=self.cfg.get('title', self.id), duration=round(self.total, 2), scenes=meta), open(os.path.join(out_dir, 'scenes.json'), 'w'), ensure_ascii=False, indent=1)
        return mp4

if __name__ == '__main__':
    cmd, path = sys.argv[1], sys.argv[2]
    var = next((int(a.split('=')[1]) - 1 for a in sys.argv if a.startswith('--hook=')), None); r = Reel(path, var)
    probs = r.check()
    print(f'{r.id}: {len(r.scenes)} сцен, {r.total:.1f} с'); print('\n'.join('  ! ' + p for p in probs) or '  проверка: всё чисто')
    if cmd == 'stills':
        d = f'/tmp/zv_{r.id}'; os.makedirs(d, exist_ok=True)
        for sc, st in zip(r.scenes, r.starts): r.frame(st + sc.settled()).save(f'{d}/{sc.idx + 1:02d}.jpg', quality=80)
        print(d)
    elif cmd == 'render':
        if probs and '--force' not in sys.argv: sys.exit('есть замечания — исправьте или --force')
        print(r.render(sys.argv[3]))
