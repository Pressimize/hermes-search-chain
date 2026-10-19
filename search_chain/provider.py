"""Hermes web search provider for the fallback chain (design sections 4, 5 and 8)."""

from __future__ import annotations

import hashlib
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
ORDER_SETTING = "SEARCH_CHAIN_ORDER"
PAUSES = {402: 86400, 429: 60, 432: 86400, 433: 86400}  # K5: seconds a stage is skipped after this HTTP status
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


# K1: stage name for the log and the order setting, provider name for error texts, setting that holds the key
# or the address, call, and what the setting holds ("key" or "url"). Listed in the default order.
STAGES = (
    ("exa", "Exa", "EXA_API_KEY", _exa, "key"),
    ("parallel", "Parallel", "PARALLEL_API_KEY", _parallel, "key"),
    ("brave", "Brave", "BRAVE_SEARCH_API_KEY", engines.brave, "key"),
    ("nimble", "Nimble", "NIMBLE_API_KEY", engines.nimble, "key"),
    ("tavily", "Tavily", "TAVILY_API_KEY", engines.tavily, "key"),
    ("youcom", "You.com", "YDC_API_KEY", engines.youcom, "key"),
    ("searxng", "SearXNG", "SEARXNG_URL", engines.searxng, "url"),
    ("degoog", "Degoog", "DEGOOG_URL", engines.degoog, "url"),
    ("firecrawl", "Firecrawl", "FIRECRAWL_API_KEY", engines.firecrawl, "key"),
)

_warned: set[str] = set()  # K8: warnings once per process


def _warn_once(topic: str, message: str, *args: object) -> None:
    if topic not in _warned:
        _warned.add(topic)
        log.warning(message, *args)


def stage_order(value: str) -> tuple:
    """K8: the stages named in SEARCH_CHAIN_ORDER, in that order; unknown and repeated names are dropped."""
    if not value.strip():
        return STAGES
    by_name = {stage[0]: stage for stage in STAGES}
    names = [part.strip().lower() for part in value.split(",") if part.strip()]
    chosen = tuple(by_name[name] for name in dict.fromkeys(names) if name in by_name)
    if not chosen or len(chosen) != len(names):
        order = chosen or STAGES
        _warn_once("order", "search-chain: %s has unknown or repeated names; using %s", ORDER_SETTING,
                   ",".join(stage[0] for stage in order))  # fmt: skip
    return chosen or STAGES


def _setting(name: str, holds: str) -> str:
    value = _env(name)
    return value.rstrip("/") if holds == "url" else value  # A13: one address, one pause slot


def _left(seconds: float) -> str:
    """Remaining pause for the error text: minutes rounded up below one hour, else the nearest hour."""
    return f"{math.floor(seconds / 3600 + 0.5)} h" if seconds >= 3600 else f"{math.ceil(seconds / 60)} min"


def _failed(error: str) -> dict:
    return {"success": False, "error": error}


class SearchChainProvider(WebSearchProvider):
    def __init__(
        self, transport: httpx.BaseTransport | None = None, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._transport = transport  # tests only; Hermes instantiates without arguments
        self._clock = clock
        self._paused: dict[tuple[str, str], tuple[float, str]] = {}  # K5: (stage, digest) -> (until, reason)

    @property
    def name(self) -> str:
        return NAME

    @property
    def display_name(self) -> str:
        return "Search chain"

    def is_available(self) -> bool:
        return any(_setting(setting, holds) for _, _, setting, _, holds in stage_order(_env(ORDER_SETTING)))

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
        if not isinstance(query, str) or not query.strip():  # S4: Hermes passes an empty query through unchecked
            steps.append("empty_query")
            return _failed("search-chain: empty query")
        limit = max(1, min(limit, engines.MAX_RESULTS))  # A6
        reasons: list[str] = []
        with httpx.Client(transport=self._transport) as client:
            for stage, provider, setting, call, holds in stage_order(_env(ORDER_SETTING)):
                if is_interrupted():
                    steps.append(f"{stage}=interrupted")
                    return _failed("Interrupted")
                value = _setting(setting, holds)
                if not value:  # K2; not named in the error text (K6)
                    steps.append(f"{stage}=no_url" if holds == "url" else f"{stage}=no_key")
                    continue
                slot = (stage, hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest())  # K5
                until, reason = self._paused.get(slot, (0.0, ""))
                if (left := until - self._clock()) > 0:
                    steps.append(f"{stage}=paused")
                    reasons.append(f"{reason} (paused for another {_left(left)})")
                    continue
                result = call(client, query, limit, value)
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
                    self._paused[slot] = (self._clock() + pause, result["error"])
                    detail = result["error"].partition(": ")[2]
                    log.warning("search-chain: %s paused for %d s (%s)", stage, pause, detail)  # L2
        if not reasons:
            return _failed("search-chain: no stage configured")  # K6
        return _failed("search-chain: " + "; ".join(reasons))  # K6
