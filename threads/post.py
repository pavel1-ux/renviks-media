"""Публикует в Threads (@renviks.remont) пост на сегодняшнюю дату (по Москве) из threads/queue/ГГГГ-ММ-ДД.json.

Формат: {"text": "до 500 символов"}. Два поста в день: ГГГГ-ММ-ДД-1.json (утро) и ГГГГ-ММ-ДД-2.json (вечер); за один запуск публикуется один пост.
Секреты репозитория: THREADS_TOKEN (долгосрочный токен), THREADS_USER_ID.
Токен живёт 60 дней; скрипт при каждом запуске пробует его продлить и пишет в лог, сколько дней осталось.
"""
import json, os, sys, glob, time, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
API = 'https://graph.threads.net/v1.0'
TOKEN = os.environ['THREADS_TOKEN'].strip()
USER = os.environ.get('THREADS_USER_ID', 'me').strip() or 'me'


def call(method, url, **params):
    params['access_token'] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    if method == 'GET':
        req = urllib.request.Request(url + '?' + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f'Threads API error {e.code}: {e.read().decode()[:500]}')


def publish(text):
    if len(text) > 500:
        raise SystemExit(f'Пост длиннее 500 символов ({len(text)})')
    c = call('POST', f'{API}/{USER}/threads', media_type='TEXT', text=text)
    time.sleep(5)  # Meta рекомендует подождать, пока контейнер обработается
    r = call('POST', f'{API}/{USER}/threads_publish', creation_id=c['id'])
    return r.get('id')


def refresh_token_info():
    try:
        r = call('GET', 'https://graph.threads.net/refresh_access_token', grant_type='th_refresh_token')
        days = int(r.get('expires_in', 0)) // 86400
        print(f'Токен продлён, действует ещё ~{days} дн.')
    except SystemExit as e:
        print(f'Не удалось продлить токен: {e}')


def main():
    msk = datetime.now(timezone(timedelta(hours=3)))
    day = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else msk.strftime('%Y-%m-%d')
    posted_path = os.path.join(ROOT, 'posted.txt')
    posted = set(open(posted_path, encoding='utf-8').read().split()) if os.path.exists(posted_path) else set()
    files = sorted(glob.glob(os.path.join(ROOT, 'queue', f'{day}*.json')))
    if not files:
        print(f'На {day} постов нет.')
    for f in files:
        key = os.path.basename(f)[:-5]
        if key in posted and os.environ.get('FORCE') != '1':
            print(f'{key}: уже опубликован'); continue
        post = json.load(open(f, encoding='utf-8'))
        pid = publish(post['text'])
        with open(posted_path, 'a', encoding='utf-8') as fh:
            fh.write(key + '\n')
        print(f'Опубликовано: {key} → {pid}')
        break  # один пост за запуск: утром -1, вечером -2
    refresh_token_info()


if __name__ == '__main__':
    main()
