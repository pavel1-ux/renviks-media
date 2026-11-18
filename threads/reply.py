"""Публикует одобренные ответы из threads/replies/*.json.

Формат файла: [{"reply_to_id": "...", "permalink": "...", "text": "..."}]
Опубликованным проставляется "published_id". Между ответами пауза 60–120 сек.
"""
import json, os, glob, time, random, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.abspath(__file__))
API = 'https://graph.threads.net/v1.0'
TOKEN = os.environ['THREADS_TOKEN'].strip()


def post(path, **params):
    params['access_token'] = TOKEN
    req = urllib.request.Request(f'{API}/{path}', data=urllib.parse.urlencode(params).encode(), method='POST')
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {'error': e.read().decode()[:400]}


def main():
    first = True
    for f in sorted(glob.glob(os.path.join(ROOT, 'replies', '*.json'))):
        items = json.load(open(f, encoding='utf-8'))
        changed = False
        for it in items:
            if it.get('published_id') or it.get('error'):
                continue
            if not first:
                time.sleep(random.randint(60, 120))
            first = False
            c = post('me/threads', media_type='TEXT', text=it['text'], reply_to_id=it['reply_to_id'])
            if 'error' in c:
                it['error'] = c['error']; changed = True; print('Ошибка:', c['error']); continue
            time.sleep(5)
            r = post('me/threads_publish', creation_id=c['id'])
            if 'error' in r:
                it['error'] = r['error']
            else:
                it['published_id'] = r['id']
            changed = True
            print(it.get('permalink'), '→', it.get('published_id') or it.get('error'))
            json.dump(items, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        if changed:
            json.dump(items, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
