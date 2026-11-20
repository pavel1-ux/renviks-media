"""Библиотека сцен. Каждая сцена: dur, frame(t)->RGBA, bg(t)->RGB без надписей, events()->звуки,
texts()->список текстовых блоков в итоговом положении (для автопроверки).
Добавить сцену: класс + запись в LIBRARY."""
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from core import *

class Scene:
    dur = 1.5
    def __init__(self, s, ctx):
        self.s = s; self.ctx = ctx; self.dur = s.get('dur', self.dur); self._texts = []
    def bg(self, t): return Image.new('RGB', (W, H), NAVY)
    def frame(self, t): return self.bg(t).convert('RGBA')
    def events(self): return []
    def texts(self): return self._texts
    def settled(self): return self.dur * 0.8          # момент, когда всё на месте
    def add_text(self, box, size, col, panel, what):
        self._texts.append(dict(box=[int(v) for v in box], size=int(size), color=col, panel=panel, what=what))

# ---------- крючок: крупный заголовок + НЕТ/ДА + подзаголовок ----------
class Hook(Scene):
    dur = 1.5
    def __init__(self, s, ctx):
        super().__init__(s, ctx)
        self.img = photo(s['img']).filter(ImageFilter.GaussianBlur(14)) if s.get('img') else None
        self.lines = s['lines']; self.marks = s.get('marks', False); self.sub = s.get('sub', '')
        self.size = min(fit_size(l, s.get('size', 132), 'Black', 960) for l in self.lines)
        self.y_title = 400
        self.sub_size = fit_size(self.sub, 58, 'ExtraBold', 960) if self.sub else 0
        y = 400
        for l in self.lines:
            tw = tlen(l, font(self.size)); self.add_text((W / 2 - tw / 2, y + self.size * 0.1, W / 2 + tw / 2, y + self.size * 1.05), self.size, WHITE, False, l); y += self.size * 1.14
        self.y_sub = y + 40; self.y_marks = self.y_sub + (self.sub_size * 1.4 if self.sub else 0) + 190
        if self.sub:
            tw = tlen(self.sub, font(self.sub_size, 'ExtraBold'))
            self.add_text((W / 2 - tw / 2, self.y_sub, W / 2 + tw / 2, self.y_sub + self.sub_size * 1.2), self.sub_size, GOLD, False, self.sub)
    def bg(self, t):
        if self.img is None: return Image.new('RGB', (W, H), NAVY)
        out = self.img.copy().convert('RGBA'); out.alpha_composite(Image.new('RGBA', (W, H), (8, 12, 20, 165))); return out.convert('RGB')
    def frame(self, t):
        out = self.bg(t).convert('RGBA'); y = self.y_title
        for k, l in enumerate(self.lines):
            a = back((t - 0.1 * k) / 0.25)
            if a > 0: paste(out, text_layer(l, self.size, WHITE), W / 2, y + self.size * 0.6, scale=0.5 + 0.5 * a)
            y += self.size * 1.14
        if self.marks:
            for k, (kind, word, col, dx) in enumerate([('net', 'НЕТ', RED, -200), ('da', 'ДА', GREEN, 200)]):
                b = back((t - 0.3 - 0.25 * k) / 0.25)
                if b > 0:
                    paste(out, mark(kind), W / 2 + dx, self.y_marks, scale=b * 1.25)
                    paste(out, text_layer(word, 110, col), W / 2 + dx, self.y_marks + 200, alpha=clamp((t - 0.3 - 0.25 * k) / 0.12))
            
        if self.sub and t > 0.15:
            paste(out, text_layer(self.sub, self.sub_size, GOLD, 'ExtraBold'), W / 2, self.y_sub + self.sub_size * 0.6, alpha=clamp((t - 0.15) / 0.15))
        return out
    def events(self):
        e = [(0, 'impact', 1), (0.05, 'pop', 1)]
        if self.marks: e += [(0.3, 'buzz', 1), (0.32, 'pop', 1), (0.56, 'ding', 1), (0.57, 'pop', 1)]
        return e

# ---------- фото: камера + кольцо + ✕/✓ + плашка + размерная линия + счётчик ----------
class PhotoScene(Scene):
    dur = 1.5
    def __init__(self, s, ctx):
        super().__init__(s, ctx)
        self.img = photo(s['img'], s.get('exposure', 1.0), s.get('contrast', 1.0)) if s.get('img') else None; self.kind = s.get('kind'); self.fx, self.fy = s.get('focus', [W / 2, H / 2])
        self.zoom = s.get('zoom', 'punch' if self.kind == 'net' else ('drift' if self.kind == 'da' else 'push'))
        self.label = None
        if s.get('text'):
            badge = s.get('badge', {'net': 'НЕТ', 'da': 'ДА'}.get(self.kind))
            col = {'net': RED, 'da': GREEN}.get(self.kind, GOLD)
            self.label = pill(badge, col, s['text'])
            self.lx = SAFE[0] + self.label.width / 2; self.ly = max(s.get('label_y', 330), 272 + self.label.height / 2)
            self.add_text((SAFE[0], self.ly - self.label.height / 2, SAFE[0] + self.label.width, self.ly + self.label.height / 2), 60, WHITE, True, s['text'])
        self.counter = s.get('counter')
        if self.counter: self.add_text((SAFE[0], 190, SAFE[0] + 120, 250), 40, WHITE, True, self.counter)
    def z(self, t):
        p = t / self.dur
        if self.zoom == 'punch': return 1.0 + 0.32 * ease_out((t - 0.15) / 0.35) + 0.03 * t
        if self.zoom == 'drift': return 1.08 - 0.06 * ease_out(t / 1.2)
        if self.zoom == 'push': return self.s.get('z0', 1.0) + (self.s.get('z1', 1.08) - self.s.get('z0', 1.0)) * ease(p)
        return 1.0
    def bg(self, t): return cam(self.img, self.z(t), self.fx, self.fy)[0]
    def frame(self, t):
        base, box = cam(self.img, self.z(t), self.fx, self.fy); out = base.convert('RGBA')
        if self.kind == 'net': out.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, int(60 * ease((t - 0.2) / 0.3)))))
        d = ImageDraw.Draw(out); px, py = map_pt(self.fx, self.fy, box)
        if self.kind:
            col = RED if self.kind == 'net' else GREEN; pr = ease((t - 0.3) / 0.25); r = self.s.get('ring', 150)
            if pr > 0: d.arc([px - r, py - r, px + r, py + r], -90, -90 + 360 * pr, fill=col + (255,), width=12)
        if self.s.get('dim'): self._dim(d, box, ease((t - 0.35) / 0.3))
        if self.kind:
            m = back((t - 0.42) / 0.22)
            if m > 0:
                mx = min(px + self.s.get('mark_dx', 120), SAFE[2] - 60); my = py - self.s.get('mark_dy', 130)
                paste(out, mark(self.kind), mx, my, scale=m * 0.95, rot=8 if self.kind == 'net' else 0)
        if self.label is not None:
            s = back(t / 0.22)
            if s > 0: paste(out, self.label, SAFE[0] + self.label.width * s / 2, self.ly, scale=s)
        if self.counter:
            f = font(40, 'ExtraBold'); d.rounded_rectangle([SAFE[0], 190, SAFE[0] + 120, 250], radius=18, fill=(0, 0, 0, 150))
            d.text((SAFE[0] + 60, 220), self.counter, font=f, fill=WHITE, anchor='mm')
        if self.kind == 'net' and 0.42 < t < 0.6:
            amp = 14 * (1 - (t - 0.42) / 0.18); dx, dy = _rngf(t).uniform(-amp, amp, 2)
            c = Image.new('RGBA', (W, H), DARK + (255,)); c.alpha_composite(out, (int(dx), int(dy))); out = c
        return out
    def _dim(self, d, box, prog):
        if prog <= 0: return
        (a, b, label) = self.s['dim']; (x1, y1), (x2, y2) = map_pt(*a, box), map_pt(*b, box)
        xm, ym = x1 + (x2 - x1) * prog, y1 + (y2 - y1) * prog; col = GOLD + (255,)
        d.line([x1, y1, xm, ym], fill=col, width=8)
        ang = math.atan2(y2 - y1, x2 - x1); nx, ny = -math.sin(ang) * 26, math.cos(ang) * 26
        d.line([x1 - nx, y1 - ny, x1 + nx, y1 + ny], fill=col, width=8)
        if prog >= 1:
            d.line([x2 - nx, y2 - ny, x2 + nx, y2 + ny], fill=col, width=8)
            f = font(58, 'Black'); mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 62; tw = d.textlength(label, font=f)
            d.rounded_rectangle([mx - tw / 2 - 22, my - 40, mx + tw / 2 + 22, my + 40], radius=20, fill=GOLD + (255,))
            d.text((mx, my), label, font=f, fill=DARK, anchor='mm')
    def events(self):
        if self.kind == 'net': return [(0.05, 'pop', 1), (0.42, 'impact', 0.7), (0.44, 'buzz', 1)]
        if self.kind == 'da': return [(0.05, 'pop', 1), (0.44, 'ding', 1)]
        return []

def _rngf(t): return np.random.default_rng(int(t * 1000))

# ---------- стадия: только камера (формат «Этапы») ----------
class Stage(PhotoScene):
    dur = 1.5
    def __init__(self, s, ctx):
        s = dict(s); s.setdefault('zoom', 'push'); super().__init__(s, ctx)

# ---------- чек-лист: пункты появляются по одному с галочками ----------
class Checklist(Scene):
    dur = 4.0
    def __init__(self, s, ctx):
        super().__init__(s, ctx)
        self.img = photo(s['img']).filter(ImageFilter.GaussianBlur(10)) if s.get('img') else None
        self.title = s['title']; self.items = s['items']
        self.ts = fit_size(self.title, 84, 'Black', SAFE[2] - SAFE[0])
        self.step = (self.dur - 0.9) / max(1, len(self.items))
        self.add_text((SAFE[0], 300, SAFE[0] + tlen(self.title, font(self.ts)), 300 + self.ts * 1.2), self.ts, WHITE, False, self.title)
        self.rows = []; y = 300 + self.ts * 1.6
        for it in self.items:
            lines = wrap(it, font(54, 'Bold'), SAFE[2] - SAFE[0] - 130); h = 40 + 64 * len(lines)
            self.rows.append((y, lines, h)); self.add_text((SAFE[0], y, SAFE[2], y + h), 54, WHITE, True, it); y += h + 26
    def bg(self, t):
        if self.img is None: return Image.new('RGB', (W, H), NAVY)
        o = self.img.convert('RGBA'); o.alpha_composite(Image.new('RGBA', (W, H), (8, 12, 20, 175))); return o.convert('RGB')
    def frame(self, t):
        out = self.bg(t).convert('RGBA'); d = ImageDraw.Draw(out)
        a = back(t / 0.25)
        if a > 0: paste(out, text_layer(self.title, self.ts, WHITE), SAFE[0] + tlen(self.title, font(self.ts)) / 2 + 20, 300 + self.ts * 0.6, scale=0.6 + 0.4 * a)
        for k, (y, lines, h) in enumerate(self.rows):
            p = back((t - 0.5 - k * self.step) / 0.25)
            if p <= 0: continue
            x0 = SAFE[0] - 200 * (1 - min(1, p))
            d.rounded_rectangle([x0, y, SAFE[2], y + h], radius=26, fill=DARK + (225,))
            paste(out, mark('da', 34), x0 + 60, y + h / 2, scale=min(1.2, p))
            yy = y + h / 2 - 32 * (len(lines) - 1)
            for l in lines: d.text((x0 + 120, yy), l, font=font(54, 'Bold'), fill=WHITE, anchor='lm'); yy += 64
        return out
    def events(self):
        return [(0, 'impact', 0.8)] + [(0.5 + k * self.step, 'ding', 0.8) for k in range(len(self.items))]

# ---------- до/после: шторка-разделитель ----------
class BeforeAfter(Scene):
    dur = 3.0
    def __init__(self, s, ctx):
        super().__init__(s, ctx); self.a = photo(s['before']); self.b = photo(s['after'])
        for word, x in [(s.get('before_label', 'ДО'), SAFE[0]), (s.get('after_label', 'ПОСЛЕ'), SAFE[2] - 260)]:
            self.add_text((x, 1380, x + 260, 1470), 60, WHITE, True, word)
    def pos(self, t): return W * (1 - ease((t - 0.4) / (self.dur - 1.0)))
    def bg(self, t):
        x = int(self.pos(t)); o = self.b.copy(); o.paste(self.a.crop((0, 0, x, H)), (0, 0)) if x > 0 else None; return o
    def frame(self, t):
        z = 1.0 + 0.05 * t / self.dur; out = cam(self.bg(t), z)[0].convert('RGBA'); d = ImageDraw.Draw(out); x = self.pos(t)
        if 0 < x < W:
            d.rectangle([x - 4, 0, x + 4, H], fill=WHITE); d.ellipse([x - 44, H / 2 - 44, x + 44, H / 2 + 44], fill=WHITE)
            d.polygon([(x - 26, H / 2), (x - 8, H / 2 - 16), (x - 8, H / 2 + 16)], fill=DARK); d.polygon([(x + 26, H / 2), (x + 8, H / 2 - 16), (x + 8, H / 2 + 16)], fill=DARK)
        for word, xx in [(self.s.get('before_label', 'ДО'), SAFE[0]), (self.s.get('after_label', 'ПОСЛЕ'), SAFE[2] - 260)]:
            d.rounded_rectangle([xx, 1380, xx + 260, 1470], radius=26, fill=DARK + (220,)); d.text((xx + 130, 1425), word, font=font(60), fill=WHITE, anchor='mm')
        return out
    def events(self): return [(0.4, 'whoosh_long', 1)]

# ---------- финал бренда ----------
class EndBrand(Scene):
    dur = 2.4
    def __init__(self, s, ctx):
        super().__init__(s, ctx); b = ctx['brand']
        self.l1, self.l2 = s.get('line1', ''), s.get('line2', ''); self.contact = s.get('contact', 'Пишите: ' + b['contact'])
        self.save = s.get('save', 'Сохраните, чтобы не забыть'); self.ls = min(fit_size(self.l1, 64, 'ExtraBold', 960), fit_size(self.l2, 64, 'ExtraBold', 960))
        self.cs = fit_size(self.contact, 56, 'ExtraBold', 700); self.ss = fit_size(self.save, 46, 'Medium', 780)
        self.logo = b.get('logo'); self.ly1, self.ly2 = (420, 510) if self.logo else (560, 650)
        if self.logo:
            for txt, y, sz, cx in [(self.l1, 420, self.ls, W / 2), (self.l2, 510, self.ls, W / 2), (self.save, 1360, self.ss, LOW_CX)]:
                if txt: tw = tlen(txt, font(sz, 'ExtraBold' if y < 600 else 'Medium')); self.add_text((cx - tw / 2, y, cx + tw / 2, y + sz * 1.0), sz, WHITE, False, txt)
            tw = tlen(self.contact, font(self.cs, 'ExtraBold')) + 72; self.add_text((LOW_CX - tw / 2, 1190, LOW_CX + tw / 2, 1290), self.cs, WHITE, True, self.contact)
            return
        for txt, y, sz, cx in [(self.l1, 560, self.ls, W / 2), (self.l2, 650, self.ls, W / 2), (b['name'], 880, 150, W / 2), (b['tagline'], 1040, 48, W / 2),
                               (self.contact, 1190, self.cs + 36, LOW_CX), (self.save, 1360, self.ss, LOW_CX)]:
            if txt:
                wt = 'SemiBold' if txt == b['tagline'] else ('Medium' if txt == self.save else ('ExtraBold' if sz < 100 else 'Black'))
                tw = tlen(txt, font(sz, wt)) if txt != self.contact else tlen(txt, font(self.cs, 'ExtraBold')) + 72
                self.add_text((cx - tw / 2, y, cx + tw / 2, y + min(sz, 150) * 1.0), sz, WHITE, txt == self.contact, txt)
    def bg(self, t):
        base = logo_bg(self.logo) if getattr(self, 'logo', None) else NAVY
        o = Image.new('RGB', (W, H), base); d = ImageDraw.Draw(o); ln = tuple(min(255, v + 9) for v in base)
        for k in range(-4, 14): x = k * 160 + (t * 120) % 160; d.line([x, 0, x - 900, H], fill=ln, width=40)
        return o
    def frame(self, t):
        out = self.bg(t).convert('RGBA'); d = ImageDraw.Draw(out); b = self.ctx['brand']; a = back(t / 0.3)
        for txt, y in [(self.l1, self.ly1), (self.l2, self.ly2)]:
            if txt: paste(out, text_layer(txt, self.ls, WHITE, 'ExtraBold'), W / 2, y + self.ls * 0.6, scale=0.7 + 0.3 * a, alpha=clamp(t / 0.2))
        bb = back((t - 0.35) / 0.3)
        if bb > 0:
            if self.logo: paste(out, logo_layer(self.logo, 640), W / 2, 870, scale=0.6 + 0.4 * bb, alpha=clamp((t - 0.35) / 0.2))
            else:
                paste(out, text_layer(b['name'], 150, GOLD), W / 2, 950, scale=0.5 + 0.5 * bb)
                paste(out, text_layer(b['tagline'], 48, WHITE, 'SemiBold'), W / 2, 1068, alpha=clamp((t - 0.4) / 0.2))
        c = back((t - 0.7) / 0.3)
        if c > 0:
            f = font(self.cs, 'ExtraBold'); tw = tlen(self.contact, f)
            d.rounded_rectangle([LOW_CX - tw / 2 - 36, 1180, LOW_CX + tw / 2 + 36, 1290], radius=40, fill=GOLD); d.text((LOW_CX, 1235), self.contact, font=f, fill=DARK, anchor='mm')
        if self.save and t > 1.1: paste(out, text_layer(self.save, self.ss, WHITE, 'Medium'), LOW_CX, 1390, alpha=clamp((t - 1.1) / 0.2))
        return out
    def events(self): return [(0.35, 'impact', 0.8), (0.72, 'pop', 1)]

# ---------- финал-логотип (как у дизайн-студий) ----------
class EndLogo(Scene):
    dur = 1.3
    def __init__(self, s, ctx):
        super().__init__(s, ctx); b = ctx['brand']
        if b.get('logo'):
            tw = tlen(b['contact'], font(46, 'SemiBold')); self.add_text((W / 2 - tw / 2, 1380, W / 2 + tw / 2, 1436), 46, WHITE, False, b['contact']); return
        for txt, y, sz in [('Р Е Н В И К С', 860, 78), (b['tagline'] + ' · Москва', 980, 44), (b['contact'], 1060, 46)]:
            tw = tlen(txt, font(sz, 'SemiBold')); self.add_text((W / 2 - tw / 2, y, W / 2 + tw / 2, y + sz * 1.2), sz, WHITE, False, txt)
    def card(self, a):
        b = self.ctx['brand']; out = Image.new('RGB', (W, H), BLACK); d = ImageDraw.Draw(out)
        c = tuple(int(235 * a) for _ in range(3)); g = tuple(int(v * a) for v in GOLD); cx, cy = W // 2, 740
        if b.get('logo'):
            bgc = logo_bg(b['logo']); o = Image.new('RGBA', (W, H), tuple(int(v * min(1, a * 1.5)) for v in bgc) + (255,))
            paste(o, logo_layer(b['logo'], 1000), W / 2, 860, scale=0.92 + 0.08 * a, alpha=a)
            f = font(46, 'SemiBold'); dd = ImageDraw.Draw(o); t = b['contact']
            dd.text((W / 2 - dd.textlength(t, font=f) / 2, 1380), t, font=f, fill=tuple(int(235 * a) for _ in range(3)))
            return o.convert('RGB')
        d.line([cx - 95, cy + 70, cx - 95, cy - 20, cx, cy - 105, cx + 95, cy - 20, cx + 95, cy + 70], fill=c, width=5, joint='curve')
        d.line([cx - 25, cy + 70, cx - 25, cy + 5, cx + 25, cy + 5, cx + 25, cy + 70], fill=g, width=5); d.line([cx + 140, cy - 150, cx + 40, cy - 60], fill=c, width=3)
        f = font(78, 'SemiBold'); txt = 'Р Е Н В И К С'; tw = d.textlength(txt, font=f); d.text((cx - tw / 2, cy + 120), txt, font=f, fill=c)
        d.line([cx - 330, cy + 165, cx - tw / 2 - 30, cy + 165], fill=c, width=2); d.line([cx + tw / 2 + 30, cy + 165, cx + 330, cy + 165], fill=c, width=2)
        for txt, y, sz, col in [(b['tagline'] + ' · Москва', cy + 240, 44, g), (b['contact'], cy + 320, 46, c)]:
            f = font(sz, 'SemiBold'); d.text((cx - d.textlength(txt, font=f) / 2, y), txt, font=f, fill=col)
        return out
    def bg(self, t): return Image.new('RGB', (W, H), BLACK)
    def frame(self, t):
        p = t / self.dur; return self.card(ease((p - 0.15) / 0.45)).convert('RGBA')
    def events(self): return [(0.3, 'shimmer', 1)]

# ---------- клип: живое видео с объекта ----------
import subprocess, json as _json
def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height:stream_side_data=rotation:format=duration',
                          '-of', 'json', path], capture_output=True, text=True).stdout
    j = _json.loads(out); st = j['streams'][0]; w, h = st['width'], st['height']
    rot = 0
    for sd in st.get('side_data_list', []) or []:
        if 'rotation' in sd: rot = abs(int(sd['rotation']))
    if rot in (90, 270): w, h = h, w
    return w, h, float(j['format']['duration'])

class Clip(PhotoScene):
    """src, start, dur, speed (1 = норм., 2 = ускорение), mode cover|fit (fit: горизонтальное видео на размытом фоне),
    focus_x (0..1, куда сдвинуть кадр при cover), + всё от photo: kind, text, ring, focus, dim, counter. zoom по умолчанию 'none'."""
    dur = 2.5
    def __init__(self, s, ctx):
        s = dict(s); s.setdefault('zoom', 'none'); s['img'] = None
        Scene.__init__(self, s, ctx)
        self.src = s['src'] if os.path.isabs(s['src']) else os.path.join(ctx['root'], s['src'])
        self.vw, self.vh, self.vdur = probe(self.src)
        self.start = s.get('start', 0.0); self.speed = s.get('speed', 1.0)
        self.mode = s.get('mode', 'cover' if self.vh >= self.vw else 'fit')
        self.kind = s.get('kind'); self.fx, self.fy = s.get('focus', [W / 2, H / 2]); self.zoom = s['zoom']
        self.label = None; self._texts = []
        if s.get('text'):
            badge = s.get('badge', {'net': 'НЕТ', 'da': 'ДА'}.get(self.kind)); col = {'net': RED, 'da': GREEN}.get(self.kind, GOLD)
            self.label = pill(badge, col, s['text']); self.ly = max(s.get('label_y', 330), 272 + self.label.height / 2)
            self.add_text((SAFE[0], self.ly - self.label.height / 2, SAFE[0] + self.label.width, self.ly + self.label.height / 2), 60, WHITE, True, s['text'])
        self.counter = s.get('counter')
        if self.counter: self.add_text((SAFE[0], 190, SAFE[0] + 120, 250), 40, WHITE, True, self.counter)
        self._proc = None; self._next = None; self._last = None
    def _vf(self):
        sp = f'setpts=PTS/{self.speed},' if self.speed != 1 else ''
        if self.mode == 'cover':
            fx = self.s.get('focus_x', 0.5)
            return f"{sp}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}:(iw-{W})*{fx}:(ih-{H})/2,fps={FPS},format=rgb24"
        return (f"{sp}split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=28:2,eq=brightness=-0.12[bg];"
                f"[b]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2-{self.s.get('fit_up', 120)},fps={FPS},format=rgb24")
    def _open(self, t):
        if self._proc: self._proc.kill()
        ss = self.start + t * self.speed
        self._proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', f'{ss:.3f}', '-i', self.src, '-t', f'{(self.dur - t) * self.speed + 0.5:.3f}',
                                       '-filter_complex', self._vf(), '-an', '-f', 'rawvideo', '-'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self._next = round(t * FPS)
    def video(self, t):
        fi = round(t * FPS)
        if self._proc is None or fi != self._next:
            if self._last is not None and fi == self._next - 1: return self._last
            self._open(t)
        raw = self._proc.stdout.read(W * H * 3); self._next += 1
        if len(raw) < W * H * 3: return self._last or Image.new('RGB', (W, H), DARK)
        self._last = Image.frombytes('RGB', (W, H), raw); return self._last
    def bg(self, t): return cam(self.video(t), self.z(t), self.fx, self.fy)[0]
    def frame(self, t):
        self.img = self.video(t); return PhotoScene.frame(self, t)
    def z(self, t):
        return 1.0 if self.zoom == 'none' else PhotoScene.z(self, t)

LIBRARY = {'hook': Hook, 'photo': PhotoScene, 'stage': Stage, 'checklist': Checklist,
           'before_after': BeforeAfter, 'clip': Clip, 'end_brand': EndBrand, 'end_logo': EndLogo}

# ================= v3: сцены с движением =================

# ---------- квиз-крючок: фото + крупный вопрос + таймер обратного отсчёта ----------
class Quiz(PhotoScene):
    """img, title (крупно, 1-2 строки через |), sub, count (секунд отсчёта, 0 = без таймера). Камера медленно наезжает."""
    dur = 3.0
    def __init__(self, s, ctx):
        s = dict(s); s.setdefault('zoom', 'push'); s.setdefault('z1', 1.12); s['text'] = None; s['kind'] = None
        super().__init__(s, ctx)
        self.lines = s['title'].split('|'); self.sub = s.get('sub', ''); self.count = s.get('count', 3)
        self.ts = min(fit_size(l, s.get('size', 112), 'Black', 940) for l in self.lines)
        y = 300
        for l in self.lines:
            tw = tlen(l, font(self.ts)); self.add_text((W / 2 - tw / 2, y, W / 2 + tw / 2, y + self.ts * 1.1), self.ts, WHITE, True, l); y += self.ts * 1.18
        self.y_sub = y + 20; self.ss = fit_size(self.sub, 56, 'ExtraBold', 900) if self.sub else 0
        if self.sub:
            tw = tlen(self.sub, font(self.ss, 'ExtraBold')); self.add_text((W / 2 - tw / 2 - 30, self.y_sub, W / 2 + tw / 2 + 30, self.y_sub + self.ss * 1.5), self.ss, DARK, True, self.sub)
    def frame(self, t):
        out = PhotoScene.frame(self, t)
        g = Image.new('RGBA', (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(g)
        for k in range(40): gd.rectangle([0, k * 22, W, k * 22 + 22], fill=(0, 0, 0, int(150 * (1 - k / 40))))
        out.alpha_composite(g); y = 300
        for k, l in enumerate(self.lines):
            a = back((t - 0.12 * k) / 0.28)
            if a > 0: paste(out, text_layer(l, self.ts, WHITE), W / 2, y + self.ts * 0.6, scale=0.4 + 0.6 * a)
            y += self.ts * 1.18
        if self.sub:
            a = back((t - 0.45) / 0.25)
            if a > 0:
                f = font(self.ss, 'ExtraBold'); tw = tlen(self.sub, f)
                lay = Image.new('RGBA', (int(tw + 60), int(self.ss * 1.5)), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
                ld.rounded_rectangle([0, 0, lay.width - 1, lay.height - 1], radius=26, fill=GOLD + (255,)); ld.text((lay.width / 2, lay.height / 2), self.sub, font=f, fill=DARK, anchor='mm')
                paste(out, lay, W / 2, self.y_sub + lay.height / 2, scale=a, rot=-2)
        if self.count:
            st = 0.7; left = self.count - (t - st)
            if t > st and left > 0:
                cx, cy, r = W / 2, 1000, 105; d = ImageDraw.Draw(out); frac = left - math.floor(left)
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=DARK + (215,))
                d.arc([cx - r + 8, cy - r + 8, cx + r - 8, cy + r - 8], -90, -90 + 360 * frac, fill=GOLD + (255,), width=14)
                n = str(math.ceil(left)); p = back(1 - frac) if frac > 0.75 else 1
                paste(out, text_layer(n, 120, WHITE, shadow=False), cx, cy + 8, scale=0.6 + 0.4 * min(1, (1 - frac) / 0.25 + 0.0) if frac > 0.75 else 1)
        return out
    def events(self):
        e = [(0, 'impact', 1), (0.05, 'pop', 1), (0.45, 'pop', 0.8)]
        e += [(0.7 + k, 'tick', 1.4) for k in range(self.count)]
        return e

# ---------- лупа: увеличенный круг на месте ошибки ----------
class Lens(PhotoScene):
    """img, kind net|da, text, focus [x,y], lens_r (радиус лупы), lens_z (увеличение), lens_at [x,y] — где висит лупа (по умолчанию над точкой)."""
    dur = 2.2
    def __init__(self, s, ctx):
        s = dict(s); s.setdefault('zoom', 'push'); s.setdefault('z1', 1.04); s.setdefault('ring', 0)
        super().__init__(s, ctx)
        self.lr = s.get('lens_r', 230); self.lz = s.get('lens_z', 2.2)
        fx, fy = self.fx, self.fy; self.lat = s.get('lens_at', [min(max(fx, self.lr + 70), W - self.lr - 70), min(max(fy - 150, 640), 800)])
    def frame(self, t):
        base, box = cam(self.img, self.z(t), self.fx, self.fy); out = base.convert('RGBA')
        dim = 110 * ease((t - 0.15) / 0.3); out.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, int(dim))))
        p = back((t - 0.15) / 0.35)
        if p > 0:
            r = self.lr; z = self.lz * (0.85 + 0.15 * ease((t - 0.15) / 0.8))
            src = self.img; cw = 2 * r / z
            crop = src.resize((2 * r, 2 * r), Image.BICUBIC, box=(self.fx - cw / 2, self.fy - cw / 2, self.fx + cw / 2, self.fy + cw / 2)).convert('RGBA')
            m = Image.new('L', (2 * r, 2 * r), 0); ImageDraw.Draw(m).ellipse([0, 0, 2 * r - 1, 2 * r - 1], fill=255); crop.putalpha(m)
            lens = Image.new('RGBA', (2 * r + 40, 2 * r + 40), (0, 0, 0, 0)); ld = ImageDraw.Draw(lens)
            ld.ellipse([8, 14, 2 * r + 32, 2 * r + 38], fill=(0, 0, 0, 120)); lens.alpha_composite(crop, (20, 20))
            col = RED if self.kind == 'net' else GREEN; ld.ellipse([14, 14, 2 * r + 26, 2 * r + 26], outline=col + (255,), width=14)
            # линия от точки к лупе
            px, py = map_pt(self.fx, self.fy, box); lx, ly = self.lat
            d = ImageDraw.Draw(out); d.line([px, py, lx, ly], fill=col + (int(255 * min(1, p)),), width=8); d.ellipse([px - 14, py - 14, px + 14, py + 14], fill=col + (255,))
            paste(out, lens, lx, ly, scale=min(1.05, p))
            m2 = back((t - 0.5) / 0.22)
            if m2 > 0: paste(out, mark(self.kind, 70), lx + r * 0.72, ly - r * 0.72, scale=m2, rot=8 if self.kind == 'net' else 0)
        if self.label is not None:
            s = back(t / 0.22)
            if s > 0: paste(out, self.label, SAFE[0] + self.label.width * s / 2, self.ly, scale=s)
        return out
    def events(self):
        return [(0.05, 'pop', 1), (0.15, 'whoosh', 0.8), (0.5, 'impact' if self.kind == 'net' else 'ding', 0.8), (0.52, 'buzz' if self.kind == 'net' else 'pop', 1)]

# ---------- сплит: НЕТ сверху / ДА снизу ----------
class Split(Scene):
    """net (img), da (img), net_text, da_text, net_focus, da_focus"""
    dur = 2.4
    def __init__(self, s, ctx):
        super().__init__(s, ctx)
        self.a = photo(s['net']); self.b = photo(s['da'])
        self.fa = s.get('net_focus', [W / 2, H / 2]); self.fb = s.get('da_focus', [W / 2, H / 2])
        self.la = pill('НЕТ', RED, s.get('net_text', ''), maxw=680, size=56); self.lb = pill('ДА', GREEN, s.get('da_text', ''), maxw=600, size=56)
        self.ya = 272 + self.la.height / 2; self.yb = H // 2 + 30 + self.lb.height / 2
        self.add_text((SAFE[0], self.ya - self.la.height / 2, SAFE[0] + self.la.width, self.ya + self.la.height / 2), 54, WHITE, True, s.get('net_text', ''))
        self.add_text((SAFE[0], self.yb - self.lb.height / 2, SAFE[0] + self.lb.width, self.yb + self.lb.height / 2), 54, WHITE, True, s.get('da_text', ''))
    def half(self, img, f, z):
        h = H // 2; cw, ch = W / z, h / z
        x = min(max(f[0] - cw / 2, 0), W - cw); y = min(max(f[1] - ch / 2, 0), H - ch)
        return img.resize((W, h), Image.BICUBIC, box=(x, y, x + cw, y + ch))
    def bg(self, t):
        o = Image.new('RGB', (W, H), DARK); z = 1.6 + 0.12 * t / self.dur
        pa = ease(t / 0.3); pb = ease((t - 0.35) / 0.3)
        o.paste(self.half(self.a, self.fa, z), (int(-W * (1 - pa)), 0))
        if pb > 0: o.paste(self.half(self.b, self.fb, z), (int(W * (1 - pb)), H // 2))
        return o
    def frame(self, t):
        out = self.bg(t).convert('RGBA'); d = ImageDraw.Draw(out)
        d.rectangle([0, H // 2 - 5, W * ease((t - 0.3) / 0.3), H // 2 + 5], fill=WHITE + (255,))
        a = back((t - 0.2) / 0.22); b = back((t - 0.6) / 0.22)
        if a > 0: paste(out, self.la, SAFE[0] + self.la.width / 2, self.ya, scale=a)
        if b > 0: paste(out, self.lb, SAFE[0] + self.lb.width / 2, self.yb, scale=b)
        return out
    def events(self): return [(0.0, 'whoosh', 1), (0.2, 'buzz', 0.8), (0.35, 'whoosh', 1), (0.6, 'ding', 0.9)]

# ---------- большая цифра / акцент ----------
class BigNum(Scene):
    """value ('№4'), title, sub, img (фон, размыт), shake"""
    dur = 1.6
    def __init__(self, s, ctx):
        super().__init__(s, ctx)
        self.img = photo(s['img']).filter(ImageFilter.GaussianBlur(16)) if s.get('img') else None
        self.v = s['value']; self.title = s.get('title', ''); self.sub = s.get('sub', '')
        self.vs = fit_size(self.v, 330, 'Black', 900); self.ts = fit_size(self.title, 92, 'Black', 940) if self.title else 0
        tw = tlen(self.v, font(self.vs)); self.add_text((W / 2 - tw / 2, 430, W / 2 + tw / 2, 430 + self.vs), self.vs, GOLD, False, self.v)
        if self.title: tw = tlen(self.title, font(self.ts)); self.add_text((W / 2 - tw / 2, 820, W / 2 + tw / 2, 820 + self.ts * 1.1), self.ts, WHITE, False, self.title)
    def bg(self, t):
        if self.img is None: return Image.new('RGB', (W, H), NAVY)
        o = cam(self.img, 1.05 + 0.05 * t / self.dur)[0].convert('RGBA'); o.alpha_composite(Image.new('RGBA', (W, H), (8, 12, 20, 185))); return o.convert('RGB')
    def frame(self, t):
        out = self.bg(t).convert('RGBA'); a = back(t / 0.3)
        if a > 0: paste(out, text_layer(self.v, self.vs, GOLD), W / 2, 430 + self.vs * 0.55, scale=2.2 - 1.2 * min(1, a) if a < 1 else 1 + 0.03 * math.sin(t * 9))
        b = back((t - 0.25) / 0.25)
        if b > 0 and self.title: paste(out, text_layer(self.title, self.ts, WHITE), W / 2, 820 + self.ts * 0.6, scale=b)
        if self.s.get('shake', True) and 0.28 < t < 0.5:
            amp = 18 * (1 - (t - 0.28) / 0.22); dx, dy = _rngf(t).uniform(-amp, amp, 2)
            c = Image.new('RGBA', (W, H), DARK + (255,)); c.alpha_composite(out, (int(dx), int(dy))); out = c
        return out
    def events(self): return [(0.0, 'whoosh_long', 0.8), (0.28, 'boom', 1), (0.3, 'impact', 1)]

LIBRARY.update({'quiz': Quiz, 'lens': Lens, 'split': Split, 'bignum': BigNum})

# ================= v4: монтажные сцены по разбору топ-рилсов =================

# ---------- обратный отсчёт: быстрые склейки с ускорением + крупная цифра ----------
class Countdown(Scene):
    """imgs: [путь | {img, label, focus}], start_n (по умолч. len), d0/d1 — длительность первого/последнего кадра (ускорение),
    title — надпись сверху на всём отсчёте"""
    def __init__(self, s, ctx):
        super().__init__(s, ctx)
        self.items = [x if isinstance(x, dict) else {'img': x} for x in s['imgs']]
        for it in self.items:
            if not os.path.isabs(it['img']): it['img'] = os.path.join(ctx['root'], it['img'])
            it['im'] = photo(it['img'], s.get('exposure', 1.0), s.get('contrast', 1.0))
        n = len(self.items); d0, d1 = s.get('d0', 0.75), s.get('d1', 0.22)
        self.durs = [d0 + (d1 - d0) * (k / max(1, n - 1)) ** 0.8 for k in range(n)]
        self.dur = sum(self.durs); self.starts = [sum(self.durs[:k]) for k in range(n)]
        self.n0 = s.get('start_n', n); self.title = s.get('title', '')
        self.ts = fit_size(self.title, 66, 'Black', 940) if self.title else 0
        if self.title: tw = tlen(self.title, font(self.ts)); self.add_text((W / 2 - tw / 2, 260, W / 2 + tw / 2, 260 + self.ts * 1.2), self.ts, WHITE, True, self.title)
        self.add_text((W / 2 - 170, 560, W / 2 + 170, 860), 260, WHITE, False, '10')
    def _at(self, t):
        k = 0
        while k + 1 < len(self.starts) and t >= self.starts[k + 1]: k += 1
        return k, t - self.starts[k]
    def bg(self, t):
        k, lt = self._at(t); it = self.items[k]; d = self.durs[k]
        z = 1.12 - 0.08 * lt / d if k % 2 else 1.04 + 0.08 * lt / d
        f = it.get('focus', [W / 2, H / 2]); o = cam(it['im'], z, *f)[0]
        o = ImageEnhance.Color(o).enhance(0.55); o = ImageEnhance.Brightness(o).enhance(0.7).convert('RGBA')
        o.alpha_composite(_spot()); return o.convert('RGB')
    def frame(self, t):
        k, lt = self._at(t); out = self.bg(t).convert('RGBA')
        num = str(self.n0 - k); p = back(lt / 0.12)
        paste(out, text_layer(num, 300, WHITE), W / 2, 720, scale=1.35 - 0.35 * min(1, p))
        lab = self.items[k].get('label')
        if lab: paste(out, text_layer(lab, 58, GOLD, 'ExtraBold'), W / 2, 930, alpha=clamp(lt / 0.08))
        if self.title:
            f = font(self.ts); tw = tlen(self.title, f); d = ImageDraw.Draw(out)
            d.rounded_rectangle([W / 2 - tw / 2 - 30, 250, W / 2 + tw / 2 + 30, 260 + self.ts * 1.35], radius=24, fill=DARK + (220,))
            d.text((W / 2, 260 + self.ts * 0.65), self.title, font=f, fill=WHITE, anchor='mm')
        if lt < 0.05: out = Image.alpha_composite(out, Image.new('RGBA', (W, H), (255, 255, 255, int(110 * (1 - lt / 0.05)))))
        return out
    def events(self):
        e = []
        for k, st in enumerate(self.starts):
            e += [(st, 'tick', 1.6), (st, 'pop', 0.6 + 0.4 * k / len(self.starts))]
        return e

_SPOT = []
def _spot():
    if not _SPOT:
        sp = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sp).ellipse([W / 2 - 380, 480, W / 2 + 380, 1040], fill=(0, 0, 0, 105))
        _SPOT.append(sp.filter(ImageFilter.GaussianBlur(110)))
    return _SPOT[0]

# ---------- раскрытие: вспышка → медленный наезд на «после» + заголовок по строкам ----------
class Reveal(Scene):
    """img, lines (заголовок, по строкам), sub, focus, z0/z1"""
    dur = 3.5
    def __init__(self, s, ctx):
        super().__init__(s, ctx)
        self.img = photo(s['img'], s.get('exposure', 1.0), s.get('contrast', 1.0)); self.f = s.get('focus', [W / 2, H / 2])
        self.lines = s.get('lines', []); self.sub = s.get('sub', '')
        self.size = min([fit_size(l, s.get('size', 104), 'Black', 940) for l in self.lines] or [104])
        y = s.get('y', 300)
        self.ys = []
        for l in self.lines:
            tw = tlen(l, font(self.size)); self.add_text((W / 2 - tw / 2, y, W / 2 + tw / 2, y + self.size * 1.1), self.size, WHITE, False, l); self.ys.append(y); y += self.size * 1.15
        self.ysub = y + 16
        if self.sub:
            self.ss = fit_size(self.sub, 54, 'ExtraBold', 900); tw = tlen(self.sub, font(self.ss, 'ExtraBold'))
            self.add_text((W / 2 - tw / 2 - 30, self.ysub, W / 2 + tw / 2 + 30, self.ysub + self.ss * 1.5), self.ss, DARK, True, self.sub)
    def z(self, t): return self.s.get('z0', 1.18) + (self.s.get('z1', 1.0) - self.s.get('z0', 1.18)) * ease_out(t / self.dur)
    def bg(self, t):
        o = cam(self.img, self.z(t), *self.f)[0]
        g = Image.new('RGBA', (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(g)
        for k in range(36): gd.rectangle([0, k * 24, W, k * 24 + 24], fill=(0, 0, 0, int(140 * (1 - k / 36))))
        o = o.convert('RGBA'); o.alpha_composite(g); return o.convert('RGB')
    def frame(self, t):
        out = self.bg(t).convert('RGBA')
        for k, (l, y) in enumerate(zip(self.lines, self.ys)):
            a = ease_out((t - 0.35 - 0.18 * k) / 0.35)
            if a > 0: paste(out, text_layer(l, self.size, WHITE), W / 2, y + self.size * 0.6 + 40 * (1 - a), alpha=a)
        if self.sub:
            a = back((t - 0.9) / 0.25)
            if a > 0:
                f = font(self.ss, 'ExtraBold'); tw = tlen(self.sub, f)
                lay = Image.new('RGBA', (int(tw + 60), int(self.ss * 1.5)), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
                ld.rounded_rectangle([0, 0, lay.width - 1, lay.height - 1], radius=26, fill=GOLD + (255,)); ld.text((lay.width / 2, lay.height / 2), self.sub, font=f, fill=DARK, anchor='mm')
                paste(out, lay, W / 2, self.ysub + lay.height / 2, scale=a)
        if t < 0.35: out = Image.alpha_composite(out, Image.new('RGBA', (W, H), (255, 255, 255, int(255 * (1 - t / 0.35) ** 2))))
        return out
    def events(self): return [(0, 'boom', 1), (0.02, 'impact', 1), (0.1, 'shimmer', 1), (0.9, 'pop', 0.8)]

LIBRARY.update({'countdown': Countdown, 'reveal': Reveal})

# ================= v5: квиз «отличите материал от еды» с «человеческим» монтажом =================
class HookIntro(Scene):
    """img, word (крупно лаймом сверху), lines (вопрос снизу; строка с * — лаймом), seed"""
    dur = 2.4
    def __init__(self, s, ctx):
        super().__init__(s, ctx)
        self.img = photo(s['img'], s.get('exposure', 1.0), s.get('contrast', 1.0)); self.f = s.get('focus', [W / 2, H / 2])
        self.word = s.get('word', ''); self.ws = s.get('word_size', 120)
        self.lines = s.get('lines', []); self.ls = s.get('line_size', 62)
        f = ifont(self.ws, 'Black'); tw = tlen(self.word, f); self.add_text((W / 2 - tw / 2, 420, W / 2 + tw / 2, 420 + self.ws), self.ws, LIME, False, self.word)
        y = 1120
        for l in self.lines:
            tw = tlen(l.strip('*'), ifont(self.ls, 'Bold')); self.add_text((LOW_CX - tw / 2, y, LOW_CX + tw / 2, y + self.ls * 1.05), self.ls, WHITE, False, l.strip('*')); y += self.ls * 1.22
    def bg(self, t): return shake_cam(self.img, 1.0 + 0.05 * t / self.dur, *self.f, t, seed=self.s.get('seed', 3))[0]
    def frame(self, t):
        out = self.bg(t).convert('RGBA')
        g = Image.new('RGBA', (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(g)
        for k in range(30): gd.rectangle([0, H - (k + 1) * 30, W, H - k * 30], fill=(0, 0, 0, int(150 * (1 - k / 30))))
        out.alpha_composite(g)
        if self.word:
            p = (t - 0.12) / 0.35; l = blur_text(self.word, self.ws, LIME, 'Black', p)
            paste(out, l, W / 2 + 60 * (1 - ease_out(p)), 420 + self.ws * 0.5)
        y = 1120
        for k, line in enumerate(self.lines):
            p = (t - 0.45 - 0.15 * k) / 0.35; col = LIME if line.startswith('*') else WHITE
            paste(out, blur_text(line.strip('*'), self.ls, col, 'Bold', p), LOW_CX, y + self.ls * 0.55 + 18 * (1 - ease_out(p)))
            y += self.ls * 1.22
        return out
    def events(self): return [(0.12, 'whoosh', 0.7), (0.15, 'pop', 0.8), (0.45, 'pop', 0.6)]

class MatQuiz(Scene):
    """img, question (строки через |), answers [{text, at:[x,y]}], count (сек отсчёта), hold (сек показа ответа), focus, seed"""
    def __init__(self, s, ctx):
        super().__init__(s, ctx)
        self.img = photo(s['img'], s.get('exposure', 1.0), s.get('contrast', 1.0)); self.f = s.get('focus', [W / 2, H / 2])
        self.q = s['question'].split('|'); self.qs = s.get('q_size', 50); self.count = s.get('count', 5); self.hold = s.get('hold', 1.5)
        self.t_rev = 0.25 + self.count; self.dur = s.get('dur', self.t_rev + self.hold)
        self.ans = s.get('answers', []); self.as_ = s.get('a_size', 50)
        y = s.get('q_y', 1180)
        self.qy = []
        for l in self.q:
            tw = tlen(l, ifont(self.qs, 'SemiBold')); self.add_text((LOW_CX - tw / 2, y, LOW_CX + tw / 2, y + self.qs * 1.05), self.qs, WHITE, False, l); self.qy.append(y); y += self.qs * 1.22
        self.rc = s.get('ring_at', [860, 300])
    def bg(self, t): return shake_cam(self.img, 1.0 + 0.06 * t / self.dur, *self.f, t, amp=5, seed=self.s.get('seed', self.idx if hasattr(self, 'idx') else 1))[0]
    def frame(self, t):
        out = self.bg(t).convert('RGBA'); d = ImageDraw.Draw(out)
        # вопрос: blur-in, перед ответом — blur-out
        for k, (l, y) in enumerate(zip(self.q, self.qy)):
            p_in = (t - 0.1 - 0.12 * k) / 0.35; p_out = 1 - (t - self.t_rev + 0.25) / 0.3
            p = min(p_in, p_out)
            if p > 0: paste(out, blur_text(l, self.qs, WHITE, 'SemiBold', p), LOW_CX - 30 * (1 - ease_out(min(1, p_in))), y + self.qs * 0.55)
        # отсчёт: тонкое кольцо, которое «стекает» каждую секунду, и цифра
        if t < self.t_rev + 0.35:
            cx, cy = self.rc; r = 62; el = t - 0.25
            n = max(0, self.count - int(max(0, el))) if el < self.count else 0
            frac = 1 - (el - math.floor(el)) if 0 <= el < self.count else 0
            a_in = ease(t / 0.25); a_out = 1 - ease((t - self.t_rev) / 0.35)
            alpha = int(255 * min(a_in, a_out))
            if alpha > 4:
                lay = Image.new('RGBA', (2 * r + 40, 2 * r + 40), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
                ld.ellipse([20, 20, 2 * r + 20, 2 * r + 20], outline=(255, 255, 255, 70), width=4)
                if frac > 0: ld.arc([20, 20, 2 * r + 20, 2 * r + 20], -90, -90 + 360 * frac, fill=(120, 190, 255, 255), width=6)
                ft = ifont(64, 'Medium'); ld.text((r + 20, r + 22), str(n), font=ft, fill=(255, 255, 255, 255), anchor='mm')
                pop = 1 + 0.12 * (1 - ease(min(1, (el - math.floor(el)) / 0.15))) if el >= 0 else 1
                lay.putalpha(lay.split()[3].point(lambda v: int(v * alpha / 255)))
                paste(out, lay, cx, cy, scale=pop)
        # ответы: подписи над кучками
        for k, a in enumerate(self.ans):
            p = (t - self.t_rev - 0.08 * k) / 0.3
            if p > 0:
                x, y = a['at']; paste(out, blur_text(a['text'], self.as_, a.get('color', WHITE) if isinstance(a.get('color'), tuple) else WHITE, 'Bold', p), x, y - 12 * (1 - ease_out(p)))
        return out
    def texts(self):
        tx = list(self._texts)
        for a in self.ans:
            tw = tlen(a['text'], ifont(self.as_, 'Bold')); x, y = a['at']; tx.append(dict(box=[int(x - tw / 2), int(y - self.as_ * 0.6), int(x + tw / 2), int(y + self.as_ * 0.6)], size=self.as_, color=WHITE, panel=False, what=a['text']))
        return tx
    def settled(self): return self.t_rev + 0.6
    def events(self):
        e = [(0.1, 'pop', 0.5)] + [(0.25 + k, 'tick', 1.5) for k in range(self.count)]
        e += [(self.t_rev, 'ding', 0.9), (self.t_rev + 0.02, 'pop', 0.8)]
        return e

LIBRARY.update({'hook_intro': HookIntro, 'matquiz': MatQuiz})
