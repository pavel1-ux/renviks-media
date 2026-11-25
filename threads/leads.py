"""Ищет свежие посты в Threads по ключевым словам и сохраняет кандидатов для ответов в threads/leads/ГГГГ-ММ-ДД.json.

Секрет в GitHub: THREADS_SEARCH_TOKEN. Нужно разрешение threads_keyword_search.
"""
import json, os, sys, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
API = 'https://graph.threads.net/v1.0'
TOKEN = os.environ['THREADS_TOKEN'].strip()
QUERIES = [
    'ищу бригаду', 'посоветуйте бригаду', 'ремонт квартиры москва', 'ремонт новостройки',
    'получили ключи', 'приемка квартиры', 'ищу прораба', 'бригада ремонт', 'дизайнер интерьера москва',
    'ремонт под ключ', 'бригада пропала', 'начинаем ремонт',
    'ремонт квартиры', 'новостройка', 'бригада', 'ремонт',
]


def get(path, **params):
    params['access_token'] = TOKEN
    url = f'{API}/{path}?' + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {'error': e.read().decode()[:400]}


def main():
    verify_only = '--verify-only' in sys.argv
    msk = datetime.now(timezone(timedelta(hours=3)))
    day = msk.strftime('%Y-%m-%d')
    me = get('me', fields='id,username')
    own_username = me.get('username')
    if not own_username:
        raise SystemExit('Threads API не вернул имя подключённого профиля.')
    seen, out, errors = set(), [], []
    for q in QUERIES:
        r = get('keyword_search', q=q, search_type='RECENT',
                fields='id,text,username,timestamp,permalink,media_type')
        if 'error' in r:
            errors.append({'q': q, 'error': r['error']})
            continue
        posts = r.get('data', [])
        if verify_only:
            own_count = sum(post.get('username') == own_username for post in posts)
            anonymous_count = sum(not post.get('username') for post in posts)
            print(f'RECENT «{q}»: всего {len(posts)}, своих {own_count}, без имени {anonymous_count}')
        for p in posts:
            if p['id'] in seen or p.get('username') == own_username:
                continue
            seen.add(p['id'])
            p['query'] = q
            out.append(p)
    print(f'Найдено постов: {len(out)}; ошибок запросов: {len(errors)}')
    if verify_only:
        for query in ('ThreadsAPI', 'ремонт', 'ремонт квартиры'):
            for mode in ('RECENT', 'TOP'):
                result = get('keyword_search', q=query, search_type=mode, fields='id', limit=10)
                count = 'ошибка API' if 'error' in result else len(result.get('data', []))
                print(f'{mode} «{query}»: {count}')
        return int(bool(errors))
    os.makedirs(os.path.join(ROOT, 'leads'), exist_ok=True)
    path = os.path.join(ROOT, 'leads', f'{day}.json')
    json.dump({'date': day, 'me': me, 'count': len(out), 'posts': out, 'errors': errors},
              open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    sys.exit(main())
