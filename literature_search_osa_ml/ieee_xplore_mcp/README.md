# IEEE Xplore MCP

Servidor MCP (stdio) que busca en IEEE Xplore con la API oficial de metadatos.

| Herramienta | Qué hace |
|---|---|
| `ieee_search_articles` | Búsqueda booleana (`query`) o por campos (título, resumen, autor, términos, revista/congreso), con filtros de año, tipo de contenido y acceso abierto, orden y paginación (`limit` ≤ 200, `offset`). |
| `ieee_get_article` | Metadatos completos de un artículo por `article_number` o `doi`. |

Cada artículo trae título, autores, publicación, año, DOI, `html_url`, `pdf_url`, tipo de acceso, citas y resumen.
`pdf_url` solo se descarga sin suscripción cuando `open_access` es `true`.

## Instalación

1. Pide una clave gratuita en <https://developer.ieee.org> (producto *Metadata Search*). La activación la aprueba IEEE y puede tardar unos días; hasta entonces la API responde `Developer Inactive`.
2. `pip install mcp`
3. Registra el servidor.

Claude Code:

```bash
claude mcp add ieee-xplore --env IEEE_API_KEY=TU_CLAVE -- python /ruta/a/ieee_xplore_mcp/server.py
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ieee-xplore": {
      "command": "python",
      "args": ["C:\\ruta\\a\\ieee_xplore_mcp\\server.py"],
      "env": { "IEEE_API_KEY": "TU_CLAVE" }
    }
  }
}
```

No guardes la clave en el repositorio. El plan gratuito permite 200 llamadas al día.

## Pruebas

```bash
python -m unittest test_server -v
```

Las 7 pruebas simulan la respuesta HTTP. El servidor también se probó por stdio contra la API real: lista las dos
herramientas y la API responde, pero **no se ha probado con una clave válida**, así que los nombres de parámetros y
campos siguen la documentación de IEEE y no una respuesta real observada.
