"""Hermes plugin: web_search fallback chain over up to nine search services (Exa, Parallel, Brave, Nimble, Tavily,
You.com, SearXNG, Degoog, Firecrawl)."""


def register(ctx) -> None:
    # Imported here so engines.py stays usable without Hermes (tests).
    from .provider import SearchChainProvider

    ctx.register_web_search_provider(SearchChainProvider())
