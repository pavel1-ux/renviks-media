# Как Claude делает картинки в SYNTX сам

- Вход: встроенный браузер на Mac, syntx.ai, аккаунт @Pavelpppp (вход через Telegram-ссылку бота @syntxaibot; QR декодируется BarcodeDetector'ом на странице).
- Картинки: /ru/image/banana (Nano Banana 2, 9:16, 2K) — 3 токена за картинку. Одновременно не больше 3 генераций, иначе промпт молча пропадает.
- В промптах: "Photorealistic vertical photo ... shot on iPhone, realistic, no people, no text, no brand logos." Одна и та же кухня в описании → серия выглядит единой.
- Порядок картинок в DOM ≠ порядок промптов: сверять по содержимому.
- Забрать файлы: полноразмерный URL = превью без "_500" (.jpg или .png; файл появляется не сразу — проверять HEAD из браузера). Список "имя URL" в media/fetch/<серия>.txt → GitHub Action fetch-media скачивает в media/in/<серия>/.
- Монтаж: python3 factory/netda.py factory/netda-rozetki.json out.mp4 (stills — превью кадров).
- Пакетная генерация: в странице определить window.__gen(prompt) (React-setter textarea + клик по кнопке отправки справа от поля) и очередь ≤3 одновременно; сопоставление картинка→промпт по ближайшему предыдущему тексту промпта в DOM (window.__pmap).
- Бренды в кадре владелец разрешил (так реалистичнее).

## Цены в токенах SYNTX (проверено 19.11.2026, тариф Pro до 17.12.2026)
- Nano Banana 2 (2K): 3 · Nano Banana (первая): 1,5 · FLUX.1: 0,3 · FLUX.1.1 Pro / Kontext Pro: 1,5 · Pro Ultra: 2,5 · Seedream 5.5: 4,8
- ElevenLabs v4: ~0,9 за 100 знаков (озвучка 28 с ≈ 3,6)
- Экономия: Flux для простых кадров (в промпте «European Schuko type F sockets», иначе рисует американские розетки), Nano Banana 2 только для «геройских» кадров; одна серия картинок → несколько рилсов; голос только на лучших.
