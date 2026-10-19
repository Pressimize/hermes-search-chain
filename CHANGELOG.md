# Changelog

## 0.2.0 – 2026-10-19

Six more stages and a setting for the order. Exa, Parallel and Firecrawl are called as before. Why this order: design D17 and [docs/evaluation.md](docs/evaluation.md), *Benchmark v2*.

- The default chain is now Exa → Parallel → Brave → Nimble → Tavily → You.com → SearXNG → Degoog → Firecrawl. Brave, Nimble, Tavily and You.com need a key (`BRAVE_SEARCH_API_KEY`, `NIMBLE_API_KEY`, `TAVILY_API_KEY`, `YDC_API_KEY`), SearXNG and Degoog the address of your own instance (`SEARXNG_URL`, `DEGOOG_URL`). A stage without a key or address is skipped, so an existing setup behaves as before unless it already has one of these keys or addresses (next point).
- A key that is already set switches its stage on: the names follow Hermes' built-in providers where there is one. This includes a `TAVILY_API_KEY` that was set only for hermes-extract-chain; Tavily search then spends those credits.
- New setting `SEARCH_CHAIN_ORDER`: comma-separated stage names that pick the stages and their order. A stage left out is never asked, even with a key. Unknown and repeated names are dropped with one warning. If the order names no stage with a key or address, a search fails with `search-chain: no stage configured`.
- The error text names only the stages that were asked or are paused. Before, a stage without a key was named, too (`no API key`); the log line still lists every stage. The log line has the stage names in the order used.
- Tavily's HTTP 432 and 433 (plan limit, pay-as-you-go limit) pause the stage for 24 hours, like a 402.
- Error reasons are also read from `detail` and from lists in the reply body, which the new services use. In rare shapes the reason of an Exa, Parallel or Firecrawl error can therefore read differently than before.
- Addresses of self-hosted stages are checked (`http` or `https`, a host, no `?` or `#`); a bad one fails the stage with `invalid URL setting` and no request. Redirects are not followed. The address is never written to error texts or the log.
- The display name is "Search chain" without a list of services.
- `plugin.yaml` lists the new keys, addresses and `SEARCH_CHAIN_ORDER` as `optional_env`.
- Developer script: `scripts/live_check.py --break` accepts all nine stages; for SearXNG and Degoog it replaces the address with one where nothing listens.
- Documentation: README with the new stages, prices and settings; evaluation with the benchmark of 2026-10-18/19; design decisions D17 to D21.

## 0.1.2 – 2026-10-17

Fixes from a review by seven models and from a mutation run, and alignment with hermes-extract-chain. The order of the chain, the pauses and the settings are unchanged.

- A request that cannot be built, e.g. because the key contains an invisible Unicode character, fails its stage as `<Provider>: UnicodeEncodeError`. Before, it was reported as `malformed reply`, although nothing had been sent.
- A Firecrawl reply with a 2xx status and `success: false` keeps its reason: `Firecrawl: <reason>` (log code `rejected`) instead of `Firecrawl: malformed reply`.
- Aligned with hermes-extract-chain: a key echoed in an error text is also masked when percent-encoded or in another case.
- `plugin.yaml` lists the two settings `SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS` and `SEARCH_CHAIN_PARALLEL_API` as `optional_env`.
- Developer script: `scripts/live_check.py` shows the log line of a call that ran no stage instead of reporting it as served from Hermes' cache.

## 0.1.1 – 2026-10-11

Hardening after three external code reviews of 0.1.0. The order of the chain, the lengths of the pauses and the settings are unchanged.

- Every service is asked for at most 20 results, and at least 1. Hermes lets the model ask for up to 100, and Exa bills each result above 10 extra. Before, the number went to Exa and Firecrawl unchanged.
- A result counts only with a URL that is text and starts with `http://` or `https://`. Before, any non-empty value became a row, also `javascript:…` or a value that was not text.
- A title is cut at 300 characters and a description at 16,000, from Firecrawl at 3,000; a title or description that is not text becomes empty. Before, there was no bound.
- A search with an empty or non-text query fails at once (`search-chain: empty query`, log line `search-chain: empty_query`). Before, it was sent to all three services.
- Error texts are one line of printable characters. Before, a line break in a provider's reply added a line to the log.
- A key is masked in error texts only if it has 8 or more characters. Before, a one-character value garbled every error text.
- An error reply whose JSON is nested too deeply to parse keeps its HTTP status, so the pause after 402 or 429 still starts. Before, it was reported as a `RecursionError` without a status. A 2xx reply like that is `malformed`.
- The pause table is keyed by a digest of the API key, so the table holds no key.
- The remaining pause in an error text is the nearest hour from one hour on. Before, 61 minutes read "2 h" and one hour "60 min".
- README: the install command can be repeated, and the update note warns against copying onto an existing directory. The limitations name the timeouts as they are, the bound of 20 results, and that result texts are third-party content.
- `scripts/live_check.py` rejects an unknown `--break` stage and a negative `--pace`, and stops with a message instead of an assertion. It no longer sets `sys._hermes_pin_default_home`, which has no effect once `HERMES_HOME` is set. CI runs `scripts/recompute.py`.
- Design: decisions D12–D16 record the text bounds and the proposals of the reviews that were not adopted, with their reasons.
- Documentation: the provider tables in the README, `docs/design.md` and `docs/evaluation.md` now show Firecrawl (65 of 75, put together from run 1 and the extra queries of run 2). The text gives its run 1 score from the result list (49 of 55) next to the one with result pages (53 of 55) and no longer calls it "slightly behind". `scripts/recompute.py` prints the result-list totals of run 1.
- Metadata: Claude is named as an author next to Pressimize (README, `plugin.yaml`, `pyproject.toml`).

## 0.1.0 – 2026-10-10

- First version: `search-chain` provider for `web_search` with the chain Exa → Parallel → Firecrawl.
- Moves on when a service fails, returns no results or has no key; pauses a service for 24 hours after HTTP 402 and for a minute after HTTP 429.
- Exa highlights capped at 600 characters (`SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS`).
- Parallel on the beta endpoint in mode `agentic`, as Hermes calls it; `/v1/search` selectable with `SEARCH_CHAIN_PARALLEL_API=v1`.
