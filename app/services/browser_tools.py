"""
Browser Tools — инструменты веб-браузера для ИИ-агента BauNavigator.

Два инструмента передаются Клоду через Anthropic Tool Use API:
  web_search  — поиск через Jina Search API (s.jina.ai)
  fetch_page  — загрузка страницы через Jina Reader (r.jina.ai)

Claude сам решает когда и что искать, выполняет до MAX_TOOL_ROUNDS итераций,
после чего возвращает итоговый ответ с актуальными данными из сети.
"""
import urllib.request
import urllib.parse
import re
import logging

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5          # максимум итераций tool-loop
MAX_CONTENT_CHARS = 25_000  # обрезка ответа инструмента чтобы не раздуть контекст

_JINA_READER_BASE = 'https://r.jina.ai/'
_JINA_SEARCH_BASE = 'https://s.jina.ai/'
_WS_RE = re.compile(r'\n{3,}')

# ─── Схемы инструментов для Anthropic API ────────────────────────────────────

TOOLS = [
    {
        "name": "web_search",
        "description": (
            "Sucht im Internet nach aktuellen Informationen. "
            "Nutze dies für: aktuelle Baupreise, Grundstückspreise, neue Gesetze/HBO-Änderungen, "
            "Förderungsprogramme, Firmeninformationen, Bauamt-Kontakte, Bodenrichtwerte, "
            "Bebauungspläne und alles was nach deinem Wissensdatum liegen könnte. "
            "Gibt Top-Suchergebnisse als Markdown zurück."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Suchanfrage auf Deutsch oder Englisch. "
                        "Präzise Formulierung liefert bessere Ergebnisse. "
                        "Beispiel: 'Bodenrichtwert Groß-Umstadt 2025 €/m²'"
                    )
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch_page",
        "description": (
            "Lädt den vollständigen Inhalt einer bestimmten Webseite als sauberen Text. "
            "Nutze dies um: Bauamt-Websites zu lesen, Förderbedingungen nachzuschauen, "
            "Gesetztestexte abzurufen, Bebauungsplan-Dokumente zu lesen, "
            "oder Suchergebnis-Links zu vertiefen. "
            "Gibt den Seiteninhalt als Markdown zurück."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Vollständige URL der Seite (https://...)"
                }
            },
            "required": ["url"]
        }
    }
]


# ─── Ausführung ───────────────────────────────────────────────────────────────

def _jina_headers(jina_key: str = '') -> dict:
    h = {
        'Accept': 'text/plain',
        'X-Return-Format': 'text',
        'User-Agent': (
            'Mozilla/5.0 (compatible; BauNavigator-Agent/1.0; '
            '+https://baunavigator.de/bot)'
        ),
    }
    if jina_key:
        h['Authorization'] = f'Bearer {jina_key}'
    return h


def _do_web_search(query: str, jina_key: str = '') -> str:
    """Поиск через Jina Search API — возвращает Markdown с результатами."""
    encoded = urllib.parse.quote(query, safe='')
    url = _JINA_SEARCH_BASE + encoded
    try:
        req = urllib.request.Request(url, headers=_jina_headers(jina_key))
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode('utf-8', errors='replace')
        text = _WS_RE.sub('\n\n', text).strip()
        return text[:MAX_CONTENT_CHARS]
    except Exception as exc:
        logger.warning(f'[BrowserTools] web_search failed for "{query}": {exc}')
        return f'[Suche fehlgeschlagen: {exc}]'


def _do_fetch_page(url: str, jina_key: str = '') -> str:
    """Загрузка страницы через Jina Reader — возвращает чистый Markdown."""
    # Basic URL validation — only allow http(s) schemes
    if not re.match(r'^https?://', url, re.IGNORECASE):
        return '[Fehler: Nur http/https URLs erlaubt]'
    jina_url = _JINA_READER_BASE + url
    try:
        req = urllib.request.Request(jina_url, headers=_jina_headers(jina_key))
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode('utf-8', errors='replace')
        text = _WS_RE.sub('\n\n', text).strip()
        return text[:MAX_CONTENT_CHARS]
    except Exception as exc:
        logger.warning(f'[BrowserTools] fetch_page failed for "{url}": {exc}')
        # Fallback: direct request stripped of HTML tags
        try:
            req2 = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; BauNavigator/1.0)',
                'Accept-Language': 'de-DE,de;q=0.9',
            })
            with urllib.request.urlopen(req2, timeout=15) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
            raw = re.sub(
                r'<(script|style|nav|header|footer|aside|iframe)[^>]*>.*?</\1>',
                '', raw, flags=re.DOTALL | re.IGNORECASE
            )
            text = re.sub(r'<[^>]+>', ' ', raw)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:MAX_CONTENT_CHARS]
        except Exception as exc2:
            return f'[Seite nicht abrufbar: {exc2}]'


def execute_tool(tool_name: str, tool_input: dict, jina_key: str = '') -> str:
    """Диспетчер: вызывает нужный инструмент и возвращает строку-результат."""
    if tool_name == 'web_search':
        query = str(tool_input.get('query', '')).strip()
        if not query:
            return '[Fehler: query darf nicht leer sein]'
        logger.info(f'[BrowserTools] web_search: "{query}"')
        return _do_web_search(query, jina_key)

    if tool_name == 'fetch_page':
        url = str(tool_input.get('url', '')).strip()
        if not url:
            return '[Fehler: url darf nicht leer sein]'
        logger.info(f'[BrowserTools] fetch_page: {url}')
        return _do_fetch_page(url, jina_key)

    return f'[Unbekanntes Tool: {tool_name}]'
