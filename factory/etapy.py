"""Рилс-формат «ЭТАПЫ»: одна комната, 3 стадии (бетон → инженерка → готово), наезды камеры,
переходы zoom-blur, финальная плашка с логотипом. Как у lamarchinterior.
Запуск: python3 etapy.py shell.jpg eng.jpg final.jpg out.mp4
"""
import math, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

W, H, FPS = 1080, 1920, 30
FONT = '/usr/share/fonts/truetype/google-fonts/ofl/montserrat/Montserrat[wght].ttf'
SHELL, ENG, FINAL, OUT = sys.argv[1:5]

def load(p):
    im = Image.open(p).convert('RGB'); s = W / im.width
    im = im.resize((W, round(im.height * s)), Image.LANCZOS)
    if im.height < H: im = im.resize((round(im.width * H / im.height), H), Image.LANCZOS)
    x0 = (im.width - W) // 2; y0 = (im.height - H) // 2
    return im.crop((x0, y0, x0 + W, y0 + H))

IM = [load(SHELL), load(ENG), load(FINAL)]
# тайминг: (начало, конец) каждой стадии; переходы перекрываются
T1, TR1, T2, TR2, T3, TL, TOTAL = 1.45, 0.4, 1.5, 0.4, 4.9, 1.3, 10.0

def ease(t): t = max(0, min(1, t)); return t * t * (3 - 2 * t)
def ease_out(t): t = max(0, min(1, t)); return 1 - (1 - t) ** 3

def zoom(img, z, cx=0.5, cy=0.5):
    if z <= 1.0005: return img
    cw, ch = W / z, H / z
    x = cx * W - cw / 2; y = cy * H - ch / 2
    x = min(max(x, 0), W - cw); y = min(max(y, 0), H - ch)
    return img.resize((W, H), Image.BICUBIC, box=(x, y, x + cw, y + ch))

def zoom_blur(img, z, strength, n=7):
    """радиальное размытие: среднее нескольких увеличений"""
    if strength < 0.004: return zoom(img, z)
    acc = None
    for k in range(n):
        a = np.asarray(zoom(img, z * (1 + strength * k / (n - 1))), dtype=np.float32)
        acc = a if acc is None else acc + a
    return Image.fromarray((acc / n).clip(0, 255).astype(np.uint8))

_fc = {}
def font(size, wt):
    k = (size, wt)
    if k not in _fc:
        f = ImageFont.truetype(FONT, size); f.set_variation_by_name(wt); _fc[k] = f
    return _fc[k]

def logo_card(a):
    out = Image.new('RGB', (W, H), (0, 0, 0)); d = ImageDraw.Draw(out)
    c = tuple(int(235 * a) for _ in range(3)); g = (int(214 * a), int(172 * a), int(44 * a))
    cx, cy = W // 2, 860
    # тонкий значок-домик
    d.line([cx - 95, cy + 70, cx - 95, cy - 20, cx, cy - 105, cx + 95, cy - 20, cx + 95, cy + 70], fill=c, width=5, joint='curve')
    d.line([cx - 25, cy + 70, cx - 25, cy + 5, cx + 25, cy + 5, cx + 25, cy + 70], fill=g, width=5)
    d.line([cx + 140, cy - 150, cx + 40, cy - 60], fill=c, width=3)
    # название с разрядкой
    f = font(78, 'SemiBold'); txt = 'Р Е Н В И К С'
    tw = d.textlength(txt, font=f); d.text((cx - tw / 2, cy + 120), txt, font=f, fill=c)
    d.line([cx - 330, cy + 165, cx - tw / 2 - 30, cy + 165], fill=c, width=2)
    d.line([cx + tw / 2 + 30, cy + 165, cx + 330, cy + 165], fill=c, width=2)
    f2 = font(36, 'Medium'); t2 = 'ремонт квартир под ключ · Москва'
    d.text((cx - d.textlength(t2, font=f2) / 2, cy + 240), t2, font=f2, fill=g)
    f3 = font(38, 'SemiBold'); t3 = '@renviks_moscow'
    d.text((cx - d.textlength(t3, font=f3) / 2, cy + 320), t3, font=f3, fill=c)
    return out

def frame(t):
    s1e = T1; s2s = T1 + TR1; s2e = s2s + T2; s3s = s2e + TR2; s3e = s3s + T3
    if t < s1e:                                   # бетон: медленный наезд
        return zoom(IM[0], 1.0 + 0.05 * t / s1e)
    if t < s2s:                                   # переход 1: влёт с размытием
        p = (t - s1e) / TR1
        if p < 0.5: return zoom_blur(IM[0], 1.05 + 0.5 * ease(p * 2), 0.22 * ease(p * 2))
        return zoom_blur(IM[1], 1.25 - 0.2 * ease_out((p - 0.5) * 2), 0.22 * (1 - ease_out((p - 0.5) * 2)))
    if t < s2e:                                   # инженерка
        p = (t - s2s) / T2; return zoom(IM[1], 1.05 - 0.04 * ease_out(p) + 0.03 * p)
    if t < s3s:                                   # переход 2
        p = (t - s2e) / TR2
        if p < 0.5: return zoom_blur(IM[1], 1.04 + 0.5 * ease(p * 2), 0.22 * ease(p * 2))
        im = zoom_blur(IM[2], 1.22 - 0.2 * ease_out((p - 0.5) * 2), 0.22 * (1 - ease_out((p - 0.5) * 2)))
        return ImageEnhance.Brightness(im).enhance(1 + 0.35 * (1 - (p - 0.5) * 2))
    if t < s3e:                                   # готово: длинный плавный наезд
        p = (t - s3s) / T3; return zoom(IM[2], 1.02 + 0.10 * ease(p), 0.5, 0.55)
    p = (t - s3e) / TL                            # логотип
    if p < 0.3:
        return Image.blend(zoom(IM[2], 1.12, 0.5, 0.55), logo_card(0), ease(p / 0.3))
    return logo_card(ease((p - 0.3) / 0.4))

# ---------- звук: только эффекты ----------
SR = 44100
def env(n, a, dcy): t = np.arange(n) / SR; return np.minimum(t / a, 1) * np.exp(-t / dcy)
def whoosh(dur):
    n = int(dur * SR); x = np.random.default_rng(7).standard_normal(n)
    x = np.convolve(x, np.ones(18) / 18, 'same'); e = np.sin(np.linspace(0, np.pi, n)) ** 2
    return 0.55 * x * e
def boom():
    n = int(1.2 * SR); t = np.arange(n) / SR; f = 70 * np.exp(-t * 4) + 35
    return 0.9 * np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.003, 0.35)
def shimmer():
    n = int(1.6 * SR); t = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * fr * t) * w for fr, w in [(880, .5), (1320, .35), (1760, .25), (2640, .12)])
    return 0.18 * s * env(n, 0.02, 0.6)
def room_tone(dur):
    n = int(dur * SR); x = np.random.default_rng(3).standard_normal(n)
    x = np.convolve(x, np.ones(400) / 400, 'same'); return 0.6 * x

def build_audio(path):
    buf = np.zeros(int((TOTAL + 0.5) * SR))
    def add(s, at):
        i = int(at * SR); buf[i:i + len(s)] += s[:max(0, len(buf) - i)]
    add(room_tone(TOTAL), 0)
    t1 = T1; t2 = T1 + TR1 + T2
    add(whoosh(0.55), t1 - 0.3); add(boom() * 0.8, t1 + 0.2)
    add(whoosh(0.55), t2 - 0.3); add(boom(), t2 + 0.2); add(shimmer() * 0.7, t2 + 0.25)
    add(shimmer(), TOTAL - TL + 0.35)
    buf = np.tanh(buf * 1.1)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((buf * 30000).astype(np.int16).tobytes())

if __name__ == '__main__':
    if len(sys.argv) > 5:
        for k, tt in enumerate([0.7, 1.55, 1.75, 2.6, 3.45, 3.65, 5.0, 8.0, 8.9, 9.8]):
            frame(tt).save(f'/tmp/et_{k:02d}.jpg', quality=80)
        sys.exit()
    build_audio('/tmp/et_sfx.wav')
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
                          '-i', '-', '-i', '/tmp/et_sfx.wav', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p',
                          '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', OUT], stdin=subprocess.PIPE)
    for fi in range(int(TOTAL * FPS)):
        p.stdin.write(frame(fi / FPS).tobytes())
    p.stdin.close(); p.wait(); print('ok', TOTAL)
