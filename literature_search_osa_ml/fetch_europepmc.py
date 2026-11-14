"""Descarga de Europe PMC (a) la búsqueda enfocada a título/resumen y (b) los metadatos de acceso
abierto de una lista de PMID. Uso: python3 fetch_europepmc.py <dir_salida> [pmids.txt]"""
import json, sys, time, urllib.parse, urllib.request
API = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search'
ta = lambda terms: '(' + ' OR '.join(f'TITLE:"{t}" OR ABSTRACT:"{t}"' for t in terms) + ')'
AI = ['machine learning', 'artificial intelligence', 'deep learning', 'classification algorithm', 'neural network',
      'support vector machine', 'random forest']
OSA = ['obstructive sleep apnea', 'obstructive sleep apnoea', 'sleep apnea', 'sleep apnoea', 'OSAS', 'sleep-disordered breathing']
SIG = ['physiological signal', 'biosignal', 'polysomnography', 'electroencephalography', 'EEG', 'electrooculography',
       'electromyography', 'electrocardiogram', 'electrocardiography', 'ECG', 'airflow', 'thoracic effort', 'abdominal effort',
       'respiratory effort', 'oximetry', 'SpO2', 'photoplethysmography', 'PPG', 'snoring', 'capnography']
DX = ['diagnostic accuracy', 'diagnosis', 'detection', 'screening', 'classification']
QUERY = ' AND '.join(ta(b) for b in (AI, OSA, SIG, DX))

def search(query, page=1000):
    cursor, out = '*', []
    while True:
        url = API + '?' + urllib.parse.urlencode(dict(query=query, format='json', resultType='core', pageSize=page, cursorMark=cursor))
        for attempt in range(4):
            try:
                d = json.load(urllib.request.urlopen(url, timeout=120)); break
            except Exception as e:
                if attempt == 3: raise
                time.sleep(2 ** (attempt + 1))
        res = d['resultList']['result']; out += res
        nxt = d.get('nextCursorMark')
        if not res or not nxt or nxt == cursor: return out
        cursor = nxt

if __name__ == '__main__':
    out = sys.argv[1]
    r = search(QUERY); json.dump(r, open(f'{out}/epmc_search.json', 'w')); print('búsqueda enfocada:', len(r))
    if len(sys.argv) > 2:
        ids = open(sys.argv[2]).read().split(); got = []
        for i in range(0, len(ids), 150):
            got += search('SRC:MED AND EXT_ID:(' + ' OR '.join(ids[i:i + 150]) + ')')
        json.dump(got, open(f'{out}/epmc_pmids.json', 'w')); print('PMID resueltos:', len(got), 'de', len(ids))
