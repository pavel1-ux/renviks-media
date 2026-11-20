"""Тайминги слов для голоса: python align.py <папка>  → <файл>.words.json рядом с каждым mp3/wav без него.
Если рядом лежит <файл>.txt с точным текстом — слова берутся из текста (без ошибок распознавания),
а тайминги — из Whisper (выравнивание по порядку)."""
import json, os, re, sys, difflib

def norm(w): return re.sub(r'[^\wё]', '', w.lower().replace('ё', 'е'))

def align_text(words, text):
    """подставить точные слова сценария на тайминги распознанных"""
    ref = text.split(); a = [norm(w['w']) for w in words]; b = [norm(w) for w in ref]
    out = []; sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal':
            for k in range(i2 - i1): out.append(dict(words[i1 + k], w=ref[j1 + k]))
        elif j2 > j1:
            s = words[i1]['start'] if i1 < len(words) else (out[-1]['end'] if out else 0)
            e = words[i2 - 1]['end'] if i2 > i1 else (words[i1]['start'] if i1 < len(words) else s + 0.3 * (j2 - j1))
            step = max(0.05, (e - s) / (j2 - j1))
            for k in range(j2 - j1): out.append(dict(w=ref[j1 + k], start=round(s + k * step, 3), end=round(s + (k + 1) * step, 3)))
    return out

def main(folder):
    from faster_whisper import WhisperModel
    model = None
    for f in sorted(os.listdir(folder)):
        if not f.endswith(('.mp3', '.wav')): continue
        base = os.path.join(folder, os.path.splitext(f)[0]); dst = base + '.words.json'
        if os.path.exists(dst): continue
        model = model or WhisperModel('small', device='cpu', compute_type='int8')
        segs, _ = model.transcribe(os.path.join(folder, f), language='ru', word_timestamps=True, vad_filter=False)
        words = [dict(w=w.word.strip(), start=round(w.start, 3), end=round(w.end, 3)) for s in segs for w in s.words]
        if os.path.exists(base + '.txt'): words = align_text(words, open(base + '.txt').read())
        json.dump(dict(file=f, words=words), open(dst, 'w'), ensure_ascii=False, indent=0)
        print(f, len(words), 'слов')

if __name__ == '__main__': main(sys.argv[1])
