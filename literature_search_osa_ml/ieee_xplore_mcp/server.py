#!/usr/bin/env python3
"""Servidor MCP para IEEE Xplore (API oficial de metadatos, https://developer.ieee.org).

Herramientas:
  ieee_search_articles  — búsqueda booleana o por campos, con filtros y paginación.
  ieee_get_article      — metadatos de un artículo por número de artículo o DOI.

Requiere la variable de entorno IEEE_API_KEY (clave gratuita de developer.ieee.org).
Transporte: stdio.  Dependencia única: `pip install mcp`.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Annotated, Literal, Optional

from mcp.types import ToolAnnotations
from pydantic import Field

try:  # SDK de MCP 2.x
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:  # SDK de MCP 1.x
    from mcp.server.fastmcp import FastMCP

API_URL = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
MAX_RECORDS = 200  # tope de la API por llamada
ABSTRACT_PREVIEW = 600

mcp = FastMCP("ieee_xplore_mcp")


class IeeeApiError(Exception):
    """Error con un mensaje pensado para que el agente sepa qué hacer."""


def _call_api(params: dict) -> dict:
    key = os.environ.get("IEEE_API_KEY", "").strip()
    if not key:
        raise IeeeApiError(
            "Falta la variable de entorno IEEE_API_KEY. Regístrate en https://developer.ieee.org, "
            "solicita una clave para 'Metadata Search' y defínela en la configuración del servidor MCP."
        )
    query = {k: v for k, v in params.items() if v not in (None, "")}
    query.update(apikey=key, format="json")
    url = API_URL + "?" + urllib.parse.urlencode(query)
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        if e.code == 403:
            raise IeeeApiError(
                f"IEEE rechazó la clave (HTTP 403: {detail.strip()}). 'Developer Inactive' significa que la clave "
                "aún no está activada; 'Developer Over Qps/Rate' significa que se agotó la cuota (200 llamadas/día)."
            ) from e
        raise IeeeApiError(f"La API de IEEE respondió HTTP {e.code}: {detail.strip()}") from e
    except urllib.error.URLError as e:
        raise IeeeApiError(f"No se pudo conectar con ieeexploreapi.ieee.org: {e.reason}") from e
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise IeeeApiError(f"Respuesta no JSON de IEEE: {body[:200]}") from e


def _format_article(a: dict, full_abstract: bool) -> dict:
    authors = [x.get("full_name", "") for x in (a.get("authors") or {}).get("authors", [])]
    abstract = a.get("abstract") or ""
    if not full_abstract and len(abstract) > ABSTRACT_PREVIEW:
        abstract = abstract[:ABSTRACT_PREVIEW].rstrip() + "…"
    terms = a.get("index_terms") or {}
    keywords = sorted({t for group in terms.values() for t in group.get("terms", [])})
    doi = a.get("doi") or ""
    return {
        "article_number": a.get("article_number", ""),
        "title": a.get("title", ""),
        "authors": authors,
        "publication_title": a.get("publication_title", ""),
        "year": a.get("publication_year", ""),
        "content_type": a.get("content_type", ""),
        "doi": doi,
        "doi_url": f"https://doi.org/{doi}" if doi else "",
        "html_url": a.get("html_url", ""),
        "pdf_url": a.get("pdf_url", ""),
        "access_type": a.get("access_type", ""),
        "open_access": str(a.get("access_type", "")).upper() in ("OPEN_ACCESS", "EPHEMERA"),
        "citing_paper_count": a.get("citing_paper_count", 0),
        "keywords": keywords,
        "abstract": abstract,
    }


@mcp.tool(
    name="ieee_search_articles",
    annotations=ToolAnnotations(title="Buscar artículos en IEEE Xplore", readOnlyHint=True, destructiveHint=False,
                                idempotentHint=True, openWorldHint=True),
)
def ieee_search_articles(
    query: Annotated[Optional[str], Field(description=(
        "Consulta booleana sobre metadatos y resumen. Admite AND, OR, NOT, paréntesis y frases entre comillas. "
        'Ejemplo: ("deep learning" OR "machine learning") AND "sleep apnea" AND (ECG OR oximetry)'))] = None,
    title: Annotated[Optional[str], Field(description="Palabras que deben aparecer en el título.")] = None,
    abstract: Annotated[Optional[str], Field(description="Palabras que deben aparecer en el resumen.")] = None,
    author: Annotated[Optional[str], Field(description="Nombre de autor, p. ej. 'Hornero R'.")] = None,
    index_terms: Annotated[Optional[str], Field(description="Términos de indización (IEEE Terms, palabras clave del autor).")] = None,
    publication_title: Annotated[Optional[str], Field(description="Revista o congreso, p. ej. 'IEEE Journal of Biomedical and Health Informatics'.")] = None,
    start_year: Annotated[Optional[int], Field(ge=1900, le=2100, description="Año inicial (inclusive).")] = None,
    end_year: Annotated[Optional[int], Field(ge=1900, le=2100, description="Año final (inclusive).")] = None,
    content_type: Annotated[Optional[Literal["Journals", "Conferences", "Early Access", "Magazines", "Books", "Standards", "Courses"]],
                            Field(description="Tipo de contenido.")] = None,
    open_access_only: Annotated[bool, Field(description="Si es true, solo artículos de acceso abierto (PDF descargable sin suscripción).")] = False,
    sort_by: Annotated[Literal["relevance", "newest", "oldest", "title"], Field(description="Orden de los resultados.")] = "relevance",
    limit: Annotated[int, Field(ge=1, le=MAX_RECORDS, description="Resultados por página (máx. 200).")] = 25,
    offset: Annotated[int, Field(ge=0, description="Resultados a saltar; usa next_offset de la respuesta anterior para paginar.")] = 0,
    full_abstracts: Annotated[bool, Field(description="Si es false, cada resumen se recorta a 600 caracteres para ahorrar contexto.")] = False,
) -> str:
    """Busca artículos, ponencias y capítulos en IEEE Xplore y devuelve metadatos con enlaces.

    Da al menos uno de: query, title, abstract, author, index_terms o publication_title.
    Devuelve JSON: {total, count, offset, has_more, next_offset, articles[]}; cada artículo trae
    article_number, title, authors, publication_title, year, content_type, doi, doi_url, html_url,
    pdf_url, access_type, open_access, citing_paper_count, keywords y abstract.
    pdf_url solo se descarga sin suscripción cuando open_access es true.
    Cada llamada cuenta para la cuota diaria de la clave (200 llamadas/día en el plan gratuito):
    usa limit alto y pagina en vez de repetir consultas pequeñas.
    """
    if not any([query, title, abstract, author, index_terms, publication_title]):
        return json.dumps({"error": "Indica al menos un criterio: query, title, abstract, author, index_terms o publication_title."}, ensure_ascii=False)
    sort = {"relevance": (None, None), "newest": ("publication_year", "desc"),
            "oldest": ("publication_year", "asc"), "title": ("article_title", "asc")}[sort_by]
    params = dict(querytext=query, article_title=title, abstract=abstract, author=author, index_terms=index_terms,
                  publication_title=publication_title, start_year=start_year, end_year=end_year, content_type=content_type,
                  open_access="True" if open_access_only else None, sort_field=sort[0], sort_order=sort[1],
                  max_records=limit, start_record=offset + 1)
    try:
        data = _call_api(params)
    except IeeeApiError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    articles = [_format_article(a, full_abstracts) for a in data.get("articles", [])]
    total = int(data.get("total_records", 0))
    has_more = offset + len(articles) < total
    return json.dumps({"total": total, "count": len(articles), "offset": offset, "has_more": has_more,
                       "next_offset": offset + len(articles) if has_more else None, "articles": articles},
                      ensure_ascii=False, indent=1)


@mcp.tool(
    name="ieee_get_article",
    annotations=ToolAnnotations(title="Obtener un artículo de IEEE Xplore", readOnlyHint=True, destructiveHint=False,
                                idempotentHint=True, openWorldHint=True),
)
def ieee_get_article(
    article_number: Annotated[Optional[str], Field(description="Número de artículo de IEEE Xplore, p. ej. '8952673' (el de la URL /document/8952673).")] = None,
    doi: Annotated[Optional[str], Field(description="DOI, p. ej. '10.1109/JBHI.2019.2951346'.")] = None,
) -> str:
    """Devuelve los metadatos completos (con resumen íntegro y enlaces) de un artículo de IEEE Xplore.

    Indica article_number o doi (uno de los dos). Devuelve el mismo esquema por artículo que
    ieee_search_articles, o {"error": ...} si no existe.
    """
    if bool(article_number) == bool(doi):
        return json.dumps({"error": "Indica exactamente uno: article_number o doi."}, ensure_ascii=False)
    if doi:
        doi = doi.strip().removeprefix("https://doi.org/")
    try:
        data = _call_api(dict(article_number=article_number, doi=doi, max_records=1))
    except IeeeApiError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    arts = data.get("articles", [])
    if not arts:
        return json.dumps({"error": f"IEEE Xplore no tiene un artículo con {'DOI ' + doi if doi else 'número ' + str(article_number)}. "
                                    "Verifica el identificador o búscalo por título con ieee_search_articles."}, ensure_ascii=False)
    return json.dumps(_format_article(arts[0], full_abstract=True), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    mcp.run()
