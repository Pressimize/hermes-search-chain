"""REST calls to the search services of the chain (design section 6).

Every function returns a dict and never raises: ``{"rows": [...]}`` for a valid reply (possibly without rows),
else ``{"error": "<Provider>: <detail>", "code": "<short code>", "status": <HTTP status or None>}``.
For SearXNG and Degoog the ``key`` argument is the address of the user's instance (A13).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from urllib.parse import quote, urlsplit

import httpx

EXA_URL = "https://api.exa.ai/search"
PARALLEL_URL = "https://api.parallel.ai/v1beta/search"  # A2, D2: the call Hermes' built-in provider makes
PARALLEL_BETA = "search-extract-2025-10-10"
PARALLEL_V1_URL = "https://api.parallel.ai/v1/search"
FIRECRAWL_URL = "https://api.firecrawl.dev/v2/search"
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
NIMBLE_URL = "https://sdk.nimbleway.com/v2/search"
TAVILY_URL = "https://api.tavily.com/search"
YOUCOM_URL = "https://ydc-index.io/v1/search"

# A0: timeout per request in seconds (httpx applies it to each phase).
EXA_TIMEOUT = 10.0
PARALLEL_TIMEOUT = 15.0
BRAVE_TIMEOUT = 10.0
NIMBLE_TIMEOUT = 15.0
TAVILY_TIMEOUT = 15.0
YOUCOM_TIMEOUT = 10.0
SEARXNG_TIMEOUT = 15.0
DEGOOG_TIMEOUT = 10.0
FIRECRAWL_TIMEOUT = 15.0
ERROR_MAX = 200  # A4
ERROR_SCAN = 2000  # A4: only this many characters of a reply are cleaned up for the error text
KEY_MIN = 8  # S3: a shorter value is not masked as a key
EXA_HIGHLIGHT_CHARS = 600  # A1, D3
MAX_RESULTS = 20  # A6
TITLE_MAX = 300  # S4
TEXT_MAX = 16000  # S4: no description is longer than this
FIRECRAWL_TEXT_MAX = 3000  # A3, D12


def _error(provider: str, detail: object, code: str, key: str, status: int | None = None) -> dict:
    text = str(detail)
    forms = {key, quote(key, safe="", errors="surrogatepass")} if len(key) >= KEY_MIN else ()
    for form in forms:  # S3: a reply that echoes the key, as sent or percent-encoded and in any case
        text = re.sub(re.escape(form), "[key]", text, flags=re.IGNORECASE)
    # A4: one line of printable characters, so a reply cannot add lines to the log
    text = " ".join("".join(c if c.isprintable() else " " for c in text[:ERROR_SCAN]).split())
    return {"error": f"{provider}: {text[:ERROR_MAX]}", "code": code, "status": status}


def _malformed(provider: str, key: str) -> dict:
    return _error(provider, "malformed reply", "malformed", key)


def _reason(body: object) -> str:
    """A4: the vendor's own reason in a JSON body, or ""."""
    if isinstance(body, dict):
        for field in ("tag", "error", "message", "detail"):
            value = body.get(field)
            if isinstance(value, list):  # e.g. Tavily's validation errors: [{"msg": ...}, ...]
                value = value[0] if value else None
                if isinstance(value, dict):
                    value = value.get("msg")
            elif isinstance(value, dict):  # e.g. Brave {"error": {"detail": ...}}, Tavily {"detail": {"error": ...}}
                value = value.get("message") or value.get("detail") or value.get("error")
            if value:
                return str(value)
    return ""


def _detail(response: httpx.Response) -> str:
    """A4: the vendor's own reason for a non-2xx reply."""
    try:
        body = response.json()
    except (ValueError, RecursionError):  # an unreadable body must not hide the status (K5)
        body = None
    return _reason(body) or response.text.strip()


def _send(provider: str, key: str, send: Callable[[], httpx.Response]) -> tuple[dict | None, dict | None]:
    """(JSON object of a 2xx reply, None) or (None, error dict)."""
    try:
        try:
            response = send()
        except ValueError as exc:  # e.g. a key or query httpx cannot encode: no reply was read (A4)
            return None, _error(provider, type(exc).__name__, type(exc).__name__, key)
        if not 200 <= response.status_code < 300:
            status = response.status_code
            return None, _error(provider, f"HTTP {status} {_detail(response)}", f"http_{status}", key, status)
        data = response.json()
    except httpx.TimeoutException:
        return None, _error(provider, "timeout", "timeout", key)
    except (ValueError, RecursionError):  # not JSON, or nested too deeply to parse
        return None, _malformed(provider, key)
    except Exception as exc:  # transport errors; only the class name, never the text (A13: it may hold an address)
        return None, _error(provider, type(exc).__name__, type(exc).__name__, key)
    if not isinstance(data, dict):
        return None, _malformed(provider, key)
    return data, None


def _post(
    client: httpx.Client, provider: str, url: str, key: str, timeout: float, headers: dict, body: dict
) -> tuple[dict | None, dict | None]:
    return _send(provider, key, lambda: client.post(url, json=body, headers=headers, timeout=timeout))


def _get(
    client: httpx.Client, provider: str, url: str, key: str, timeout: float, headers: dict, params: dict
) -> tuple[dict | None, dict | None]:
    return _send(provider, key, lambda: client.get(url, params=params, headers=headers, timeout=timeout))


def _str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _rows(
    provider: str,
    key: str,
    items: object,
    text: Callable[[dict], str],
    text_max: int = TEXT_MAX,
    limit: int | None = None,
    clean: Callable[[str], str] | None = None,
) -> dict:
    """S4: rows in Hermes' key order, numbered from 1; an item without an http(s) URL is dropped.
    ``text`` builds the description of one item, cut to ``text_max`` characters; ``limit`` keeps the first rows;
    ``clean`` is applied to title and description before they are cut."""
    if items is None:
        items = []
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        return _malformed(provider, key)
    hits = [item for item in items if _str(item.get("url")).lower().startswith(("http://", "https://"))]
    clean = clean or (lambda value: value)
    return {
        "rows": [
            {
                "url": item["url"],
                "title": clean(_str(item.get("title")))[:TITLE_MAX],
                "description": clean(text(item))[:text_max],
                "position": position,
            }
            for position, item in enumerate(hits[:limit], 1)
        ]
    }


def _joined(field: str) -> Callable[[dict], str]:
    def text(item: dict) -> str:
        parts = item.get(field)
        return " ".join(part for part in parts if isinstance(part, str)) if isinstance(parts, list) else ""

    return text


def _field(field: str) -> Callable[[dict], str]:
    return lambda item: _str(item.get(field))


def _base(provider: str, value: str) -> tuple[str | None, dict | None]:
    """A13: the address of a self-hosted instance without trailing slashes, or a ``bad_url`` error."""
    base = value.rstrip("/")
    try:
        parts = urlsplit(base)
        parts.port  # noqa: B018 - raises ValueError for a port that is no number or out of range
    except ValueError:
        parts = None
    valid = (
        parts is not None
        and parts.scheme in ("http", "https")
        and bool(parts.hostname)
        and not any(c in "?#" or c.isspace() or not c.isprintable() for c in base)
    )
    return (base, None) if valid else (None, _error(provider, "invalid URL setting", "bad_url", ""))


def exa(client: httpx.Client, query: str, limit: int, key: str, highlight_chars: int = EXA_HIGHLIGHT_CHARS) -> dict:
    """A1: ``highlight_chars`` 0 requests Exa's default highlights."""
    highlights = {"maxCharacters": highlight_chars} if highlight_chars else True
    body = {"query": query, "numResults": limit, "contents": {"highlights": highlights}}
    data, error = _post(client, "Exa", EXA_URL, key, EXA_TIMEOUT, {"x-api-key": key}, body)
    return error or _rows("Exa", key, data.get("results"), _joined("highlights"))


def parallel(client: httpx.Client, query: str, limit: int, key: str, v1: bool = False) -> dict:
    """A2: beta endpoint in mode ``agentic``, as Hermes' built-in provider calls it (D2).
    ``v1`` selects the GA endpoint in mode ``advanced`` instead."""
    results = min(limit, MAX_RESULTS)
    if v1:
        url, headers = PARALLEL_V1_URL, {"x-api-key": key}
        body = {
            "objective": query,
            "search_queries": [query],
            "mode": "advanced",
            "advanced_settings": {"max_results": results},
        }
    else:
        url, headers = PARALLEL_URL, {"x-api-key": key, "parallel-beta": PARALLEL_BETA}
        body = {"search_queries": [query], "objective": query, "mode": "agentic", "max_results": results}
    data, error = _post(client, "Parallel", url, key, PARALLEL_TIMEOUT, headers, body)
    return error or _rows("Parallel", key, data.get("results"), _joined("excerpts"))


def _no_strong(text: str) -> str:
    return re.sub(r"</?strong>", "", text, flags=re.IGNORECASE)


def brave(client: httpx.Client, query: str, limit: int, key: str) -> dict:
    """A7: Brave marks query words with <strong>; the tags are removed before the cut."""
    headers = {"X-Subscription-Token": key, "Accept": "application/json"}
    data, error = _get(client, "Brave", BRAVE_URL, key, BRAVE_TIMEOUT, headers, {"q": query, "count": limit})
    if error:
        return error
    web = data.get("web")
    if web is None:  # a reply without a web section is a valid reply without hits
        return {"rows": []}
    if not isinstance(web, dict):
        return _malformed("Brave", key)
    return _rows("Brave", key, web.get("results"), _field("description"), limit=limit, clean=_no_strong)


def nimble(client: httpx.Client, query: str, limit: int, key: str) -> dict:
    """A8."""
    body = {"query": query, "search_depth": "lite", "focus": "general", "full_content": False, "max_results": limit}
    headers = {"Authorization": f"Bearer {key}"}
    data, error = _post(client, "Nimble", NIMBLE_URL, key, NIMBLE_TIMEOUT, headers, body)
    return error or _rows("Nimble", key, data.get("results"), _field("description"), limit=limit)


def tavily(client: httpx.Client, query: str, limit: int, key: str) -> dict:
    """A9."""
    body = {"query": query, "search_depth": "basic", "max_results": limit, "include_answer": False}
    headers = {"Authorization": f"Bearer {key}"}
    data, error = _post(client, "Tavily", TAVILY_URL, key, TAVILY_TIMEOUT, headers, body)
    return error or _rows("Tavily", key, data.get("results"), _field("content"), limit=limit)


def _youcom_text(item: dict) -> str:
    snippets = item.get("snippets")
    parts = [_str(item.get("description"))] + (snippets if isinstance(snippets, list) else [])
    return " ".join(part for part in parts if isinstance(part, str) and part)


def youcom(client: httpx.Client, query: str, limit: int, key: str) -> dict:
    """A10: ``count`` applies per section (web, news); only web results are used."""
    body = {"query": query, "count": limit}
    data, error = _post(client, "You.com", YOUCOM_URL, key, YOUCOM_TIMEOUT, {"X-API-Key": key}, body)
    if error:
        return error
    results = data.get("results")
    if not isinstance(results, dict):
        return _malformed("You.com", key)
    return _rows("You.com", key, results.get("web"), _youcom_text, limit=limit)


def searxng(client: httpx.Client, query: str, limit: int, key: str) -> dict:
    """A11: ``key`` is the instance address; results in the order the instance sends them."""
    base, error = _base("SearXNG", key)
    if error:
        return error
    params = {"q": query, "format": "json"}
    data, error = _get(client, "SearXNG", f"{base}/search", base, SEARXNG_TIMEOUT, {}, params)
    return error or _rows("SearXNG", base, data.get("results"), _field("content"), limit=limit)


def degoog(client: httpx.Client, query: str, limit: int, key: str) -> dict:
    """A12: ``key`` is the instance address; results in the order the instance sends them."""
    base, error = _base("Degoog", key)
    if error:
        return error
    data, error = _get(client, "Degoog", f"{base}/api/search", base, DEGOOG_TIMEOUT, {}, {"q": query})
    return error or _rows("Degoog", base, data.get("results"), _field("snippet"), limit=limit)


def firecrawl(client: httpx.Client, query: str, limit: int, key: str) -> dict:
    """A3."""
    headers = {"Authorization": f"Bearer {key}"}
    body = {"query": query, "limit": limit}
    data, error = _post(client, "Firecrawl", FIRECRAWL_URL, key, FIRECRAWL_TIMEOUT, headers, body)
    if error:
        return error
    if data.get("success") is False:  # A3: a 2xx reply that reports a failure keeps its reason, if it has one
        rejected = _error("Firecrawl", _reason(data), "rejected", key)
        if rejected["error"] != "Firecrawl: ":
            return rejected
    payload = data.get("data")
    if data.get("success") is not True or not isinstance(payload, dict):
        return _malformed("Firecrawl", key)
    return _rows("Firecrawl", key, payload.get("web"), lambda item: _str(item.get("description")), FIRECRAWL_TEXT_MAX)
