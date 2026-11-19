"""Рилс-формат «НЕТ / ДА»: пары фото, наезд на ошибку, ✕/✓, подписи, размерная линия, sfx.
Запуск: python3 netda.py config.json out.mp4
"""
import json, math, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
FONT = '/usr/share/fonts/truetype/google-fonts/ofl/montserrat/Montserrat[wght].ttf'
NAVY = (12, 22, 38); GOLD = (214, 172, 44); WHITE = (248, 248, 244)
RED = (235, 52, 58); GREEN = (40, 190, 95); DARK = (10, 14, 22)
SAFE_L, SAFE_R = 60, 900          # справа кнопки Instagram
CX = (SAFE_L + SAFE_R) // 2

cfg = json.load(open(sys.argv[1])); OUT = sys.argv[2]
HOOK, SEG, END = cfg.get('hook_dur', 1.5), cfg.get('seg_dur', 1.5), cfg.get('end_dur', 2.4)
ITEMS = []
for p in cfg['pairs']:
    ITEMS.append(dict(p['net'], kind='net')); ITEMS.append(dict(p['da'], kind='da'))
TOTAL = HOOK + SEG * len(ITEMS) + END

_fc = {}
def font(size, wt='Black'):
    k = (size, wt)
    if k not in _fc:
        f = ImageFont.truetype(FONT, size); f.set_variation_by_name(wt); _fc[k] = f
    return _fc[k]

def clamp(t): return max(0.0, min(1.0, t))
def ease(t): t = clamp(t); return 1 - (1 - t) ** 3
def back(t):
    t = clamp(t); c1 = 2.2; c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2

# ---------- фото ----------
def load(path):
    im = Image.open(path).convert('RGB')
    s = W / im.width; im = im.resize((W, round(im.height * s)), Image.LANCZOS)
    if im.height < H:
        s = H / im.height; im = im.resize((round(im.width * s), H), Image.LANCZOS)
    x0 = (im.width - W) // 2; y0 = (im.height - H) // 2
    return im.crop((x0, y0, x0 + W, y0 + H))

PHOTOS = {it['img']: load(it['img']) for it in ITEMS}
HOOK_BG = load(cfg['pairs'][0]['net']['img']).filter(ImageFilter.GaussianBlur(14))

def zoomed(img, fx, fy, z):
    """увеличение z с фокусом (fx,fy), фокус смещается к центру кадра"""
    if z <= 1.001: return img.copy()
    cw, ch = W / z, H / z
    cx = min(max(fx, cw / 2), W - cw / 2); cy = min(max(fy, ch / 2), H - ch / 2)
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    return img.resize((W, H), Image.BICUBIC, box=box), box

def map_pt(x, y, box):
    if box is None: return x, y
    sx = W / (box[2] - box[0]); return (x - box[0]) * sx, (y - box[1]) * sx

# ---------- графика ----------
def pill_label(kind, text):
    badge = 'НЕТ' if kind == 'net' else 'ДА'
    col = RED if kind == 'net' else GREEN
    fb, ft = font(70, 'Black'), font(60, 'ExtraBold')
    d = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    lines = []; cur = ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=ft) <= 600: cur = t
        else: lines.append(cur); cur = w
    lines.append(cur)
    bw = d.textlength(badge, font=fb) + 56
    tw = max(d.textlength(l, font=ft) for l in lines)
    h = max(120, 44 + 70 * len(lines)); w = int(bw + tw + 60)
    img = Image.new('RGBA', (w, h + 12), (0, 0, 0, 0)); dr = ImageDraw.Draw(img)
    dr.rounded_rectangle([0, 8, w, h + 8], radius=30, fill=(0, 0, 0, 90))
    dr.rounded_rectangle([0, 0, w, h], radius=30, fill=DARK + (235,))
    dr.rounded_rectangle([12, 12, bw, h - 12], radius=22, fill=col)
    dr.text(((12 + bw) / 2, h / 2), badge, font=fb, fill=WHITE, anchor='mm')
    y = h / 2 - 35 * (len(lines) - 1)
    for l in lines:
        dr.text((bw + 30, y), l, font=ft, fill=WHITE, anchor='lm'); y += 70
    return img

def mark(kind, r=95):
    """круглый значок ✕ / ✓"""
    s = r * 2 + 20; img = Image.new('RGBA', (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    col = RED if kind == 'net' else GREEN; c = s / 2
    d.ellipse([c - r, c - r, c + r, c + r], fill=col + (255,), outline=WHITE, width=10)
    k = r * 0.42; lw = 22
    if kind == 'net':
        d.line([c - k, c - k, c + k, c + k], fill=WHITE, width=lw); d.line([c - k, c + k, c + k, c - k], fill=WHITE, width=lw)
    else:
        d.line([c - k, c + 2, c - k * 0.2, c + k * 0.8, c + k * 1.05, c - k * 0.7], fill=WHITE, width=lw, joint='curve')
    return img

def ring(draw, x, y, r, col, width, prog):
    if prog <= 0: return
    draw.arc([x - r, y - r, x + r, y + r], start=-90, end=-90 + 360 * prog, fill=col, width=width)

def paste(base, layer, cx, cy, scale=1.0, alpha=1.0, rot=0):
    if scale <= 0.01 or alpha <= 0.01: return
    l = layer if scale == 1 else layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))), Image.BICUBIC)
    if rot: l = l.rotate(rot, Image.BICUBIC, expand=True)
    if alpha < 1:
        a = l.split()[3].point(lambda v: int(v * alpha)); l = l.copy(); l.putalpha(a)
    base.alpha_composite(l, (int(cx - l.width / 2), int(cy - l.height / 2)))

def text_center(base, text, y, size, col, wt='Black', alpha=1.0, scale=1.0, x=CX):
    f = font(int(size * scale), wt)
    d = ImageDraw.Draw(Image.new('RGB', (1, 1))); tw = d.textlength(text, font=f)
    layer = Image.new('RGBA', (int(tw) + 40, int(size * scale * 1.4)), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((20, 0), text, font=f, fill=col + (int(255 * alpha),))
    base.alpha_composite(layer, (int(x - layer.width / 2), int(y)))

LABELS = [pill_label(it['kind'], it['text']) for it in ITEMS]
MARKS = {'net': mark('net'), 'da': mark('da')}
SMALL_MARKS = {'net': mark('net', 46), 'da': mark('da', 46)}

def dim_line(draw, a, b, label, prog, box):
    """размерная линия от a до b (координаты кадра без зума)"""
    if prog <= 0: return
    (x1, y1), (x2, y2) = map_pt(*a, box), map_pt(*b, box)
    xm, ym = x1 + (x2 - x1) * prog, y1 + (y2 - y1) * prog
    col = GOLD + (255,)
    draw.line([x1, y1, xm, ym], fill=col, width=8)
    ang = math.atan2(y2 - y1, x2 - x1); nx, ny = -math.sin(ang) * 26, math.cos(ang) * 26
    draw.line([x1 - nx, y1 - ny, x1 + nx, y1 + ny], fill=col, width=8)
    if prog >= 1:
        draw.line([x2 - nx, y2 - ny, x2 + nx, y2 + ny], fill=col, width=8)
        f = font(58, 'Black'); mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 62
        tw = draw.textlength(label, font=f)
        draw.rounded_rectangle([mx - tw / 2 - 22, my - 40, mx + tw / 2 + 22, my + 40], radius=20, fill=GOLD + (255,))
        draw.text((mx, my), label, font=f, fill=DARK, anchor='mm')

# ---------- кадры ----------
def frame_hook(t):
    out = HOOK_BG.copy().convert('RGBA')
    out.alpha_composite(Image.new('RGBA', (W, H), (8, 12, 20, 165)))
    a = back(t / 0.25); a2 = back((t - 0.1) / 0.25)
    for k, line in enumerate(cfg['hook_top']):
        aa = a if k == 0 else a2
        if aa > 0: text_center(out, line, 420 + k * 150, 132, WHITE, 'Black', scale=0.5 + 0.5 * aa, x=W // 2)
    b1 = back((t - 0.3) / 0.25); b2 = back((t - 0.55) / 0.25)
    if b1 > 0:
        paste(out, MARKS['net'], W // 2 - 200, 960, scale=b1 * 1.25)
        text_center(out, 'НЕТ', 1100, 110, RED, x=W // 2 - 200, alpha=clamp((t - 0.3) / 0.12))
    if b2 > 0:
        paste(out, MARKS['da'], W // 2 + 200, 960, scale=b2 * 1.25)
        text_center(out, 'ДА', 1100, 110, GREEN, x=W // 2 + 200, alpha=clamp((t - 0.55) / 0.12))
    if t > 0.8:
        text_center(out, cfg['hook_sub'], 1300, 58, GOLD, 'ExtraBold', alpha=clamp((t - 0.8) / 0.15), x=W // 2)
    return out

def frame_item(i, t):
    it = ITEMS[i]; img = PHOTOS[it['img']]; fx, fy = it['focus']
    if it['kind'] == 'net':
        z = 1.0 + 0.32 * ease((t - 0.15) / 0.35) + 0.03 * t     # резкий наезд на ошибку
    else:
        z = 1.08 - 0.06 * ease(t / 1.2)                          # плавный отъезд
    res = zoomed(img, fx, fy, z)
    if isinstance(res, tuple): base, box = res
    else: base, box = res, None
    out = base.convert('RGBA')
    if it['kind'] == 'net':  # лёгкое затемнение вокруг
        out.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, int(60 * ease((t - 0.2) / 0.3)))))
    d = ImageDraw.Draw(out)
    px, py = map_pt(fx, fy, box)
    col = RED if it['kind'] == 'net' else GREEN
    ring(d, px, py, it.get('ring', 150), col + (255,), 12, ease((t - 0.3) / 0.25))
    if 'dim' in it:
        dim_line(d, it['dim'][0], it['dim'][1], it['dim'][2], ease((t - 0.35) / 0.3), box)
    m = back((t - 0.42) / 0.22)
    if m > 0:
        mx, my = px + it.get('mark_dx', 120), py - it.get('mark_dy', 130)
        mx = min(mx, SAFE_R - 80)
        paste(out, MARKS[it['kind']], mx, my, scale=m * 0.95, rot=(8 if it['kind'] == 'net' else 0))
    # подпись сверху
    lab = LABELS[i]; s = back(t / 0.22)
    if s > 0:
        x = SAFE_L + lab.width / 2; y = 330
        out.alpha_composite(lab.resize((max(1, int(lab.width * s)), max(1, int(lab.height * s))), Image.BICUBIC) if s != 1 else lab,
                            (int(x - lab.width * s / 2), int(y - lab.height * s / 2)))
    # счётчик пар
    k = i // 2 + 1; n = len(ITEMS) // 2
    f = font(40, 'ExtraBold'); txt = f'{k}/{n}'
    d.rounded_rectangle([SAFE_L, 190, SAFE_L + 120, 250], radius=18, fill=(0, 0, 0, 150))
    d.text((SAFE_L + 60, 220), txt, font=f, fill=WHITE, anchor='mm')
    # вход: вспышка + сдвиг
    if t < 0.12:
        a = 1 - t / 0.12
        out.alpha_composite(Image.new('RGBA', (W, H), (255, 255, 255, int(150 * a))))
    # тряска на ✕
    if it['kind'] == 'net' and 0.42 < t < 0.6:
        amp = 14 * (1 - (t - 0.42) / 0.18); rng = np.random.default_rng(int(t * 1000))
        dx, dy = rng.uniform(-amp, amp, 2)
        c = Image.new('RGBA', (W, H), DARK + (255,)); c.alpha_composite(out, (int(dx), int(dy))); out = c
    return out

def frame_end(t):
    out = Image.new('RGBA', (W, H), NAVY + (255,)); d = ImageDraw.Draw(out)
    for k in range(-4, 14):   # бегущие диагонали
        x = k * 160 + (t * 120) % 160
        d.line([x, 0, x - 900, H], fill=(20, 34, 56, 255), width=40)
    a = back(t / 0.3)
    text_center(out, cfg['end_line1'], 560, 64, WHITE, 'ExtraBold', alpha=clamp(t / 0.2), scale=0.7 + 0.3 * a, x=W // 2)
    text_center(out, cfg['end_line2'], 650, 64, WHITE, 'ExtraBold', alpha=clamp(t / 0.2), scale=0.7 + 0.3 * a, x=W // 2)
    b = back((t - 0.35) / 0.3)
    if b > 0:
        text_center(out, 'РЕНВИКС', 860, 150, GOLD, 'Black', scale=0.5 + 0.5 * b, x=W // 2)
        text_center(out, 'ремонт квартир под ключ', 1040, 52, WHITE, 'SemiBold', alpha=clamp((t - 0.4) / 0.2), x=W // 2)
    c = back((t - 0.7) / 0.3)
    if c > 0:
        f = font(56, 'ExtraBold'); txt = cfg['end_contact']; tw = d.textlength(txt, font=f)
        d.rounded_rectangle([W / 2 - tw / 2 - 36, 1180, W / 2 + tw / 2 + 36, 1290], radius=40, fill=GOLD)
        d.text((W / 2, 1235), txt, font=f, fill=DARK, anchor='mm')
    if t > 1.1:
        text_center(out, cfg['end_save'], 1360, 46, WHITE, 'Medium', alpha=clamp((t - 1.1) / 0.2), x=W // 2)
    return out

def frame(t):
    if t < HOOK: return frame_hook(t).convert('RGB')
    t2 = t - HOOK; i = int(t2 // SEG)
    if i < len(ITEMS): return frame_item(i, t2 - i * SEG).convert('RGB')
    return frame_end(t2 - SEG * len(ITEMS)).convert('RGB')

# ---------- звук ----------
SR = 44100
def env(n, a, dcy): t = np.arange(n) / SR; return np.minimum(t / a, 1) * np.exp(-t / dcy)
def whoosh(dur=0.25):
    n = int(dur * SR); x = np.random.default_rng(5).standard_normal(n)
    x = np.convolve(x, np.ones(10) / 10, 'same'); return 0.45 * x * np.linspace(0, 1, n) ** 2
def impact():
    n = int(0.45 * SR); t = np.arange(n) / SR; f = 110 * np.exp(-t * 8) + 40
    return 0.85 * np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.14) + 0.3 * np.random.default_rng(2).standard_normal(n) * env(n, 0.001, 0.01)
def buzz():
    n = int(0.28 * SR); t = np.arange(n) / SR
    s = np.sign(np.sin(2 * np.pi * 140 * t)) * 0.5 + np.sin(2 * np.pi * 147 * t) * 0.5
    return 0.28 * s * env(n, 0.005, 0.2)
def ding():
    n = int(0.6 * SR); t = np.arange(n) / SR
    return 0.32 * (np.sin(2 * np.pi * 1318 * t) + 0.5 * np.sin(2 * np.pi * 1976 * t)) * env(n, 0.002, 0.18)
def pop():
    n = int(0.09 * SR); t = np.arange(n) / SR; f = 1000 * np.exp(-t * 30) + 300
    return 0.4 * np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.03)

def build_audio(path):
    buf = np.zeros(int((TOTAL + 0.5) * SR))
    def add(s, at):
        i = int(at * SR); buf[i:i + len(s)] += s[:max(0, len(buf) - i)]
    add(impact(), 0.0); add(pop(), 0.3); add(buzz(), 0.28); add(ding(), 0.58); add(pop(), 0.88)
    for i, it in enumerate(ITEMS):
        t0 = HOOK + i * SEG
        add(whoosh(), t0 - 0.2); add(pop(), t0 + 0.05)
        if it['kind'] == 'net': add(impact() * 0.7, t0 + 0.42); add(buzz(), t0 + 0.44)
        else: add(ding(), t0 + 0.44)
    te = HOOK + SEG * len(ITEMS)
    add(whoosh(0.3), te - 0.22); add(impact() * 0.8, te + 0.35); add(pop(), te + 0.72)
    buf = np.tanh(buf * 1.1)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((buf * 30000).astype(np.int16).tobytes())

if __name__ == '__main__':
    if len(sys.argv) > 3 and sys.argv[3] == 'stills':
        for k, tt in enumerate([0.9] + [HOOK + i * SEG + 1.0 for i in range(len(ITEMS))] + [TOTAL - 0.3]):
            frame(tt).save(f'/tmp/nd_{k:02d}.jpg', quality=80)
        sys.exit()
    build_audio('/tmp/nd_sfx.wav')
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
                          '-i', '-', '-i', '/tmp/nd_sfx.wav', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p',
                          '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', OUT], stdin=subprocess.PIPE)
    for fi in range(int(TOTAL * FPS)):
        p.stdin.write(frame(fi / FPS).tobytes())
    p.stdin.close(); p.wait(); print('ok', round(TOTAL, 1), 's')
