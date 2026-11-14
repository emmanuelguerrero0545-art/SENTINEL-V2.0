"""Etapa 2: amplía el corpus (Europe PMC + Consensus/IEEE), añade enlaces de texto completo,
puntúa la relevancia con reglas transparentes y genera la lista depurada.
Uso: python3 curate.py <corpus_etapa1.json> <dir_crudos_epmc> <consensus_ieee.txt> <dir_salida> [doi_cache.json]"""
import json, re, csv, sys, os, collections, time, urllib.parse, urllib.request
base, epmc_dir, cons_file, out = sys.argv[1:5]
norm = lambda t: re.sub(r'[^a-z0-9]', '', re.sub(r'<[^>]+>', '', t or '').lower())
clean = lambda t: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', t or '')).strip()

rows = {}
for r in json.load(open(base)):
    for k in ('n', 'signals', 'mentions_apnea', 'is_review'): r.pop(k, None)
    rows[norm(r['title'])] = r

def epmc_row(x):
    pmid, pmcid, doi = x.get('pmid', ''), x.get('pmcid', ''), x.get('doi', '')
    j = (x.get('journalInfo') or {}).get('journal', {}).get('title') or (x.get('bookOrReportDetails') or {}).get('publisher', '')
    urls = (x.get('fullTextUrlList') or {}).get('fullTextUrl', [])
    free_pdf = next((u['url'] for u in urls if u.get('availabilityCode') in ('F', 'OA') and u.get('documentStyle') == 'pdf'), '')
    return dict(pmid=pmid, pmcid=pmcid, doi=doi, title=clean(x.get('title', '')).rstrip('.'), authors=(x.get('authorString') or '').rstrip('.').replace(', ', '; '),
        year=x.get('pubYear', ''), journal=j or ('Preprint' if x['source'] == 'PPR' else ''), abstract=clean(x.get('abstractText', '')),
        article_types='; '.join((x.get('pubTypeList') or {}).get('pubType', [])), keywords='; '.join((x.get('keywordList') or {}).get('keyword', [])),
        open_access=x.get('isOpenAccess', ''), cited_by=x.get('citedByCount', 0), free_pdf=free_pdf, epmc_source=x['source'], epmc_id=x['id'])

def link(r, e):
    """Completa un registro con identificadores y enlaces de Europe PMC."""
    for k in ('pmcid', 'doi', 'pmid'):
        if e.get(k) and not r.get(k): r[k] = e[k]
    r['open_access'] = e['open_access']; r['cited_by_epmc'] = e['cited_by']
    if e['free_pdf']: r['free_pdf'] = e['free_pdf']

# --- acceso abierto de los PMID de la etapa 1 ---
by_pmid = {r['pmid']: r for r in rows.values() if r.get('pmid')}
for x in json.load(open(f'{epmc_dir}/epmc_pmids.json')):
    if x.get('pmid') in by_pmid: link(by_pmid[x['pmid']], epmc_row(x))
# --- búsqueda enfocada en Europe PMC ---
n_epmc = n_epmc_new = 0
for x in json.load(open(f'{epmc_dir}/epmc_search.json')):
    if x['source'] == 'PAT': continue
    n_epmc += 1; e = epmc_row(x); k = norm(e['title'])
    r = by_pmid.get(e['pmid']) if e['pmid'] else None
    r = r or rows.get(k)
    if r:
        if 'Europe PMC' not in r['source']: r['source'] += ' + Europe PMC'
        link(r, e)
    else:
        n_epmc_new += 1
        url = f"https://pubmed.ncbi.nlm.nih.gov/{e['pmid']}/" if e['pmid'] else f"https://europepmc.org/article/{e['epmc_source']}/{e['epmc_id']}"
        rows[k] = dict(source='Europe PMC' + (' (preprint)' if e['epmc_source'] == 'PPR' else ''), title=e['title'], authors=e['authors'], year=e['year'],
            journal=e['journal'], doi=e['doi'], pmid=e['pmid'], pmcid=e['pmcid'], url=url, article_types=e['article_types'], citations='',
            keywords=e['keywords'], mesh='', abstract=e['abstract'], open_access=e['open_access'], cited_by_epmc=e['cited_by'], free_pdf=e['free_pdf'])
# --- Consensus restringido a IEEE ---
n_ci = n_ci_new = 0
txt = '\n'.join(x['text'] for x in json.load(open(cons_file)))
for m in re.finditer(r'\n\[(\d+)\] \[(.+?)\]\((https://consensus\.app/[^)]+)\) \((.+?)\)\n\s+id: (\S+)\n(.*?)(?=\n\[\d+\] \[|\Z)', txt, re.S):
    n_ci += 1; _, title, url, meta, cid, abstract = m.groups()
    mm = re.match(r'(.*?), (\d{4}), (\d+) citations?(?:, (.*))?$', meta)
    authors, year, cit, journal = (mm.groups() if mm else (meta, '', '', ''))
    k = norm(title)
    if k in rows:
        if 'IEEE' not in rows[k]['source']: rows[k]['source'] += ' + Consensus (IEEE)'
        rows[k]['citations'] = rows[k].get('citations') or cit
    else:
        n_ci_new += 1
        rows[k] = dict(source='Consensus (IEEE)', title=title, authors=authors, year=year, journal=journal or 'IEEE', doi='', pmid='', pmcid='',
            url=url.split('?')[0], article_types='', citations=cit, keywords='', mesh='', abstract=clean(abstract.split('Upgrade to Consensus')[0]))

# --- DOI resueltos por título en Crossref (resolve_dois.py) ---
if len(sys.argv) > 5:
    for k, v in json.load(open(sys.argv[5])).items():
        r = rows.get(k)
        if r and v and not r.get('doi'):
            r['doi'] = v['doi']
            if v.get('journal') and (not r.get('journal') or r['journal'] in ('IEEE', 'Unknown Journal')): r['journal'] = v['journal']

# ---------------- puntuación de relevancia ----------------
P = dict(
 apnea=r'apn(o)?ea|sleep[- ]disordered breathing|\bosas?\b|hypopn(o)?ea|\bsahs\b',
 ai=r'machine[- ]learning|deep[- ]learning|artificial intelligence|neural network|\bcnn\b|\blstm\b|\brnn\b|transformer|support vector|\bsvm\b|random forest|xgboost|gradient boost|classifier|\bk-?nn\b|ensemble|autoencoder|attention|foundation model|large language model',
 task=r'detect|classif|screen|diagnos|severity|apn(o)?ea[- ]hypopn(o)?ea index|\bahi\b|predict|scoring|estimat|recogni',
 metric=r'sensitivity|specificity|accuracy|\bauc\b|auroc|area under|f1|kappa|precision|recall',
 imaging=r'cephalomet|\bcbct\b|cone[- ]beam|\bmri\b|magnetic resonance|computed tomograph|facial (photo|image)|3d (face|scan)|radiograph|endoscop',
 treatment=r'\bcpap\b|adheren|mandibular advancement|surgery outcome|uvulopalat|hypoglossal|postoperative|pharmacolog',
 staging=r'sleep stag',
 notprimary=r'^\d{3,4} |protocol\b|erratum|correction to|comment on|editorial|letter to|retract',
 animal=r'\b(mice|mouse|rats?|murine|zebrafish)\b')
SIGNALS = {'PSG': r'polysomnogra|\bpsg\b', 'EEG': r'electroencephalogra|\beeg\b', 'EOG': r'electrooculogra|\beog\b',
 'EMG': r'electromyogra|\bemg\b', 'ECG/HRV': r'electrocardiogra|\becg\b|\bekg\b|heart rate variab|\bhrv\b',
 'Airflow': r'airflow|nasal (pressure|flow)|respiratory flow|thermistor', 'Resp. effort': r'(thoracic|abdominal|respiratory|chest) (effort|movement|belt)|thoracoabdominal|inductance plethysmogra',
 'SpO2/Oximetry': r'oximetr|spo2|spo 2|oxygen saturation|sao2', 'PPG': r'photoplethysmogra|\bppg\b', 'Snoring/Audio': r'snor|acoustic|breathing sound|audio|tracheal sound',
 'Capnography': r'capnogra|etco2', 'Wearable/Radar/Other': r'wearable|smartwatch|radar|ballistocardiogra|accelerom|bed sensor|peripheral arterial ton'}
has = lambda p, s: bool(re.search(P[p] if p in P else p, s))
L = list(rows.values())
for r in L:
    t, a = r['title'].lower(), (r.get('abstract') or '').lower()
    ta = t + ' ' + a + ' ' + (r.get('keywords') or '').lower()
    sig = [k for k, p in SIGNALS.items() if re.search(p, ta)]
    core_sig = [s for s in sig if s != 'Wearable/Radar/Other']
    types = (r.get('article_types') or '').lower()
    review = bool(re.search(r'review|meta-analysis', types + ' ' + t))
    s = (3 if has('apnea', t) else 1 if has('apnea', a) else -6)
    s += (3 if has('ai', t) else 2 if has('ai', a) else -4)
    s += (2 if sig else -2) + (1 if any(re.search(SIGNALS[k], t) for k in sig) else 0)
    s += (2 if has('task', t) else 1 if has('task', a) else 0)
    s += (2 if has('metric', a) else 0)
    s -= 3 * has('imaging', t) + 2 * has('treatment', t) + 4 * has('notprimary', t) + 3 * has('animal', t) + 2 * has('staging', t) + (2 if len(a) < 200 else 0)
    cit = max(int(r.get('citations') or 0), int(r.get('cited_by_epmc') or 0))
    yr = int(r['year']) if str(r.get('year', '')).isdigit() else 0
    r.update(signals='; '.join(sig), is_review='yes' if review else 'no', relevance_score=s, cited_by=cit,
             cites_per_year=round(cit / max(1, 2027 - yr), 1) if yr else 0)
    doi, pmcid = r.get('doi', ''), r.get('pmcid', '')
    r['doi_url'] = f'https://doi.org/{doi}' if doi else ''
    r['pdf_url'] = (f'https://europepmc.org/articles/{pmcid}?pdf=render' if pmcid else r.get('free_pdf', ''))
    r['pmc_url'] = f'https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/' if pmcid else ''
    r['access'] = 'PDF libre' if r['pdf_url'] else ('suscripción / revisar DOI' if doi or r.get('pmid') else 'sin DOI (enlace Consensus)')
    r['is_ieee'] = 'yes' if re.search(r'ieee|engineering in medicine and biology society|\bembc\b', (r.get('journal') or '').lower() + r['source'].lower()) or doi.startswith('10.1109') else 'no'

MAXS = 13   # apnea en título 3 + IA en título 3 + señal 2 (+1 en título) + tarea diagnóstica en título 2 + métricas 2
def tier(r):
    """A = núcleo: máxima pertinencia temática y además reciente, citado o síntesis de evidencia."""
    sr = bool(re.search(r'systematic review|meta-analysis', (r.get('article_types') or '').lower() + ' ' + r['title'].lower()))
    yr = int(r['year']) if str(r.get('year', '')).isdigit() else 0
    rel = r['relevance_score']
    indexed = bool(r.get('pmid'))   # revista indexada en PubMed
    if rel >= 12 and sr: r['why'] = 'revisión sistemática / metaanálisis'; return 'A'
    if rel >= 11 and r['cites_per_year'] >= 10: r['why'] = 'muy citado (≥10 citas/año)'; return 'A'
    if rel >= MAXS and r['cites_per_year'] >= 5: r['why'] = 'pertinencia máxima y ≥5 citas/año'; return 'A'
    if rel >= MAXS and yr >= 2025 and indexed: r['why'] = 'pertinencia máxima, 2025-2026, indexado en PubMed'; return 'A'
    r['why'] = ''
    return 'B' if rel >= 11 else 'C'
CITES = 8
for r in L: r['tier'] = tier(r)
L.sort(key=lambda r: (r['tier'], -r['relevance_score'], -r['cites_per_year'], r['title']))
for i, r in enumerate(L, 1): r['n'] = i
short = [r for r in L if r['tier'] == 'A']

cols = ['n', 'tier', 'why', 'relevance_score', 'year', 'title', 'authors', 'journal', 'is_review', 'is_ieee', 'signals', 'cited_by', 'cites_per_year',
        'access', 'pdf_url', 'pmc_url', 'doi_url', 'url', 'pmid', 'pmcid', 'source', 'article_types', 'keywords', 'abstract']
os.makedirs(out, exist_ok=True)
def write(name, data):
    with open(f'{out}/{name}.csv', 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, cols, extrasaction='ignore'); w.writeheader(); w.writerows(data)
    with open(f'{out}/{name}.ris', 'w', encoding='utf-8') as fh:
        for r in data:
            fh.write('TY  - JOUR\n' + ''.join(f'AU  - {a.strip()}\n' for a in r['authors'].split(';') if a.strip()))
            for tag, key in [('TI', 'title'), ('JO', 'journal'), ('PY', 'year'), ('DO', 'doi'), ('AN', 'pmid'), ('UR', 'url'), ('L1', 'pdf_url'), ('AB', 'abstract')]:
                if r.get(key): fh.write(f"{tag}  - {' '.join(str(r[key]).split())}\n")
            fh.write('ER  - \n\n')
write('osa_ml_corpus', L); write('osa_ml_shortlist', short)
json.dump(L, open(f'{out}/osa_ml_corpus.json', 'w'), ensure_ascii=False, indent=1)
json.dump([{k: r.get(k, '') for k in ('n', 'title', 'year', 'pmid', 'pmcid', 'doi', 'pdf_url')} for r in short if r['pdf_url']],
          open(f'{out}/shortlist_pdfs.json', 'w'), ensure_ascii=False, indent=1)
C = collections.Counter
print(f'Europe PMC: {n_epmc} (nuevos {n_epmc_new}) | Consensus IEEE: {n_ci} (nuevos {n_ci_new}) | TOTAL corpus: {len(L)}')
print('scores:', sorted(C(r['relevance_score'] for r in L).items(), reverse=True))
print('tiers:', C(r['tier'] for r in L), '| shortlist:', len(short), '| con PDF libre:', sum(bool(r['pdf_url']) for r in short),
      '| IEEE:', sum(r['is_ieee'] == 'yes' for r in short), '| revisiones:', sum(r['is_review'] == 'yes' for r in short), '| sin DOI:', sum(not r.get('doi') for r in short))
print('corpus IEEE:', sum(r['is_ieee'] == 'yes' for r in L), '| corpus PDF libre:', sum(bool(r['pdf_url']) for r in L))
print('años shortlist:', sorted(C(r['year'] for r in short).items(), reverse=True)[:8])
