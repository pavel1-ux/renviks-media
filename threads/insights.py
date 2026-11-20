"""Статистика постов @renviks.remont: просмотры, лайки, ответы, репосты по каждому посту за 14 дней.
Пишет threads/stats/ГГГГ-ММ-ДД.json и threads/stats/REPORT.md (что заходит, что нет). Секрет: THREADS_TOKEN."""
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
    msk = datetime.now(timezone(timedelta(hours=3))); since = int((msk - timedelta(days=14)).timestamp())
    posts, url = [], None
    r = get('me/threads', fields='id,text,timestamp,permalink,media_type,topic_tag', since=since, limit=100)
    if 'error' in r: raise SystemExit(r['error'])
    for p in r.get('data', []):
        m = get(f"{p['id']}/insights", metric='views,likes,replies,reposts,quotes,shares')
        vals = {x['name']: x['values'][0]['value'] for x in m.get('data', [])} if 'data' in m else {}
        posts.append(dict(p, **vals))
    acc = get('me/threads_insights', metric='views,followers_count,likes,replies', since=since, until=int(msk.timestamp()))
    os.makedirs(os.path.join(ROOT, 'stats'), exist_ok=True)
    json.dump(dict(date=msk.strftime('%Y-%m-%d %H:%M'), posts=posts, account=acc), open(os.path.join(ROOT, 'stats', msk.strftime('%Y-%m-%d') + '.json'), 'w'), ensure_ascii=False, indent=1)
    posts.sort(key=lambda p: (p.get('views', 0) + 30 * p.get('replies', 0)), reverse=True)
    def row(p):
        t = (p.get('text') or '').replace('\n', ' ')[:70]
        return f"| {p.get('views',0)} | {p.get('replies',0)} | {p.get('likes',0)} | {p.get('reposts',0)+p.get('shares',0)} | {p.get('media_type','')} | {t} |"
    med = sorted(p.get('views', 0) for p in posts)[len(posts) // 2] if posts else 0
    lines = [f"# Threads: статистика за 14 дней (на {msk:%d.%m %H:%M})", f"Постов: {len(posts)} · медиана просмотров: {med}", '',
             '| Просм. | Ответы | Лайки | Репост/шер | Формат | Начало поста |', '|---|---|---|---|---|---|']
    lines += [row(p) for p in posts]
    by = {}
    for p in posts: by.setdefault(p.get('media_type', '?'), []).append(p.get('views', 0))
    lines += ['', '## По форматам'] + [f"- {k}: {len(v)} постов, средн. {sum(v)//max(1,len(v))} просмотров" for k, v in by.items()]
    open(os.path.join(ROOT, 'stats', 'REPORT.md'), 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines[:14]))

if __name__ == '__main__': main()
