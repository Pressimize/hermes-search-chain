# Changelog

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
