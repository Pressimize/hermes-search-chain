"""Hermes plugin: web_search fallback chain Exa -> Parallel -> Firecrawl."""


def register(ctx) -> None:
    # Imported here so engines.py stays usable without Hermes (tests).
    from .provider import SearchChainProvider

    ctx.register_web_search_provider(SearchChainProvider())
