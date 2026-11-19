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

def resolve(spec):
    for k in ('img', 'before', 'after'):
        if k in spec and not os.path.isabs(spec[k]): spec[k] = os.path.join(ROOT, spec[k])
    return spec

class Reel:
    def __init__(self, path):
        self.cfg = json.load(open(path)); self.id = self.cfg.get('id', os.path.splitext(os.path.basename(path))[0])
        brand = dict(BRAND, **self.cfg.get('brand', {}))
        if brand.get('logo') and not os.path.isabs(brand['logo']): brand['logo'] = os.path.join(ROOT, brand['logo'])
        if brand.get('logo') and not os.path.exists(brand['logo']): brand['logo'] = None
        ctx = dict(brand=brand, root=ROOT)
        self.scenes, self.starts, t = [], [], 0.0
        for i, s in enumerate(self.cfg['scenes']):
            sc = LIBRARY[s['type']](resolve(dict(s)), ctx)
            sc.enter = s.get('enter', 'flash' if s['type'] == 'photo' else 'cut'); sc.idx = i
            self.scenes.append(sc); self.starts.append(t); t += sc.dur
        self.total = t

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
    cmd, path = sys.argv[1], sys.argv[2]; r = Reel(path)
    probs = r.check()
    print(f'{r.id}: {len(r.scenes)} сцен, {r.total:.1f} с'); print('\n'.join('  ! ' + p for p in probs) or '  проверка: всё чисто')
    if cmd == 'stills':
        d = f'/tmp/zv_{r.id}'; os.makedirs(d, exist_ok=True)
        for sc, st in zip(r.scenes, r.starts): r.frame(st + sc.settled()).save(f'{d}/{sc.idx + 1:02d}.jpg', quality=80)
        print(d)
    elif cmd == 'render':
        if probs and '--force' not in sys.argv: sys.exit('есть замечания — исправьте или --force')
        print(r.render(sys.argv[3]))
