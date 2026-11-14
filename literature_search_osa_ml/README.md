# Búsqueda de literatura: ML/IA para diagnóstico de AOS con señales fisiológicas

Última ejecución: 2026-11-14. Sin límite de fechas ni de idioma.

## Qué hay aquí

| Archivo | Contenido |
|---|---|
| `osa_ml_shortlist.csv` / `.ris` | **Lista depurada (nivel A): 117 artículos.** Empieza por aquí. |
| `osa_ml_corpus.csv` / `.ris` / `.json` | Corpus completo: 1 213 registros únicos, ordenados por nivel y pertinencia. |
| `download_pdfs.py` | Descarga a `./pdfs` los PDF de acceso abierto (no se versionan en git). |
| `ieee_xplore_mcp/` | Servidor MCP para buscar en IEEE Xplore (requiere clave gratuita de IEEE). |
| `build_corpus.py`, `fetch_europepmc.py`, `resolve_dois.py`, `curate.py` | Scripts que reproducen el corpus. |
| `pmids_unique.txt` | PMID de la búsqueda original en PubMed. |

Los CSV están en UTF-8 con BOM (abren directo en Excel). Los RIS se importan en Zotero, Mendeley o Rayyan.

## Fuentes

| Fuente | Consulta | Registros | Nuevos |
|---|---|---|---|
| PubMed | Cadena booleana original, todos los campos (3 consultas por el límite de 20 operadores del conector) | 561 | 560 |
| Consensus | Búsqueda semántica general, tope 300 | 300 | 182 |
| Scholar Gateway (Wiley) | 2 consultas semánticas | 18 | 16 |
| Europe PMC | Los 4 bloques restringidos a título/resumen, con sinónimos añadidos; incluye preprints | 674 | 246 |
| Consensus, editorial IEEE | Búsqueda semántica restringida a IEEE, tope 300 | 300 | 208 |
| **Total deduplicado** | | | **1 213** |

Además: Crossref resolvió por título 339 DOI que faltaban (quedan 25 registros sin DOI) y Europe PMC aportó
PMCID, citas y enlaces de texto completo. 407 registros son de IEEE (revistas, congresos o DOI 10.1109).

No disponibles: la API de IEEE Xplore (falta clave; ver `ieee_xplore_mcp/`), Elicit (el plan no incluye API),
OpenAlex (cuota gratuita agotada sin clave), Scopus y Web of Science (sin conector).

## Cómo se depuró

`relevance_score` (máx. 13) se calcula con reglas de texto sobre título y resumen, definidas en `curate.py`:

- apnea en el título +3 (solo en el resumen +1; ausente −6)
- término de IA/ML en el título +3 (solo en el resumen +2; ausente −4)
- alguna señal fisiológica +2, y +1 si está en el título (ninguna −2)
- tarea diagnóstica (detección, clasificación, cribado, severidad, IAH) en el título +2 (solo resumen +1)
- el resumen reporta métricas (sensibilidad, especificidad, exactitud, AUC, F1) +2
- penalizaciones: imagen (CBCT, RM, foto facial) −3, tratamiento (CPAP, cirugía) −2, solo estadificación de sueño −2,
  modelo animal −3, protocolo/editorial/errata/resumen de congreso −4, sin resumen −2

Nivel **A** (lista depurada) si cumple alguna de estas, registrada en la columna `why`:

| Criterio | Artículos |
|---|---|
| Muy citado: pertinencia ≥ 11 y ≥ 10 citas/año | 37 |
| Pertinencia máxima (13) y ≥ 5 citas/año | 31 |
| Revisión sistemática o metaanálisis con pertinencia ≥ 12 | 25 |
| Pertinencia máxima, 2025–2026, indexado en PubMed | 24 |

Nivel **B** (593): pertinencia ≥ 11 sin cumplir lo anterior. Nivel **C** (503): el resto.

## PDF

Columnas de acceso en los CSV: `access`, `pdf_url` (PDF libre), `pmc_url`, `doi_url`.

- Lista depurada: 61 de 117 tienen PDF libre; los otros 56 requieren suscripción (entra por `doi_url` con el acceso de la biblioteca).
- Corpus completo: 458 con PDF libre.

```bash
python download_pdfs.py              # nivel A -> ./pdfs
python download_pdfs.py --tier AB    # niveles A y B
```

El script baja de PubMed Central (repositorio abierto en AWS, sin clave) y deja el detalle en `pdfs/_descargas.csv`.
Los artículos en PMC que no pertenecen al subconjunto de acceso abierto (manuscritos de autor) hay que abrirlos en el
navegador con `pdf_url`: Europe PMC bloquea la descarga automática.

## Limitaciones

- La depuración es por reglas de texto, no por lectura: sirve para priorizar, no sustituye el cribado manual.
  Antes de descartar el nivel B conviene revisarlo; ahí quedan artículos pertinentes poco citados o de congreso.
- Las citas vienen de Europe PMC o Consensus (se toma el mayor); favorecen a los artículos más antiguos.
- Los registros que solo vienen de Consensus traen resumen pero no tipo de publicación ni palabras clave.
- Las búsquedas semánticas (Consensus, Scholar Gateway) están ordenadas por relevancia y truncadas; no son
  reproducibles como una cadena booleana.
