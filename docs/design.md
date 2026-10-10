# Design: `search-chain`, a fallback chain for Hermes' `web_search`

Requirements carry IDs (`S`, `K`, `A`, `I`, `L`, `T`, decisions `D`). Tests and reviews refer to them.

## 1. Purpose

Hermes Agent uses exactly one provider for `web_search` (`web.search_backend`). When that provider fails, for example because its free quota is used up, Hermes does not try a second configured provider. The only built-in fallback is the *keyless rescue*: it serves the failed call from anonymous free tiers, without the configured keys.

This plugin registers its own search provider that chains three services per call:

1. **Exa**, with highlights capped at 600 characters per result.
2. **Parallel**, GA endpoint in mode `advanced`.
3. **Firecrawl**.

The next stage is asked when a stage fails, returns no hits, has no key, or is paused after a quota or rate-limit reply (K5).

**Why these three, in this order.** The choice comes from a comparison of seven providers (Exa, Parallel, Firecrawl, TinyFish, Brave, Tavily, Keenable) on 2026-10-09 and 2026-10-10, without an LLM: 80 queries (official documentation, error messages, facts, current versions, German-language and niche topics), 75 of them scored on whether the first five results contain the expected source or answer.

| | Correct, of 75 | Text per search (median) | Time per search (median) |
|---|---|---|---|
| Exa, highlights capped at 600 characters | 74 | 4,000 characters | 0.6 s |
| Exa, as Hermes calls it | 73 | 12,000 characters | 2.0 s |
| Parallel, as Hermes calls it (beta endpoint, `agentic`) | 72 | 8,200 characters | 2.9 s |
| Parallel, `/v1/search`, `advanced` | 70 | 8,400 characters | 1.8 s |
| TinyFish, Brave, Tavily, Keenable | 50 to 54 | | |

- Exa and Parallel are not distinguishable on this data: a difference of one to four queries is within the day-to-day variation of the providers.
- Firecrawl ran on 20 of the 75 scored queries (the harder ones) and got 16, against 19 for Exa and 18 for Parallel. In the first run, on the other 55, it got 53.
- The other four are clearly behind on the same queries.
- Exa comes first because the capped call returns the least text for the same hits and is the fastest. It also has the smallest free allowance, so the chain moves on to Parallel during the month.

## 2. Non-goals

- No merging or re-ranking of results from several providers, no LLM.
- No page extraction. `web.extract_backend` is untouched.
- No retries, no cache of its own (Hermes caches search results), no state on disk.
- No note for the model about which stage served a call (D6).

## 3. Environment

- Hermes Agent ≥ 0.21, written against v0.21.6. Hermes runs Python 3.14; the code supports Python ≥ 3.11, and CI tests 3.11 and 3.14.
- Uses only the standard library and `httpx`, which Hermes ships as a core dependency (`httpx==0.28.1`). No vendor SDKs (D1).

## 4. Interface to Hermes

- **S1** The plugin directory contains `plugin.yaml` and `__init__.py`.
  - `plugin.yaml` declares `name: search-chain`, `kind: backend`, `requires_hermes: ">=0.21"`, `provides_web_providers: [search-chain]` and `requires_env` with `EXA_API_KEY`, `PARALLEL_API_KEY` and `FIRECRAWL_API_KEY` (each `secret: true`).
  - `register(ctx)` calls `ctx.register_web_search_provider(...)` once.
- **S2** The provider subclasses `agent.web_search_provider.WebSearchProvider`. Its `name` is `search-chain`; `supports_search()` returns True and `supports_extract()` False. `is_available()` is true iff at least one of the three keys is set, and checks without network access.
- **S3** Keys and the setting (A1) are read only via `agent.web_search_provider.get_provider_env(...)`, so per-profile `.env` files work.
  - If reading a value raises (e.g. `UnscopedSecretError`), it counts as unset.
  - Keys never appear in logs or error texts.
- **S4** `search(query, limit=5)` is synchronous, as in every Hermes search provider. On success it returns `{"success": True, "data": {"web": [...]}}`. Each row has the keys `url`, `title`, `description`, `position`, in this order; `position` counts from 1. All rows of one call come from one stage. A result without a URL is dropped and does not count as a row.
- **S5** `search` never raises. A failure is `{"success": False, "error": "<text>"}`. An unexpected exception fails the call with `search-chain: <exception class>`.
- **S6** Interrupts, as in Hermes' built-in providers: the plugin checks `tools.interrupt.is_interrupted()` before each stage. If it is set, the chain stops without a further request, the call returns the failure `Interrupted`, and the log line shows `<stage>=interrupted`. A request in flight is not cancelled; its timeout (A0) still applies. Hermes checks the flag itself before it calls the provider, so the check matters between stages. Outside Hermes (tests) the module is not importable; then interrupts are not checked.

## 5. Chain (per call)

- **K1** The stages are asked in the fixed order Exa, Parallel, Firecrawl.
- **K2** A stage is skipped without a request when its key is unset (`no_key`) or the stage is paused (`paused`, K5).
- **K3** A stage that returns at least one row ends the chain; the call succeeds with these rows.
- **K4** Otherwise the next stage is asked. This covers an API error (HTTP status outside 200–299), a transport error, a timeout, a malformed reply, and a valid reply without rows (`empty`).
- **K5** Pauses. After certain replies a stage is skipped for a while, so that a used-up quota does not cost one failing request per search:

  | Reply | Pause | Meaning |
  |---|---|---|
  | HTTP 402 | 3,600 s | quota or budget used up |
  | HTTP 429 | 60 s | rate limit |
  | anything else | none | |

  - A pause belongs to the pair of stage and key, so profiles with different keys in one process do not pause each other, and a corrected key is used at once.
  - Pauses live in memory only. A new process starts without pauses; a wrong pause ends by itself.
  - After the pause, the stage is asked again on the next call. Nothing needs to be reset when a quota renews.
  - The reason of a paused stage repeats the reply that caused the pause and the remaining time, e.g. `Exa: HTTP 402 NO_MORE_CREDITS (paused for another 42 min)`.
  - Hermes may run several searches at once on one provider object. The pause table is a plain dict without a lock: calls already in flight when the first quota reply arrives each get their own reply and set the same pause again.
- **K6** When no stage returned rows, the call fails, and the error names the reason of every stage, e.g. `search-chain: Exa: HTTP 402 NO_MORE_CREDITS; Parallel: no API key; Firecrawl: timeout`. A valid reply without rows has the reason `no results`. This is a failure and not an empty success, because Hermes caches every success for `web.cache_ttl_minutes`; an empty list that only came about because a better stage was paused would otherwise be repeated for that time.
- **K7** Each stage is asked at most once per call. No retries.

## 6. Provider calls (direct REST)

- **A0** Every request has a timeout (httpx): Exa 10 s, Parallel 15 s, Firecrawl 15 s. Measured maxima in the comparison: 3.0 s, 4.9 s and 7.7 s. httpx bounds each phase of a request (connect, write, read, pool), not the total.
- **A1** Exa:
  - `POST https://api.exa.ai/search`, header `x-api-key`; body `{"query", "numResults": <limit>, "contents": {"highlights": {"maxCharacters": <n>}}}`.
  - `<n>` comes from the setting `SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS` in the profile's `.env`. A value of one to six decimal digits is used as the number; `0` requests Exa's default highlights (`"highlights": true`). Unset or anything else (`-5`, `5.5`, `abc`, a longer number) means 600.
  - Rows from `results[]`: `url`, `title`, and the `highlights` joined with a space as `description`.
- **A2** Parallel:
  - `POST https://api.parallel.ai/v1/search`, header `x-api-key`; body `{"objective": <query>, "search_queries": [<query>], "mode": "advanced", "advanced_settings": {"max_results": <limit, at most 20>}}`.
  - Rows from `results[]`: `url`, `title`, and the `excerpts` joined with a space as `description`.
  - The cap of 20 is the one Hermes applies to Parallel. It only cuts rows when the model asks for more than 20 results.
- **A3** Firecrawl:
  - `POST https://api.firecrawl.dev/v2/search` with `Authorization: Bearer <key>`; body `{"query", "limit"}`.
  - Success means a 2xx status and `success: true`. Rows from `data.web[]`: `url`, `title`, `description`.
- **A4** Errors:
  - A non-2xx status becomes `<Provider>: HTTP <status> <detail>`. The detail is the first of these that is present in the JSON body: `tag` (Exa, e.g. `NO_MORE_CREDITS`), `error`, `message`; otherwise the response text.
  - A transport error becomes `<Provider>: timeout` or `<Provider>: <exception class>`; a 2xx reply that is not the expected JSON becomes `<Provider>: malformed reply`.
  - Error texts are cut to 200 characters after the provider name. A key echoed in them is replaced by `[key]` (S3).
  - Each outcome has a short code for the log (L1).
- **A5** One `httpx.Client` per `search` call, closed afterwards. It honours `HTTP(S)_PROXY`/`NO_PROXY`. A transport can be injected for tests.
- **A6** `limit` is passed on as Hermes gives it (Hermes asks for 10 results when the model wants up to 10). Rows are returned as the provider sends them; Hermes cuts the list to the model's limit.

## 7. Installation and configuration

- **I1** Install the directory `search_chain/` as the plugin `search-chain`, either:
  - by copying it to `$HERMES_HOME/plugins/search-chain/` and adding `search-chain` to `plugins.enabled`, or
  - with `hermes plugins install <owner>/hermes-search-chain#search_chain --enable`.

  The keys go into the profile's `.env`.
- **I2** Configuration:
  - `web.search_backend: search-chain`.
  - `web.keyless_rescue: false`. Otherwise, when all stages fail, Hermes serves the call from anonymous free tiers without saying so in the log line of this plugin.
- **I3** The plugin directory contains no `pyproject.toml` and no dependencies. It is therefore not a member of Hermes' package manager and needs no environment changes.
- **I4** Egress: the host must reach `api.exa.ai`, `api.parallel.ai` and `api.firecrawl.dev` (HTTPS), directly or through the configured proxy.

## 8. Logging

- **L1** Logger `logging.getLogger(__name__)`. For each call, one INFO line: `search-chain: exa=<outcome> [parallel=<outcome>] [firecrawl=<outcome>]`.
  - Outcomes: `ok`, `empty`, `no_key`, `paused`, `interrupted`, `http_<status>`, `timeout`, `malformed`, or an exception class name.
  - Each stage up to the one that ended the chain is listed. No query text, no keys.
  - If the call fails before the first stage (S5), the line is `search-chain: no stage ran`, after a WARNING `search-chain: call failed: <exception class>`.
- **L2** When a pause starts, one WARNING line: `search-chain: <stage> paused for <seconds> s (HTTP <status> <detail>)`.
- Hermes writes INFO to `logs/agent.log` and WARNING also to `logs/errors.log` in the Hermes home.

## 9. Tests and acceptance

- **T1** Unit tests (pytest, no network, `httpx.MockTransport`):
  - every branch of K2–K6, with missing keys and pauses, including all stages paused or without key; at most one request per stage (K7);
  - pauses per status, their end (injected clock), and per key (K5);
  - requests and row mapping of A1–A3, the values of the setting of A1, the cap of A2; error texts, codes and key masking (A4); the proxy variables (A5);
  - result shape and key order (S4); no exception escapes (S5); interrupts (S6);
  - `register(ctx)` and `plugin.yaml` (S1); properties and `is_available` (S2); keys absent from results and logs (S3); log lines (L1, L2).
- **T2** Live check through Hermes' real `web_search` path, without an LLM, in a profile with the three keys:
  - a few queries served by Exa;
  - the same with the Exa key replaced by an invalid one in the process (HTTP 401): Parallel serves;
  - the same with the Exa and Parallel keys replaced: Firecrawl serves;
  - at most 8 requests/min per provider;
  - the script refuses to run unless the profile selects `search-chain` and has `web.keyless_rescue: false`.
  - A used-up quota (HTTP 402) is not forced in the live check; it is observed in the log during use.
- **T3** A review checks the result against this document.
- **T4** `ruff check` and `ruff format --check` are clean; CI (GitHub Actions: ruff, pytest on Python 3.11 and 3.14) is green.

## 10. Known limitations

- The chain reacts to quota replies; it does not know the remaining quota in advance.
- Whether a provider answers HTTP 402 or bills a stored payment method when the free quota is used up depends on the account settings (auto recharge, budgets). For a hard cost cap, keep auto recharge off.
- Parallel does not document its replies for a used-up quota. The chain moves on after any failure, so only the length of the pause depends on the status code.
- After a restart the first call asks every stage again, including one with a used-up quota.
- A search that finds nothing at any stage is reported as a failure with `no results` (K6).
- Results of different stages differ in length: Exa capped about 4,000 characters per search, Parallel about 8,400, Firecrawl about 3,900 (medians for 5 results).
- Hermes caches successful results for `web.cache_ttl_minutes` (default 20).
- Every query is sent to Exa, and possibly to Parallel and Firecrawl (privacy).
- Providers and their order are fixed.

## 11. Decisions

| ID | Decision | Reason |
|---|---|---|
| D1 | Direct REST calls, not Hermes' built-in providers | The built-in Exa, Parallel and Firecrawl providers need vendor SDKs that Hermes installs on first use; in container deployments that runtime install can disturb the image's package set. Direct calls give exact status codes for K5 and reach Exa's highlight cap, which the built-in provider does not expose. |
| D2 | Parallel via `/v1/search` in mode `advanced`, not the beta endpoint Hermes 0.21.6 calls | Parallel's documentation reserves the beta endpoint for existing integrations. In the comparison `advanced` showed no detectable difference to the beta call (70 against 72 of 75) and was faster. Mode `fast` on `/v1/search` was clearly worse (49 of 75) and is not used. |
| D3 | Exa highlights capped at 600 characters, adjustable by one setting | No detectable loss (74 against 73 of 75) at one third of the text; same price. The comparison ran without an LLM, so an effect on answer quality is not measured; the setting allows switching the cap off. |
| D4 | Pauses in memory, fixed lengths, only for HTTP 402 and 429 | No files, no calendar logic, self-healing. A pause that is too long costs at most an hour of the stage; one that is too short costs one failing request. A rejected key (401, 403) is a configuration error that should stay visible in every log line. |
| D5 | A reply without rows moves on to the next stage; no rows at all is a failure with the reason `no results` | Cheap and rare (no empty reply in 1,540 searches of the comparison); another index may have hits. A failure is not cached by Hermes (K6). |
| D6 | No note for the model about the serving stage | All three are live web searches; the model does not need to treat the results differently. The log line shows the stage. |
| D7 | Synchronous `httpx.Client` | Hermes calls `search` synchronously. |
| D8 | Constants instead of configuration, except the highlight cap | As little code as needed; changes come with releases. |
| D9 | MIT license | Same as Hermes Agent. |
