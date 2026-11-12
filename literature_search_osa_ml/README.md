# Búsqueda de literatura: ML/IA para diagnóstico de AOS con señales fisiológicas

Fecha de ejecución: 2026-11-12. Sin límite de fechas ni de idioma.

## Estrategia

Cadena booleana original (4 bloques unidos con AND): IA/ML × AOS × señal fisiológica × diagnóstico/detección.

| Fuente | Cómo se consultó | Registros |
|---|---|---|
| PubMed (conector MCP) | Cadena exacta, todos los campos. El conector admite máx. 20 operadores, así que el bloque de señales se dividió en 3 consultas (488 + 142 + 181 resultados) y se unieron | 561 PMID únicos |
| Consensus (Semantic Scholar + OpenAlex + PubMed) | Búsqueda semántica equivalente, tope del plan = 300 | 300 (182 nuevos) |
| Scholar Gateway (Wiley, texto completo) | 2 consultas semánticas, 20 pasajes c/u | 18 artículos (16 nuevos) |
| **Total tras deduplicar (DOI / título normalizado)** | | **759** |

No disponibles en esta sesión: Elicit (el plan de la cuenta no incluye API), bioRxiv/medRxiv (el conector no
admite búsqueda por palabra clave), IEEE Xplore / Scopus / Web of Science (sin conector) y las API directas
de NCBI, OpenAlex y Europe PMC (bloqueadas por la política de red del entorno).

## Archivos

- `osa_ml_corpus.csv` — tabla maestra (UTF-8 con BOM, abre directo en Excel). Una fila por artículo.
- `osa_ml_corpus.ris` — para importar en Zotero / Mendeley / Rayyan.
- `osa_ml_corpus.json` — mismos datos en JSON.
- `pmids_unique.txt` — los 561 PMID de PubMed.
- `build_corpus.py` — script de consolidación (`python3 build_corpus.py <dir_crudos> <dir_salida>`).

## Columnas auxiliares (generadas por reglas de texto, no por lectura manual)

- `signals`: modalidades detectadas en título + resumen + palabras clave (PSG, EEG, EOG, EMG, ECG/HRV, Airflow,
  Resp. effort, SpO2/Oximetry, PPG, Snoring/Audio, Capnography).
- `is_review`: el tipo de publicación o el título contiene "review" o "meta-analysis".
- `mentions_apnea`: `no` marca registros probablemente fuera de tema (8).

## Limitaciones

- Esto es la fase de **identificación**; no se ha hecho cribado por título/resumen ni evaluación de elegibilidad.
- "OSA" y "Diagnosis" en todos los campos hacen la cadena sensible pero poco específica: hay registros donde la
  IA o la AOS son secundarias.
- Los registros que solo vienen de Consensus no traen DOI (limitación del plan); traen enlace a Consensus.
- Los resultados de Consensus y Scholar Gateway son semánticos (ordenados por relevancia y truncados), no
  reproducibles como una cadena booleana. Varios de Scholar Gateway son tangenciales.
- Un PMID se fusionó con otro registro por tener título idéntico (560 filas de PubMed para 561 PMID).
