"""Consolida los resultados de PubMed, Consensus y Scholar Gateway en CSV/RIS deduplicados.
Uso: python3 build_corpus.py <dir_resultados_crudos> <dir_salida>"""
import json, glob, re, csv, sys, os, collections
raw, out = sys.argv[1], sys.argv[2]
norm = lambda t: re.sub(r'[^a-z0-9]', '', (t or '').lower())

SIGNALS = {'PSG': r'polysomnogra|\bpsg\b', 'EEG': r'electroencephalogra|\beeg\b', 'EOG': r'electrooculogra|\beog\b',
 'EMG': r'electromyogra|\bemg\b', 'ECG/HRV': r'electrocardiogra|\becg\b|\bekg\b|heart rate variab|\bhrv\b',
 'Airflow': r'airflow|nasal (pressure|flow)|respiratory flow', 'Resp. effort': r'(thoracic|abdominal|respiratory) (effort|movement|belt)|thoracoabdominal',
 'SpO2/Oximetry': r'oximetr|spo2|oxygen saturation|sao2', 'PPG': r'photoplethysmogra|\bppg\b', 'Snoring/Audio': r'snor|acoustic|breathing sound|audio',
 'Capnography': r'capnogra|etco2'}
def tags(text):
    t = text.lower()
    return '; '.join(k for k, p in SIGNALS.items() if re.search(p, t))

rows = {}
# ---------- PubMed ----------
arts = []
for f in glob.glob(f'{raw}/mcp-PubMed-get*') + glob.glob(f'{raw}/toolu_*') + glob.glob(f'{raw}/extra_pubmed*.json'):
    arts += json.load(open(f))['articles']
for a in arts:
    pmid = a['identifiers']['pmid']
    au = a.get('authors', [])
    pd_ = a.get('publication_date', {})
    doi = a['identifiers'].get('doi') or a.get('doi') or ''
    rows[norm(a['title'])] = dict(source='PubMed', title=a['title'].rstrip('.'),
        authors='; '.join(f"{x.get('last_name','')} {x.get('initials','')}".strip() for x in au),
        year=pd_.get('year', ''), journal=a.get('journal', {}).get('title', ''), doi=doi,
        doi_url=f'https://doi.org/{doi}' if doi else '', pmid=pmid, pmcid=a['identifiers'].get('pmc', ''),
        url=f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/', article_types='; '.join(a.get('article_types', [])),
        citations='', keywords='; '.join(a.get('keywords', [])), mesh='; '.join(a.get('mesh_terms', [])),
        abstract=a.get('abstract', ''))
n_pm = len(rows)
# ---------- Consensus ----------
n_cons = n_cons_new = 0
for f in glob.glob(f'{raw}/mcp-Consensus*'):
    txt = '\n'.join(x['text'] for x in json.load(open(f)))
    for m in re.finditer(r'\n\[(\d+)\] \[(.+?)\]\((https://consensus\.app/[^)]+)\) \((.+?)\)\n\s+id: (\S+)\n(.*?)(?=\n\[\d+\] \[|\Z)', txt, re.S):
        n_cons += 1
        _, title, url, meta, cid, abstract = m.groups()
        mm = re.match(r'(.*?), (\d{4}), (\d+) citations?(?:, (.*))?$', meta)
        authors, year, cit, journal = (mm.groups() if mm else (meta, '', '', ''))
        k = norm(title)
        if k in rows:
            rows[k]['source'] += ' + Consensus'; rows[k]['citations'] = cit
        else:
            n_cons_new += 1
            rows[k] = dict(source='Consensus', title=title, authors=authors, year=year, journal=journal or '', doi='', doi_url='',
                pmid='', pmcid='', url=url.split('?')[0], article_types='', citations=cit, keywords='', mesh='',
                abstract=re.sub(r'\s+', ' ', abstract.split('Upgrade to Consensus')[0]).strip())
# ---------- Scholar Gateway (Wiley) ----------
by_doi = {r['doi'].lower(): r for r in rows.values() if r['doi']}
sg = collections.OrderedDict()
for f in glob.glob(f'{raw}/mcp-Scholar*'):
    for r in json.load(open(f))['results']:
        sg.setdefault(r['doi'].lower(), r)
n_sg_new = 0
for doi, r in sg.items():
    if doi in by_doi:
        by_doi[doi]['source'] += ' + Scholar Gateway'; continue
    am = (r.get('metadata') or {}).get('additionalMetadata') or {}
    title = am.get('title') or ''
    k = norm(title) or doi
    if k in rows:
        rows[k]['source'] += ' + Scholar Gateway'; rows[k]['doi'] = rows[k]['doi'] or doi; rows[k]['doi_url'] = f'https://doi.org/{doi}'; continue
    n_sg_new += 1
    au = am.get('authors') or am.get('contributors') or ''
    if isinstance(au, list): au = '; '.join(x if isinstance(x, str) else str(x.get('name') or ' '.join(filter(None, [x.get('surname') or x.get('familyName'), x.get('givenNames') or x.get('givenName')]))) for x in au)
    date = str(am.get('publicationDate') or am.get('coverDate') or am.get('pubDate') or am.get('publishedDate') or am.get('year') or '')
    ym = re.search(r'(19|20)\d{2}', date)
    rows[k] = dict(source='Scholar Gateway', title=title, authors=au, year=ym.group(0) if ym else '',
        journal=am.get('journalTitle') or '', doi=doi, doi_url=f'https://doi.org/{doi}', pmid='', pmcid='',
        url=f'https://doi.org/{doi}', article_types=(r.get('metadata') or {}).get('article_type', ''), citations='', keywords='', mesh='',
        abstract=re.sub(r'\s+', ' ', am.get('abstract') or r.get('text', '')[:1500]).strip())

L = list(rows.values())
for r in L:
    blob = f"{r['title']} {r['abstract']} {r['keywords']} {r['mesh']}"
    r['signals'] = tags(blob)
    r['mentions_apnea'] = 'yes' if re.search(r'apn(o)?ea|sleep-disordered|sleep disordered|\bosa\b|hypopn', blob.lower()) else 'no'
    r['is_review'] = 'yes' if re.search(r'review|meta-analysis', (r['article_types'] + ' ' + r['title']).lower()) else 'no'
L.sort(key=lambda r: (-(int(r['year']) if r['year'].isdigit() else 0), r['title']))
cols = ['n', 'source', 'year', 'title', 'authors', 'journal', 'doi_url', 'pmid', 'pmcid', 'url', 'article_types', 'is_review',
        'signals', 'mentions_apnea', 'citations', 'keywords', 'mesh', 'abstract']
os.makedirs(out, exist_ok=True)
with open(f'{out}/osa_ml_corpus.csv', 'w', newline='', encoding='utf-8-sig') as fh:
    w = csv.DictWriter(fh, cols, extrasaction='ignore'); w.writeheader()
    for i, r in enumerate(L, 1): r['n'] = i; w.writerow(r)
with open(f'{out}/osa_ml_corpus.ris', 'w', encoding='utf-8') as fh:
    for r in L:
        fh.write('TY  - JOUR\n' + ''.join(f'AU  - {a.strip()}\n' for a in r['authors'].split(';') if a.strip()))
        for tag, key in [('TI', 'title'), ('JO', 'journal'), ('PY', 'year'), ('DO', 'doi'), ('AN', 'pmid'), ('UR', 'url'), ('AB', 'abstract')]:
            if r[key]: fh.write(f"{tag}  - {' '.join(str(r[key]).split())}\n")
        fh.write('ER  - \n\n')
json.dump(L, open(f'{out}/osa_ml_corpus.json', 'w'), ensure_ascii=False, indent=1)
# ---------- resumen ----------
print('PubMed únicos:', n_pm, '| Consensus:', n_cons, 'nuevos:', n_cons_new, '| Scholar GW artículos:', len(sg), 'nuevos:', n_sg_new, '| TOTAL:', len(L))
print('sin mención apnea:', sum(r['mentions_apnea'] == 'no' for r in L), '| revisiones:', sum(r['is_review'] == 'yes' for r in L), '| con DOI:', sum(bool(r['doi']) for r in L))
yc = collections.Counter(r['year'] for r in L); print('por año:', dict(sorted(yc.items(), reverse=True)))
sc = collections.Counter(s for r in L for s in r['signals'].split('; ') if s); print('señales:', sc.most_common())
print('fuentes:', collections.Counter(r['source'] for r in L).most_common())
