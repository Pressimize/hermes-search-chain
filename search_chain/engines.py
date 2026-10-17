"""REST calls to Exa, Parallel and Firecrawl search (design section 6).

Every function returns a dict and never raises: ``{"rows": [...]}`` for a valid reply (possibly without rows),
else ``{"error": "<Provider>: <detail>", "code": "<short code>", "status": <HTTP status or None>}``.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

EXA_URL = "https://api.exa.ai/search"
PARALLEL_URL = "https://api.parallel.ai/v1beta/search"  # A2, D2: the call Hermes' built-in provider makes
PARALLEL_BETA = "search-extract-2025-10-10"
PARALLEL_V1_URL = "https://api.parallel.ai/v1/search"
FIRECRAWL_URL = "https://api.firecrawl.dev/v2/search"

# A0: timeout per request in seconds (httpx applies it to each phase).
EXA_TIMEOUT = 10.0
PARALLEL_TIMEOUT = 15.0
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
    if len(key) >= KEY_MIN:  # S3: a reply that echoes the key must not carry it into the result
        text = text.replace(key, "[key]")
    # A4: one line of printable characters, so a reply cannot add lines to the log
    text = " ".join("".join(c if c.isprintable() else " " for c in text[:ERROR_SCAN]).split())
    return {"error": f"{provider}: {text[:ERROR_MAX]}", "code": code, "status": status}


def _malformed(provider: str, key: str) -> dict:
    return _error(provider, "malformed reply", "malformed", key)


def _reason(body: object) -> str:
    """A4: the vendor's own reason in a JSON body, or ""."""
    if isinstance(body, dict):
        for field in ("tag", "error", "message"):
            value = body.get(field)
            if isinstance(value, dict):
                value = value.get("message")
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


def _post(
    client: httpx.Client, provider: str, url: str, key: str, timeout: float, headers: dict, body: dict
) -> tuple[dict | None, dict | None]:
    """(JSON object of a 2xx reply, None) or (None, error dict)."""
    try:
        try:
            response = client.post(url, json=body, headers=headers, timeout=timeout)
        except ValueError as exc:  # e.g. a key or query httpx cannot encode: nothing was sent, so no reply (A4)
            return None, _error(provider, type(exc).__name__, type(exc).__name__, key)
        if not 200 <= response.status_code < 300:
            status = response.status_code
            return None, _error(provider, f"HTTP {status} {_detail(response)}", f"http_{status}", key, status)
        data = response.json()
    except httpx.TimeoutException:
        return None, _error(provider, "timeout", "timeout", key)
    except (ValueError, RecursionError):  # not JSON, or nested too deeply to parse
        return None, _malformed(provider, key)
    except Exception as exc:  # transport errors
        return None, _error(provider, type(exc).__name__, type(exc).__name__, key)
    if not isinstance(data, dict):
        return None, _malformed(provider, key)
    return data, None


def _str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _rows(provider: str, key: str, items: object, text: Callable[[dict], str], text_max: int = TEXT_MAX) -> dict:
    """S4: rows in Hermes' key order, numbered from 1; an item without an http(s) URL is dropped.
    ``text`` builds the description of one item, cut to ``text_max`` characters."""
    if items is None:
        items = []
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        return _malformed(provider, key)
    hits = [item for item in items if _str(item.get("url")).lower().startswith(("http://", "https://"))]
    return {
        "rows": [
            {
                "url": item["url"],
                "title": _str(item.get("title"))[:TITLE_MAX],
                "description": text(item)[:text_max],
                "position": position,
            }
            for position, item in enumerate(hits, 1)
        ]
    }


def _joined(field: str) -> Callable[[dict], str]:
    def text(item: dict) -> str:
        parts = item.get(field)
        return " ".join(part for part in parts if isinstance(part, str)) if isinstance(parts, list) else ""

    return text


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


def firecrawl(client: httpx.Client, query: str, limit: int, key: str) -> dict:
    """A3."""
    headers = {"Authorization": f"Bearer {key}"}
    body = {"query": query, "limit": limit}
    data, error = _post(client, "Firecrawl", FIRECRAWL_URL, key, FIRECRAWL_TIMEOUT, headers, body)
    if error:
        return error
    if data.get("success") is False and (reason := _reason(data)):  # A3: a 2xx reply that reports a failure
        return _error("Firecrawl", reason, "rejected", key)
    payload = data.get("data")
    if data.get("success") is not True or not isinstance(payload, dict):
        return _malformed("Firecrawl", key)
    return _rows("Firecrawl", key, payload.get("web"), lambda item: _str(item.get("description")), FIRECRAWL_TEXT_MAX)
