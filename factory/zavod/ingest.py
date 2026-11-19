"""Приёмка пачки фото/видео с объектов.
  python3 ingest.py <папка с файлами> <папка результата>
Делает: фото — разворот по EXIF, приведение к jpg, оценка резкости/яркости;
видео — планы по смене сцены, обложка и резкость каждого плана;
итог — index.json и обзорные листы sheet_NN.jpg (по 12 карточек) для отбора.
"""
import json, os, re, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageOps, ImageFont

PHOTO = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'}
VIDEO = {'.mp4', '.mov', '.m4v', '.avi', '.3gp', '.mkv'}
FONT = '/usr/share/fonts/truetype/google-fonts/ofl/montserrat/Montserrat[wght].ttf'

def sharpness(im):
    g = np.asarray(im.convert('L').resize((360, int(360 * im.height / im.width))), dtype=np.float32)
    lap = g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return float(lap.var())

def brightness(im): return float(np.asarray(im.convert('L').resize((64, 64)), dtype=np.float32).mean())

def load_photo(path):
    try:
        return ImageOps.exif_transpose(Image.open(path)).convert('RGB')
    except Exception:
        tmp = '/tmp/_ingest_conv.jpg'                       # HEIC и прочее — через ffmpeg
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', path, tmp], check=True)
        return Image.open(tmp).convert('RGB')

def probe(path):
    j = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                   'stream=width,height:stream_side_data=rotation:format=duration', '-of', 'json', path],
                                  capture_output=True, text=True).stdout)
    st = j['streams'][0]; w, h = st['width'], st['height']; rot = 0
    for sd in st.get('side_data_list', []) or []:
        if 'rotation' in sd: rot = abs(int(sd['rotation']))
    if rot in (90, 270): w, h = h, w
    return w, h, float(j['format']['duration'])

def shots(path, dur, thr=0.28, min_len=1.0):
    err = subprocess.run(['ffmpeg', '-v', 'info', '-i', path, '-vf', f"scale=320:-2,select='gt(scene,{thr})',showinfo", '-an', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    cuts = [float(m) for m in re.findall(r'pts_time:([0-9.]+)', err)]
    bounds = [0.0] + [c for c in cuts if c > 0.3] + [dur]; res = []
    for a, b in zip(bounds, bounds[1:]):
        if b - a >= min_len: res.append((round(a, 2), round(b, 2)))
        elif res: res[-1] = (res[-1][0], round(b, 2))
    return res or [(0.0, round(dur, 2))]

def grab(path, t):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.2f}', '-i', path, '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'mjpeg', '-'],
                         capture_output=True).stdout
    import io
    return Image.open(io.BytesIO(raw)).convert('RGB')

def main(src, out):
    os.makedirs(os.path.join(out, 'photos'), exist_ok=True); os.makedirs(os.path.join(out, 'thumbs'), exist_ok=True)
    files = sorted(os.path.join(r, f) for r, _, fs in os.walk(src) for f in fs if not f.startswith('.'))
    items = []; pn = vn = 0
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in PHOTO:
            pn += 1; pid = f'P{pn:03d}'; im = load_photo(f)
            if max(im.size) > 2752: im.thumbnail((2752, 2752), Image.LANCZOS)
            dst = os.path.join(out, 'photos', pid + '.jpg'); im.save(dst, quality=92)
            th = im.copy(); th.thumbnail((360, 360)); th.save(os.path.join(out, 'thumbs', pid + '.jpg'), quality=80)
            items.append(dict(id=pid, kind='photo', src=f, file=dst, w=im.width, h=im.height, orient='vert' if im.height >= im.width else 'horiz',
                              sharp=round(sharpness(im)), bright=round(brightness(im))))
        elif ext in VIDEO:
            vn += 1; vid = f'V{vn:02d}'; w, h, dur = probe(f)
            for k, (a, b) in enumerate(shots(f, dur), 1):
                im = grab(f, (a + b) / 2); sid = f'{vid}s{k}'
                th = im.copy(); th.thumbnail((360, 360)); th.save(os.path.join(out, 'thumbs', sid + '.jpg'), quality=80)
                items.append(dict(id=sid, kind='video', src=f, start=a, end=b, len=round(b - a, 1), w=w, h=h,
                                  orient='vert' if h >= w else 'horiz', sharp=round(sharpness(im)), bright=round(brightness(im))))
    # пометки качества
    sh = [i['sharp'] for i in items] or [1]; med = float(np.median(sh))
    for i in items:
        flags = []
        if i['sharp'] < 0.35 * med: flags.append('смазано')
        if i['bright'] < 45: flags.append('темно')
        if i['bright'] > 225: flags.append('пересвет')
        i['flags'] = flags
    json.dump(dict(source=src, count=len(items), items=items), open(os.path.join(out, 'index.json'), 'w'), ensure_ascii=False, indent=1)
    # обзорные листы 4x3
    fnt = ImageFont.truetype(FONT, 22); fnt.set_variation_by_name('Bold')
    for s in range(0, len(items), 12):
        sheet = Image.new('RGB', (4 * 300, 3 * 400), (20, 24, 32)); d = ImageDraw.Draw(sheet)
        for k, it in enumerate(items[s:s + 12]):
            x, y = (k % 4) * 300, (k // 4) * 400; th = Image.open(os.path.join(out, 'thumbs', it['id'] + '.jpg'))
            th.thumbnail((290, 340)); sheet.paste(th, (x + 5 + (290 - th.width) // 2, y + 5))
            lab = it['id'] + (f" {it['start']:.0f}-{it['end']:.0f}с" if it['kind'] == 'video' else '') + (' ! ' + ', '.join(it['flags']) if it['flags'] else '')
            d.text((x + 8, y + 352), lab, font=fnt, fill=(255, 210, 80) if it['flags'] else (235, 235, 235))
        sheet.save(os.path.join(out, f'sheet_{s // 12 + 1:02d}.jpg'), quality=82)
    print(f'{len(files)} файлов → {pn} фото, {vn} видео, {len(items)} карточек; листов: {(len(items) + 11) // 12}')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
