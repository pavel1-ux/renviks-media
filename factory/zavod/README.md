# Контент-завод РЕНВИКС — движок сцен

Рилс = `factory/reels/<id>.json` со списком сцен. Сцены (factory/zavod/scenes.py):
- `hook` — крупный заголовок (+ значки НЕТ/ДА), подзаголовок
- `photo` — фото + камера (punch/drift/push), кольцо, ✕/✓ (`kind` net/da), плашка `text`, размерная линия `dim`, счётчик
- `stage` — фото только с движением камеры (формат «Этапы»)
- `checklist` — заголовок + пункты с галочками
- `before_after` — шторка ДО/ПОСЛЕ
- `clip` — живое видео: `src`, `start`, `dur`, `speed` (2 = ускорение), `mode` cover|fit (горизонтальное на размытом фоне), `focus_x`; плюс всё от `photo` (kind, text, ring, dim)
- у `photo`/`stage`: `exposure`, `contrast` — подтянуть тёмные кадры с объекта
- `end_brand` — финал с контактом; `end_logo` — чёрная плашка с логотипом
Переходы: `"enter": "cut" | "flash" | "zoomblur"`.

Автопроверка (`zavod.py check`): безопасные зоны Instagram (шапка, кнопки справа внизу, подпись), наложения текста, кегль ≥ 40 px, контраст.

    python3 factory/zavod/zavod.py check  factory/reels/<id>.json
    python3 factory/zavod/zavod.py render factory/reels/<id>.json <папка>   # reel.mp4 + scenes.json + обложки сцен

## Студия на телефоне
Страница-артефакт «Студия РЕНВИКС»: slug 068bd6bd-e16b-4142-b59b-8d8506a43ae9 (https://claude.ai/artifact/1otKQRe5VhWa9iSGQzFrRv).
Файлы: index.html (factory/studio/index.html) + manifest.json + reels/<id>/v<n>/{reel.mp4, sceneNN.jpg}. Публикация publish_files в режиме patch (добавлять новые версии, старые остаются).
Правки владельца лежат в db артефакта: коллекция `edits` {reel, v, t, scene, label, text, status:new|done, reply}; одобрение — коллекция `reels` {approved_v}.
Цикл правки: db_query edits status=new → поправить factory/reels/<id>.json → render в v<n+1> → добавить версию в manifest (note: что изменено) → publish_files → db_write edits/<id> status=done + reply.

## Пачка фото/видео владельца
    python3 factory/zavod/ingest.py <папка> <результат>
Фото: разворот по EXIF, jpg, резкость/яркость. Видео: планы по смене сцены (start–end), обложки.
Итог: index.json + обзорные листы sheet_NN.jpg (P001…, V01s1…, пометки «смазано / темно / пересвет»).
По листам выбираю кадры → reel.json со сценами `photo`/`clip`. Реальные кадры — в приоритете (бесплатно и живее).
