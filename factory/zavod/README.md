# Контент-завод РЕНВИКС — движок сцен

Рилс = `factory/reels/<id>.json` со списком сцен. Сцены (factory/zavod/scenes.py):
- `hook` — крупный заголовок (+ значки НЕТ/ДА), подзаголовок
- `photo` — фото + камера (punch/drift/push), кольцо, ✕/✓ (`kind` net/da), плашка `text`, размерная линия `dim`, счётчик
- `stage` — фото только с движением камеры (формат «Этапы»)
- `checklist` — заголовок + пункты с галочками
- `before_after` — шторка ДО/ПОСЛЕ
- `end_brand` — финал с контактом; `end_logo` — чёрная плашка с логотипом
Переходы: `"enter": "cut" | "flash" | "zoomblur"`.

Автопроверка (`zavod.py check`): безопасные зоны Instagram (шапка, кнопки справа внизу, подпись), наложения текста, кегль ≥ 40 px, контраст.

    python3 factory/zavod/zavod.py check  factory/reels/<id>.json
    python3 factory/zavod/zavod.py render factory/reels/<id>.json <папка>   # reel.mp4 + scenes.json + обложки сцен
