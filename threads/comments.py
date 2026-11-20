"""Собирает новые ответы людей под нашими постами за 3 дня → threads/comments/inbox.json.
Ответить нужно в первый час: Claude готовит черновики ответов, после одобрения они уходят через reply.py.
Секрет: THREADS_TOKEN (нужно разрешение threads_read_replies)."""
import json, os, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
API = 'https://graph.threads.net/v1.0'
TOKEN = os.environ['THREADS_TOKEN'].strip()

def get(path, **params):
    params['access_token'] = TOKEN
    try:
        with urllib.request.urlopen(f'{API}/{path}?' + urllib.parse.urlencode(params), timeout=60) as r: return json.load(r)
    except urllib.error.HTTPError as e: return {'error': e.read().decode()[:300]}

def main():
    msk = datetime.now(timezone(timedelta(hours=3)))
    me = get('me', fields='id,username'); since = int((msk - timedelta(days=3)).timestamp())
    path = os.path.join(ROOT, 'comments', 'inbox.json'); os.makedirs(os.path.dirname(path), exist_ok=True)
    inbox = json.load(open(path)) if os.path.exists(path) else []
    known = {c['id'] for c in inbox}
    mine = get('me/threads', fields='id,text,permalink,timestamp', since=since, limit=50).get('data', [])
    new = 0
    for p in mine:
        conv = get(f"{p['id']}/conversation", fields='id,text,username,timestamp,permalink,replied_to,is_reply_owned_by_me', reverse='false')
        for c in conv.get('data', []):
            if c['id'] in known or c.get('username') == me.get('username'): continue
            inbox.append(dict(id=c['id'], post_id=p['id'], post_text=(p.get('text') or '')[:200], username=c.get('username'),
                              text=c.get('text'), timestamp=c.get('timestamp'), permalink=c.get('permalink'), status='new'))
            new += 1
    json.dump(inbox, open(path, 'w'), ensure_ascii=False, indent=1)
    print(f'Новых ответов под нашими постами: {new}')

if __name__ == '__main__': main()
