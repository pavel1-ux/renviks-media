"""Публикует в Телеграм-канал пост на сегодняшнюю дату (по Москве) из telegram/queue/ГГГГ-ММ-ДД.json.

Формат файла очереди:
  {"type": "text",  "text": "..."}                      — обычный пост (HTML-разметка: <b>, <i>, <a href>)
  {"type": "video", "media": "prorab.mp4", "text": "..."} — видео из telegram/media + подпись (до 1024 символов)
  {"type": "photo", "media": "file.jpg", "text": "..."}   — фото + подпись
  {"type": "poll",  "question": "...", "options": ["..", ".."], "text": "необязательный пост перед опросом"}

Секреты репозитория: TG_BOT_TOKEN (токен бота), TG_CHAT_ID (например @rrenviks).
"""
import json, os, sys, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_RAW = 'https://raw.githubusercontent.com/pavel1-ux/renviks-media/main/telegram/media/'
TOKEN = os.environ['TG_BOT_TOKEN'].strip()
CHAT = os.environ.get('TG_CHAT_ID', '@rrenviks').strip() or '@rrenviks'


def api(method, **params):
    data = urllib.parse.urlencode({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
                                   for k, v in params.items()}).encode()
    req = urllib.request.Request(f'https://api.telegram.org/bot{TOKEN}/{method}', data=data)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        res = json.load(e)
    if not res.get('ok'):
        raise SystemExit(f'Telegram error in {method}: {res}')
    return res


def main():
    msk = datetime.now(timezone(timedelta(hours=3)))
    day = (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else msk.strftime('%Y-%m-%d'))
    path = os.path.join(ROOT, 'queue', f'{day}.json')
    posted_path = os.path.join(ROOT, 'posted.txt')
    posted = set(open(posted_path, encoding='utf-8').read().split()) if os.path.exists(posted_path) else set()
    if not os.path.exists(path):
        print(f'На {day} поста нет — пропускаю.')
        return
    if day in posted and os.environ.get('FORCE') != '1':
        print(f'Пост на {day} уже опубликован.')
        return
    post = json.load(open(path, encoding='utf-8'))
    kind = post.get('type', 'text')
    common = dict(chat_id=CHAT, parse_mode='HTML')
    sent = None
    if kind == 'text':
        sent = api('sendMessage', text=post['text'], disable_web_page_preview='true', **common)
    elif kind == 'video':
        api('sendVideo', video=REPO_RAW + post['media'], caption=post.get('text', ''), supports_streaming='true', **common)
    elif kind == 'photo':
        api('sendPhoto', photo=REPO_RAW + post['media'], caption=post.get('text', ''), **common)
    elif kind == 'poll':
        if post.get('text'):
            api('sendMessage', text=post['text'], **common)
        api('sendPoll', chat_id=CHAT, question=post['question'], options=post['options'],
            is_anonymous='true', allows_multiple_answers='false')
    else:
        raise SystemExit(f'Неизвестный тип поста: {kind}')
    if post.get('pin') and sent:                       # закрепить сообщение в канале
        api('pinChatMessage', chat_id=CHAT, message_id=sent['result']['message_id'], disable_notification='true')
        print('Закреплено')
    with open(posted_path, 'a', encoding='utf-8') as f:
        f.write(day + '\n')
    print(f'Опубликовано: {day} ({kind})')


if __name__ == '__main__':
    main()
