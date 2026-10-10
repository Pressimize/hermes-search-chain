"""Hermes web search provider for the fallback chain (design sections 4, 5 and 8)."""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from typing import Any

import httpx
from agent.web_search_provider import WebSearchProvider, get_provider_env

from . import engines

NAME = "search-chain"
HIGHLIGHT_SETTING = "SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS"
PARALLEL_SETTING = "SEARCH_CHAIN_PARALLEL_API"
PAUSES = {402: 86400, 429: 60}  # K5: seconds a stage is skipped after this HTTP status
log = logging.getLogger(__name__)

# S6: same convention as Hermes' built-in providers for /stop and new user messages.
try:
    from tools.interrupt import is_interrupted
except ImportError:  # outside Hermes (tests)

    def is_interrupted() -> bool:
        return False


def _env(name: str) -> str:
    try:
        return get_provider_env(name)
    except Exception:  # S3: e.g. UnscopedSecretError counts as unset
        return ""


def _exa(client: httpx.Client, query: str, limit: int, key: str) -> dict:
    value = _env(HIGHLIGHT_SETTING)  # A1
    valid = value.isascii() and value.isdecimal() and len(value) <= 6
    chars = int(value) if valid else engines.EXA_HIGHLIGHT_CHARS
    return engines.exa(client, query, limit, key, chars)


def _parallel(client: httpx.Client, query: str, limit: int, key: str) -> dict:
    return engines.parallel(client, query, limit, key, v1=_env(PARALLEL_SETTING).lower() == "v1")  # A2


# K1: stage name for the log, provider name for error texts, key variable, call.
STAGES = (
    ("exa", "Exa", "EXA_API_KEY", _exa),
    ("parallel", "Parallel", "PARALLEL_API_KEY", _parallel),
    ("firecrawl", "Firecrawl", "FIRECRAWL_API_KEY", engines.firecrawl),
)


def _left(seconds: float) -> str:
    """Remaining pause for the error text, rounded up."""
    return f"{math.ceil(seconds / 3600)} h" if seconds > 3600 else f"{math.ceil(seconds / 60)} min"


def _failed(error: str) -> dict:
    return {"success": False, "error": error}


class SearchChainProvider(WebSearchProvider):
    def __init__(
        self, transport: httpx.BaseTransport | None = None, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._transport = transport  # tests only; Hermes instantiates without arguments
        self._clock = clock
        self._paused: dict[tuple[str, str], tuple[float, str]] = {}  # K5: (stage, key) -> (until, reason)

    @property
    def name(self) -> str:
        return NAME

    @property
    def display_name(self) -> str:
        return "Search chain (Exa, Parallel, Firecrawl)"

    def is_available(self) -> bool:
        return any(_env(key_name) for _, _, key_name, _ in STAGES)

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return False

    def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        steps: list[str] = []
        try:
            return self._chain(query, limit, steps)
        except Exception as exc:  # S5: e.g. httpx.Client rejecting a malformed proxy variable
            log.warning("search-chain: call failed: %s", type(exc).__name__)
            return _failed(f"search-chain: {type(exc).__name__}")
        finally:
            log.info("search-chain: %s", " ".join(steps) or "no stage ran")  # L1

    def _chain(self, query: str, limit: int, steps: list[str]) -> dict[str, Any]:
        reasons: list[str] = []
        with httpx.Client(transport=self._transport) as client:
            for stage, provider, key_name, call in STAGES:
                if is_interrupted():
                    steps.append(f"{stage}=interrupted")
                    return _failed("Interrupted")
                key = _env(key_name)
                if not key:
                    steps.append(f"{stage}=no_key")
                    reasons.append(f"{provider}: no API key")
                    continue
                until, reason = self._paused.get((stage, key), (0.0, ""))
                if (left := until - self._clock()) > 0:
                    steps.append(f"{stage}=paused")
                    reasons.append(f"{reason} (paused for another {_left(left)})")
                    continue
                result = call(client, query, limit, key)
                if result.get("rows"):  # K3
                    steps.append(f"{stage}=ok")
                    return {"success": True, "data": {"web": result["rows"]}}
                if "rows" in result:
                    steps.append(f"{stage}=empty")
                    reasons.append(f"{provider}: no results")
                    continue
                steps.append(f"{stage}={result['code']}")
                reasons.append(result["error"])
                if pause := PAUSES.get(result["status"]):
                    self._paused[(stage, key)] = (self._clock() + pause, result["error"])
                    detail = result["error"].partition(": ")[2]
                    log.warning("search-chain: %s paused for %d s (%s)", stage, pause, detail)  # L2
        return _failed("search-chain: " + "; ".join(reasons))  # K6
