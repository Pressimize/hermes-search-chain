"""REST calls to Exa, Parallel and Firecrawl search (design section 6).

Every function returns a dict and never raises: ``{"rows": [...]}`` for a valid reply (possibly without rows),
else ``{"error": "<Provider>: <detail>", "code": "<short code>", "status": <HTTP status or None>}``.
"""

from __future__ import annotations

import httpx

EXA_URL = "https://api.exa.ai/search"
PARALLEL_URL = "https://api.parallel.ai/v1/search"
FIRECRAWL_URL = "https://api.firecrawl.dev/v2/search"

# A0: timeout per request in seconds (httpx applies it to each phase).
EXA_TIMEOUT = 10.0
PARALLEL_TIMEOUT = 15.0
FIRECRAWL_TIMEOUT = 15.0
ERROR_MAX = 200  # A4
EXA_HIGHLIGHT_CHARS = 600  # A1, D3
PARALLEL_MAX_RESULTS = 20  # A2


def _error(provider: str, detail: object, code: str, key: str, status: int | None = None) -> dict:
    text = str(detail).strip()
    if key:  # S3: a reply that echoes the key must not carry it into the result
        text = text.replace(key, "[key]")
    return {"error": f"{provider}: {text[:ERROR_MAX]}", "code": code, "status": status}


def _malformed(provider: str, key: str) -> dict:
    return _error(provider, "malformed reply", "malformed", key)


def _detail(response: httpx.Response) -> str:
    """A4: the vendor's own reason for a non-2xx reply."""
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        for field in ("tag", "error", "message"):
            value = body.get(field)
            if isinstance(value, dict):
                value = value.get("message")
            if value:
                return str(value)
    return response.text.strip()


def _post(
    client: httpx.Client, provider: str, url: str, key: str, timeout: float, headers: dict, body: dict
) -> tuple[dict | None, dict | None]:
    """(JSON object of a 2xx reply, None) or (None, error dict)."""
    try:
        response = client.post(url, json=body, headers=headers, timeout=timeout)
        if not 200 <= response.status_code < 300:
            status = response.status_code
            return None, _error(provider, f"HTTP {status} {_detail(response)}", f"http_{status}", key, status)
        data = response.json()
    except httpx.TimeoutException:
        return None, _error(provider, "timeout", "timeout", key)
    except ValueError:
        return None, _malformed(provider, key)
    except Exception as exc:  # transport errors
        return None, _error(provider, type(exc).__name__, type(exc).__name__, key)
    if not isinstance(data, dict):
        return None, _malformed(provider, key)
    return data, None


def _rows(provider: str, key: str, items: object, text) -> dict:
    """S4: rows in Hermes' key order, numbered from 1; items without a URL are dropped.
    ``text`` builds the description of one item."""
    if items is None:
        items = []
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        return _malformed(provider, key)
    hits = [item for item in items if item.get("url")]
    return {
        "rows": [
            {
                "url": str(item["url"]),
                "title": str(item.get("title") or ""),
                "description": text(item),
                "position": position,
            }
            for position, item in enumerate(hits, 1)
        ]
    }


def _joined(field: str):
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


def parallel(client: httpx.Client, query: str, limit: int, key: str) -> dict:
    """A2: GA endpoint, mode ``advanced`` (D2)."""
    body = {
        "objective": query,
        "search_queries": [query],
        "mode": "advanced",
        "advanced_settings": {"max_results": min(limit, PARALLEL_MAX_RESULTS)},
    }
    data, error = _post(client, "Parallel", PARALLEL_URL, key, PARALLEL_TIMEOUT, {"x-api-key": key}, body)
    return error or _rows("Parallel", key, data.get("results"), _joined("excerpts"))


def firecrawl(client: httpx.Client, query: str, limit: int, key: str) -> dict:
    """A3."""
    headers = {"Authorization": f"Bearer {key}"}
    body = {"query": query, "limit": limit}
    data, error = _post(client, "Firecrawl", FIRECRAWL_URL, key, FIRECRAWL_TIMEOUT, headers, body)
    if error:
        return error
    payload = data.get("data")
    if data.get("success") is not True or not isinstance(payload, dict):
        return _malformed("Firecrawl", key)
    return _rows("Firecrawl", key, payload.get("web"), lambda item: str(item.get("description") or ""))
