"""Общие функции движка РЕНВИКС: шрифты, фото, камера, плашки, звук, безопасные зоны."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
FONT = '/usr/share/fonts/truetype/google-fonts/ofl/montserrat/Montserrat[wght].ttf'

# цвета бренда
NAVY = (12, 22, 38); GOLD = (214, 172, 44); WHITE = (248, 248, 244)
RED = (235, 52, 58); GREEN = (40, 190, 95); DARK = (10, 14, 22); BLACK = (0, 0, 0)

# безопасная зона Instagram Reels для текста: сверху шапка, справа кнопки, снизу подпись
SAFE = (60, 200, 900, 1500)
LOW_Y = 1050           # ниже этой линии справа кнопки Instagram: текст до x=900, центр нижних блоков x=LOW_CX
LOW_CX = 480
def safe_ok(box):
    x0, y0, x1, y1 = box
    if y0 < SAFE[1] - 12 or y1 > SAFE[3] + 2: return False
    if y1 <= LOW_Y: return x0 >= 36 and x1 <= W - 36
    return x0 >= SAFE[0] - 2 and x1 <= SAFE[2] + 2
MIN_TEXT = 40          # минимальный кегль, px
MIN_CONTRAST = 4.5     # WCAG для текста без подложки

_fc = {}
def font(size, wt='Black'):
    k = (int(size), wt)
    if k not in _fc:
        f = ImageFont.truetype(FONT, int(size)); f.set_variation_by_name(wt); _fc[k] = f
    return _fc[k]

def clamp(t): return max(0.0, min(1.0, t))
def ease(t): t = clamp(t); return t * t * (3 - 2 * t)
def ease_out(t): t = clamp(t); return 1 - (1 - t) ** 3
def back(t):
    t = clamp(t); c1 = 2.2; c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2

_ph = {}
def photo(path, exposure=1.0, contrast=1.0):
    """фото под 1080x1920 (cover), с кэшем; exposure/contrast — подтянуть тёмные кадры с объекта"""
    key = (path, exposure, contrast)
    if key not in _ph:
        from PIL import ImageEnhance, ImageOps
        im = ImageOps.exif_transpose(Image.open(path)).convert('RGB')
        if exposure != 1.0: im = ImageEnhance.Brightness(im).enhance(exposure)
        if contrast != 1.0: im = ImageEnhance.Contrast(im).enhance(contrast)
        s = max(W / im.width, H / im.height)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        x0 = (im.width - W) // 2; y0 = (im.height - H) // 2
        _ph[key] = im.crop((x0, y0, x0 + W, y0 + H))
    return _ph[key]

def cam(img, z, fx=W / 2, fy=H / 2):
    """камера: увеличение z с фокусом (fx,fy). Возвращает (кадр, box) — box нужен для пересчёта точек."""
    if z <= 1.0005: return img.copy(), (0, 0, W, H)
    cw, ch = W / z, H / z
    x = min(max(fx - cw / 2, 0), W - cw); y = min(max(fy - ch / 2, 0), H - ch)
    box = (x, y, x + cw, y + ch)
    return img.resize((W, H), Image.BICUBIC, box=box), box

def map_pt(x, y, box):
    s = W / (box[2] - box[0]); return (x - box[0]) * s, (y - box[1]) * s

def zoom_blur(img, z, strength, n=7):
    if strength < 0.004: return cam(img, z)[0]
    acc = None
    for k in range(n):
        a = np.asarray(cam(img, z * (1 + strength * k / (n - 1)))[0], dtype=np.float32)
        acc = a if acc is None else acc + a
    return Image.fromarray((acc / n).clip(0, 255).astype(np.uint8))

def wrap(text, f, maxw):
    d = ImageDraw.Draw(Image.new('RGB', (1, 1))); lines, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=f) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w
    lines.append(cur); return lines

def tlen(text, f): return ImageDraw.Draw(Image.new('RGB', (1, 1))).textlength(text, font=f)

def fit_size(text, size, wt, maxw):
    while size > MIN_TEXT and tlen(text, font(size, wt)) > maxw: size -= 2
    return size

def paste(base, layer, cx, cy, scale=1.0, alpha=1.0, rot=0):
    if scale <= 0.01 or alpha <= 0.01: return
    l = layer if scale == 1 else layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))), Image.BICUBIC)
    if rot: l = l.rotate(rot, Image.BICUBIC, expand=True)
    if alpha < 1:
        l = l.copy(); l.putalpha(l.split()[3].point(lambda v: int(v * alpha)))
    base.alpha_composite(l, (int(cx - l.width / 2), int(cy - l.height / 2)))

def text_layer(text, size, col, wt='Black', shadow=True):
    f = font(size, wt); tw = int(tlen(text, f)) + 40; th = int(size * 1.35)
    l = Image.new('RGBA', (tw, th), (0, 0, 0, 0)); d = ImageDraw.Draw(l)
    if shadow:
        sh = Image.new('RGBA', (tw, th), (0, 0, 0, 0)); ImageDraw.Draw(sh).text((20, 6), text, font=f, fill=(0, 0, 0, 170))
        l.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    d.text((20, 0), text, font=f, fill=col + (255,)); return l

def pill(badge, badge_col, text, maxw=600, size=60):
    """плашка: цветной бейдж + текст на тёмной подложке"""
    fb, ft = font(size + 10, 'Black'), font(size, 'ExtraBold')
    lines = wrap(text, ft, maxw)
    bw = (tlen(badge, fb) + 56) if badge else 0
    tw = max(tlen(l, ft) for l in lines); lh = int(size * 1.17)
    h = max(int(size * 2), 44 + lh * len(lines)); w = int(bw + tw + 60)
    img = Image.new('RGBA', (w, h + 12), (0, 0, 0, 0)); dr = ImageDraw.Draw(img)
    dr.rounded_rectangle([0, 8, w, h + 8], radius=30, fill=(0, 0, 0, 90))
    dr.rounded_rectangle([0, 0, w, h], radius=30, fill=DARK + (235,))
    if badge:
        dr.rounded_rectangle([12, 12, bw, h - 12], radius=22, fill=badge_col)
        dr.text(((12 + bw) / 2, h / 2), badge, font=fb, fill=WHITE, anchor='mm')
    y = h / 2 - lh / 2 * (len(lines) - 1)
    for l in lines:
        dr.text((bw + 30, y), l, font=ft, fill=WHITE, anchor='lm'); y += lh
    return img

def mark(kind, r=95):
    s = r * 2 + 20; img = Image.new('RGBA', (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    col = RED if kind == 'net' else GREEN; c = s / 2
    d.ellipse([c - r, c - r, c + r, c + r], fill=col + (255,), outline=WHITE, width=max(4, r // 9))
    k = r * 0.42; lw = max(8, r // 4)
    if kind == 'net':
        d.line([c - k, c - k, c + k, c + k], fill=WHITE, width=lw); d.line([c - k, c + k, c + k, c - k], fill=WHITE, width=lw)
    else:
        d.line([c - k, c + 2, c - k * 0.2, c + k * 0.8, c + k * 1.05, c - k * 0.7], fill=WHITE, width=lw, joint='curve')
    return img

def luminance(rgb):
    def ch(c):
        c = c / 255; return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb; return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)

def contrast(a, b):
    la, lb = luminance(a), luminance(b); hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)

# ---------- звук: синтез эффектов (без музыки) ----------
SR = 44100
def _env(n, a, d): t = np.arange(n) / SR; return np.minimum(t / a, 1) * np.exp(-t / d)
def _rng(s): return np.random.default_rng(s)
def sfx(name):
    if name == 'whoosh':
        n = int(0.3 * SR); x = np.convolve(_rng(5).standard_normal(n), np.ones(12) / 12, 'same')
        return 0.45 * x * np.linspace(0, 1, n) ** 2
    if name == 'whoosh_long':
        n = int(0.55 * SR); x = np.convolve(_rng(7).standard_normal(n), np.ones(18) / 18, 'same')
        return 0.55 * x * np.sin(np.linspace(0, np.pi, n)) ** 2
    if name == 'impact':
        n = int(0.45 * SR); t = np.arange(n) / SR; f = 110 * np.exp(-t * 8) + 40
        return 0.85 * np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, .002, .14) + 0.3 * _rng(2).standard_normal(n) * _env(n, .001, .01)
    if name == 'boom':
        n = int(1.2 * SR); t = np.arange(n) / SR; f = 70 * np.exp(-t * 4) + 35
        return 0.9 * np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, .003, .35)
    if name == 'buzz':
        n = int(0.28 * SR); t = np.arange(n) / SR
        return 0.28 * (np.sign(np.sin(2 * np.pi * 140 * t)) * .5 + np.sin(2 * np.pi * 147 * t) * .5) * _env(n, .005, .2)
    if name == 'ding':
        n = int(0.6 * SR); t = np.arange(n) / SR
        return 0.32 * (np.sin(2 * np.pi * 1318 * t) + .5 * np.sin(2 * np.pi * 1976 * t)) * _env(n, .002, .18)
    if name == 'pop':
        n = int(0.09 * SR); t = np.arange(n) / SR; f = 1000 * np.exp(-t * 30) + 300
        return 0.4 * np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, .002, .03)
    if name == 'tick':
        n = int(0.05 * SR); t = np.arange(n) / SR; return 0.25 * np.sin(2 * np.pi * 2400 * t) * _env(n, .001, .01)
    if name == 'shimmer':
        n = int(1.6 * SR); t = np.arange(n) / SR
        return 0.18 * sum(np.sin(2 * np.pi * f * t) * w for f, w in [(880, .5), (1320, .35), (1760, .25), (2640, .12)]) * _env(n, .02, .6)
    if name == 'room':
        n = int(12 * SR); return 0.6 * np.convolve(_rng(3).standard_normal(n), np.ones(400) / 400, 'same')
    raise KeyError(name)

_lg = {}
def logo_layer(path, width):
    """логотип с мягко растворёнными краями (фон логотипа сливается с фоном кадра)"""
    k = (path, width)
    if k not in _lg:
        im = Image.open(path).convert('RGB'); im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        w, h = im.size; f = 0.14
        xs = np.minimum(np.arange(w) / (w * f), (w - 1 - np.arange(w)) / (w * f)).clip(0, 1)
        ys = np.minimum(np.arange(h) / (h * f), (h - 1 - np.arange(h)) / (h * f)).clip(0, 1)
        m = (np.outer(ys, xs) ** 1.5 * 255).astype(np.uint8)
        im = im.convert('RGBA'); im.putalpha(Image.fromarray(m)); _lg[k] = im
    return _lg[k]

def logo_bg(path):
    a = np.asarray(Image.open(path).convert('RGB'), dtype=np.float32); return tuple(int(v) for v in a[:40, :40].reshape(-1, 3).mean(0))
