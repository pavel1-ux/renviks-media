"""Публикует в Threads (@renviks.remont) следующий пост на сегодня (по Москве) из threads/queue/ГГГГ-ММ-ДД-N.json.

До 5 постов в день: N = 1..5. Каждый запуск по расписанию публикует ОДИН следующий неопубликованный пост дня.
Вторник и воскресенье — выходные (в расписании их нет).

Формат файла:
  {"text": "до 500 символов",
   "topic": "Ремонт",                       # тег сообщества (необязательно, по умолчанию «Ремонт»)
   "images": ["threads/media/x.jpg", ...],  # необязательно: 1 фото = пост с фото, 2–10 = карусель
   "poll": ["вариант A", "вариант B", ...],  # необязательно: опрос, 2–4 варианта (только для текстового поста)
   "video": "media/out/x.mp4",              # необязательно: пост-видео (рилс), до 5 мин
   "chain": ["продолжение 1", ...]}         # необязательно: серия — ответы на свой пост (мини-тред)
Картинки берутся из публичного репозитория по raw-ссылке.
Секреты: THREADS_TOKEN, THREADS_USER_ID.
"""
import json, os, sys, glob, time, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
API = 'https://graph.threads.net/v1.0'
TOKEN = os.environ['THREADS_TOKEN'].strip()
USER = os.environ.get('THREADS_USER_ID', 'me').strip() or 'me'
RAW = 'https://raw.githubusercontent.com/' + os.environ.get('GITHUB_REPOSITORY', 'pavel1-ux/renviks-media') + '/main/'
DEFAULT_TOPIC = 'Ремонт'


def call(method, url, **params):
    params['access_token'] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url + '?' + data.decode()) if method == 'GET' else urllib.request.Request(url, data=data, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f'Threads API error {e.code}: {e.read().decode()[:500]}')


def wait_ready(cid, tries=20):
    for _ in range(tries):
        st = call('GET', f'{API}/{cid}', fields='status,error_message')
        if st.get('status') == 'FINISHED': return
        if st.get('status') in ('ERROR', 'EXPIRED'): raise SystemExit(f'Контейнер {cid}: {st}')
        time.sleep(4)
    raise SystemExit(f'Контейнер {cid} не обработался')


def url_of(p): return p if p.startswith('http') else RAW + p


def make(**kw):
    """создать контейнер; если API не принял тег сообщества или опрос — повторить без них"""
    try:
        return call('POST', f'{API}/{USER}/threads', **kw)
    except SystemExit as e:
        if 'topic_tag' in kw or 'poll_attachment' in kw:
            print(f'Повтор без тега/опроса: {e}')
            kw.pop('topic_tag', None); kw.pop('poll_attachment', None)
            return call('POST', f'{API}/{USER}/threads', **kw)
        raise


def publish(post):
    text = post.get('text', '')
    if len(text) > 500: raise SystemExit(f'Пост длиннее 500 символов ({len(text)})')
    extra = {}
    topic = post.get('topic', DEFAULT_TOPIC)
    if topic: extra['topic_tag'] = topic
    imgs = post.get('images') or []
    if post.get('video'):
        c = make(media_type='VIDEO', video_url=url_of(post['video']), text=text, **extra)
        wait_ready(c['id'], tries=60)
    elif len(imgs) == 1:
        c = make(media_type='IMAGE', image_url=url_of(imgs[0]), text=text, **extra)
        wait_ready(c['id'])
    elif len(imgs) > 1:
        kids = []
        for p in imgs[:10]:
            k = call('POST', f'{API}/{USER}/threads', media_type='IMAGE', image_url=url_of(p), is_carousel_item='true')
            kids.append(k['id'])
        for k in kids: wait_ready(k)
        c = make(media_type='CAROUSEL', children=','.join(kids), text=text, **extra)
        wait_ready(c['id'])
    else:
        if post.get('poll'):
            opts = post['poll'][:4]
            extra['poll_attachment'] = json.dumps({f'option_{k}': v for k, v in zip('abcd', opts)}, ensure_ascii=False)
        c = make(media_type='TEXT', text=text, **extra)
        time.sleep(5)
    r = call('POST', f'{API}/{USER}/threads_publish', creation_id=c['id'])
    pid = r.get('id'); prev = pid
    for part in post.get('chain') or []:                 # мини-тред: каждое продолжение — ответ на предыдущее
        time.sleep(8)
        k = call('POST', f'{API}/{USER}/threads', media_type='TEXT', text=part[:500], reply_to_id=prev)
        time.sleep(5); prev = call('POST', f'{API}/{USER}/threads_publish', creation_id=k['id']).get('id')
    return pid


def refresh_token_info():
    try:
        r = call('GET', 'https://graph.threads.net/refresh_access_token', grant_type='th_refresh_token')
        print(f"Токен продлён, действует ещё ~{int(r.get('expires_in', 0)) // 86400} дн.")
    except SystemExit as e:
        print(f'Не удалось продлить токен: {e}')


def main():
    msk = datetime.now(timezone(timedelta(hours=3)))
    day = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else msk.strftime('%Y-%m-%d')
    posted_path = os.path.join(ROOT, 'posted.txt')
    posted = set(open(posted_path, encoding='utf-8').read().split()) if os.path.exists(posted_path) else set()
    files = sorted(glob.glob(os.path.join(ROOT, 'queue', f'{day}*.json')))
    todo = [f for f in files if os.path.basename(f)[:-5] not in posted or os.environ.get('FORCE') == '1']
    if not todo:
        print(f'На {day} неопубликованных постов нет.')
    else:
        f = todo[0]; key = os.path.basename(f)[:-5]
        pid = publish(json.load(open(f, encoding='utf-8')))
        with open(posted_path, 'a', encoding='utf-8') as fh: fh.write(key + '\n')
        print(f'Опубликовано: {key} → {pid}; осталось на сегодня: {len(todo) - 1}')
    refresh_token_info()


if __name__ == '__main__':
    main()
