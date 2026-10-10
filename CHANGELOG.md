# Changelog

## 0.1.0 – 2026-10-10

- First version: `search-chain` provider for `web_search` with the chain Exa → Parallel → Firecrawl.
- Moves on when a service fails, returns no results or has no key; pauses a service for 24 hours after HTTP 402 and for a minute after HTTP 429.
- Exa highlights capped at 600 characters (`SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS`).
