# Changelog

## Unreleased

- Documentation: the provider tables in the README, `docs/design.md` and `docs/evaluation.md` now show Firecrawl (65 of 75, put together from run 1 and the extra queries of run 2). The text gives its run 1 score from the result list (49 of 55) next to the one with result pages (53 of 55) and no longer calls it "slightly behind". `scripts/recompute.py` prints the result-list totals of run 1. No change to the plugin.
- Metadata: Claude is named as an author next to Pressimize (README, `plugin.yaml`, `pyproject.toml`).

## 0.1.0 – 2026-10-10

- First version: `search-chain` provider for `web_search` with the chain Exa → Parallel → Firecrawl.
- Moves on when a service fails, returns no results or has no key; pauses a service for 24 hours after HTTP 402 and for a minute after HTTP 429.
- Exa highlights capped at 600 characters (`SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS`).
- Parallel on the beta endpoint in mode `agentic`, as Hermes calls it; `/v1/search` selectable with `SEARCH_CHAIN_PARALLEL_API=v1`.
