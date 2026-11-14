#!/usr/bin/env python3
"""Descarga los PDF de acceso abierto del corpus a una carpeta local.

Fuente principal: el repositorio abierto de PubMed Central en AWS (sin registro ni clave).
Para los pocos PDF libres alojados fuera de PMC se intenta el enlace directo.
Solo usa la biblioteca estándar de Python 3.8+.

  python download_pdfs.py                      # lista depurada (nivel A) -> carpeta ./pdfs
  python download_pdfs.py --tier AB            # niveles A y B
  python download_pdfs.py --tier ABC -o todos  # todo el corpus con PDF libre
"""
import argparse, csv, os, re, sys, time, unicodedata, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

BUCKET = 'https://pmc-oa-opendata.s3.amazonaws.com'
NS = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
UA = {'User-Agent': 'osa-ml-literature-downloader/1.0 (python-urllib)'}


def fetch(url, timeout=120):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception:
            if attempt == 2: raise
            time.sleep(2 * (attempt + 1))


def pmc_pdf_url(pmcid):
    """URL del PDF de la versión más reciente del artículo en el repositorio abierto de PMC, o None."""
    xml = fetch(f'{BUCKET}/?list-type=2&prefix={urllib.parse.quote(pmcid)}.&max-keys=200')
    keys = [k.text for k in ET.fromstring(xml).iterfind('.//s3:Contents/s3:Key', NS)]
    best = None
    for k in keys:
        m = re.fullmatch(rf'{pmcid}\.(\d+)/{pmcid}\.\d+\.pdf', k)
        if m and (best is None or int(m.group(1)) > best[0]): best = (int(m.group(1)), k)
    return f'{BUCKET}/{best[1]}' if best else None


def filename(row):
    ascii_ = lambda s: unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    author = re.sub(r'[^A-Za-z]', '', ascii_(row['authors'].split(';')[0]).split(' ')[0]) or 'Anon'
    title = re.sub(r'[^A-Za-z0-9]+', '-', ascii_(row['title'])).strip('-')[:70]
    return f"{int(row['n']):04d}_{row['year'] or 'sf'}_{author}_{title}.pdf"


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--corpus', default=os.path.join(here, 'osa_ml_corpus.csv'))
    ap.add_argument('--tier', default='A', help='niveles a descargar: A, AB o ABC (por defecto A)')
    ap.add_argument('-o', '--out', default=os.path.join(here, 'pdfs'))
    args = ap.parse_args()
    rows = [r for r in csv.DictReader(open(args.corpus, encoding='utf-8-sig')) if r['tier'] in args.tier.upper() and r['pdf_url']]
    os.makedirs(args.out, exist_ok=True)
    log, ok = [], 0
    for i, r in enumerate(rows, 1):
        dest = os.path.join(args.out, filename(r)); status = ''
        if os.path.exists(dest) and os.path.getsize(dest) > 10_000:
            status = 'ya existía'
        else:
            try:
                url = pmc_pdf_url(r['pmcid']) if r['pmcid'] else None
                if not url and r['pmcid']: status = 'en PMC pero fuera del subconjunto de acceso abierto; abrir pdf_url en el navegador'
                url = url or (None if r['pmcid'] else r['pdf_url'])
                if url:
                    data = fetch(url)
                    if data[:5] != b'%PDF-': status = 'el enlace no devolvió un PDF; abrir pdf_url en el navegador'
                    else:
                        open(dest, 'wb').write(data); status = 'descargado'
            except Exception as e:
                status = f'error: {e}'
        ok += status in ('descargado', 'ya existía')
        log.append(dict(n=r['n'], status=status, file=os.path.basename(dest) if status in ('descargado', 'ya existía') else '',
                        title=r['title'], pdf_url=r['pdf_url'], doi_url=r['doi_url']))
        print(f'[{i}/{len(rows)}] {status}: {r["title"][:80]}', flush=True)
    with open(os.path.join(args.out, '_descargas.csv'), 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, list(log[0])); w.writeheader(); w.writerows(log)
    print(f'\n{ok} de {len(rows)} PDF en {args.out}. Detalle en _descargas.csv')


if __name__ == '__main__':
    sys.exit(main())
