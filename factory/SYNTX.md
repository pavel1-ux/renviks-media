# Как Claude делает картинки в SYNTX сам

- Вход: встроенный браузер на Mac, syntx.ai, аккаунт @Pavelpppp (вход через Telegram-ссылку бота @syntxaibot; QR декодируется BarcodeDetector'ом на странице).
- Картинки: /ru/image/banana (Nano Banana 2, 9:16, 2K) — 3 токена за картинку. Одновременно не больше 3 генераций, иначе промпт молча пропадает.
- В промптах: "Photorealistic vertical photo ... shot on iPhone, realistic, no people, no text, no brand logos." Одна и та же кухня в описании → серия выглядит единой.
- Порядок картинок в DOM ≠ порядок промптов: сверять по содержимому.
- Забрать файлы: полноразмерный URL = превью без "_500" (.jpg или .png; файл появляется не сразу — проверять HEAD из браузера). Список "имя URL" в media/fetch/<серия>.txt → GitHub Action fetch-media скачивает в media/in/<серия>/.
- Монтаж: python3 factory/netda.py factory/netda-rozetki.json out.mp4 (stills — превью кадров).
