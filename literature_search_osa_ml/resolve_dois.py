"""Resuelve por título, en Crossref, el DOI de los registros que no lo traen.
Uso: python3 resolve_dois.py <corpus.json> <cache_salida.json>"""
import json, re, sys, time, urllib.parse, urllib.request, difflib
from concurrent.futures import ThreadPoolExecutor
norm = lambda t: re.sub(r'[^a-z0-9]', '', re.sub(r'<[^>]+>', '', t or '').lower())
corpus, cache_path = sys.argv[1:3]
try: cache = json.load(open(cache_path))
except FileNotFoundError: cache = {}
todo = [r for r in json.load(open(corpus)) if not r.get('doi') and norm(r['title']) not in cache]

def lookup(r):
    q = urllib.parse.urlencode({'query.bibliographic': r['title'], 'rows': 3, 'select': 'DOI,title,container-title,issued,type'})
    for attempt in range(3):
        try:
            items = json.load(urllib.request.urlopen('https://api.crossref.org/works?' + q, timeout=60))['message']['items']; break
        except Exception:
            if attempt == 2: return norm(r['title']), None
            time.sleep(3 * (attempt + 1))
    k = norm(r['title'])
    for it in items:
        cand = norm((it.get('title') or [''])[0])
        if cand and (cand == k or difflib.SequenceMatcher(None, cand, k).ratio() > 0.95):
            yr = ((it.get('issued') or {}).get('date-parts') or [[None]])[0][0]
            if r.get('year') and yr and abs(int(r['year']) - int(yr)) > 1: continue
            return k, dict(doi=it['DOI'].lower(), journal=(it.get('container-title') or [''])[0], type=it.get('type', ''))
    return k, {}

with ThreadPoolExecutor(4) as ex:
    for k, v in ex.map(lookup, todo):
        if v is not None: cache[k] = v
json.dump(cache, open(cache_path, 'w'), indent=1)
print('consultados:', len(todo), '| con DOI en caché:', sum(bool(v) for v in cache.values()), 'de', len(cache))
