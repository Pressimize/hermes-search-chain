# Design: `search-chain`, a fallback chain for Hermes' `web_search`

Requirements carry IDs (`S`, `K`, `A`, `I`, `L`, `T`, decisions `D`). Tests and reviews refer to them.

## 1. Purpose

Hermes Agent uses exactly one provider for `web_search` (`web.search_backend`). When that provider fails, for example because its free quota is used up, Hermes does not try a second configured provider. The only built-in fallback is the *keyless rescue*: it serves the failed call from anonymous free tiers, without the configured keys.

This plugin registers its own search provider that chains up to nine services per call, by default in this order:

1. **Exa**, with highlights capped at 600 characters per result.
2. **Parallel**, called as Hermes' built-in provider calls it (beta endpoint, mode `agentic`).
3. **Brave Search**.
4. **Nimble**.
5. **Tavily**.
6. **You.com**.
7. **SearXNG**, a self-hosted instance.
8. **Degoog**, a self-hosted instance.
9. **Firecrawl**.

The next stage is asked when a stage fails, returns no hits, has no key or address, or is paused after a quota or rate-limit reply (K5). A setting picks and orders the stages (K8).

**Why these, in this order:** D17; the full account is in [evaluation.md](evaluation.md).

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
  - `plugin.yaml` declares `name: search-chain`, `kind: backend`, `requires_hermes: ">=0.21"`, `provides_web_providers: [search-chain]` and `requires_env` with `EXA_API_KEY`, `PARALLEL_API_KEY` and `FIRECRAWL_API_KEY` (each `secret: true`). `optional_env` lists the keys of Brave, Nimble, Tavily and You.com and the addresses of SearXNG and Degoog (each `secret: true`, since an address may hold credentials), then `SEARCH_CHAIN_ORDER` (K8) and the settings of A1 and A2.
  - Hermes 0.21.6 asks for every unset `requires_env` entry when the plugin is installed with its CLI; the answer can be skipped. It reads `optional_env` only for messaging plugins, so for this plugin those entries only document the settings, which work from the profile's `.env` either way. Keeping the six new stages there spares six more questions at install time.
  - `register(ctx)` calls `ctx.register_web_search_provider(...)` once.
- **S2** The provider subclasses `agent.web_search_provider.WebSearchProvider`. Its `name` is `search-chain`; `supports_search()` returns True and `supports_extract()` False. `is_available()` is true iff at least one stage of the order (K8) has its key or address, and checks without network access.
- **S3** Keys, addresses and the settings (A1, A2, K8) are read only via `agent.web_search_provider.get_provider_env(...)`, so per-profile `.env` files work.
  - If reading a value raises (e.g. `UnscopedSecretError`), it counts as unset.
  - A key of 8 or more characters that a reply echoes never appears in error texts or logs. A shorter value is not masked (A4). The pause table holds only a SHA-256 digest of the key (K5).
- **S4** `search(query, limit=5)` is synchronous, as in every Hermes search provider. On success it returns `{"success": True, "data": {"web": [...]}}`. Each row has the keys `url`, `title`, `description`, `position`, in this order; `position` counts from 1. All rows of one call come from one stage.
  - A result counts as a row only if its `url` is a string that starts with `http://` or `https://`, in any letter case; anything else is dropped, and the URL is passed on as sent. Hermes refuses other schemes and private addresses when it fetches a URL; the plugin does not repeat that check.
  - `title` and `description` are text; a value of another type becomes empty. A title is cut at 300 characters and a description at 16,000, from Firecrawl at 3,000, without a marker (D12).
  - A query that is not text, or is empty or only whitespace, fails at once with `search-chain: empty query`; no stage is asked. Hermes passes such a query on unchecked.
- **S5** `search` never raises. A failure is `{"success": False, "error": "<text>"}`. An unexpected exception fails the call with `search-chain: <exception class>`.
- **S6** Interrupts, as in Hermes' built-in providers: the plugin checks `tools.interrupt.is_interrupted()` before each stage. If it is set, the chain stops without a further request, the call returns the failure `Interrupted`, and the log line shows `<stage>=interrupted`. A request in flight is not cancelled; its timeout (A0) still applies. Hermes checks the flag itself before it calls the provider, so the check matters between stages. Outside Hermes (tests) the module is not importable; then interrupts are not checked.

## 5. Chain (per call)

- **K1** The stages are asked in the order of K8; by default Exa, Parallel, Brave, Nimble, Tavily, You.com, SearXNG, Degoog, Firecrawl (stage names `exa`, `parallel`, `brave`, `nimble`, `tavily`, `youcom`, `searxng`, `degoog`, `firecrawl`).
- **K2** A stage is skipped without a request when its key is unset (`no_key`), its address is unset (`no_url`), or the stage is paused (`paused`, K5). An address of only slashes counts as unset.
- **K3** A stage that returns at least one row ends the chain; the call succeeds with these rows.
- **K4** Otherwise the next stage is asked. This covers an API error (HTTP status outside 200–299), a transport error, a timeout, a malformed reply, and a valid reply without rows (`empty`), which includes a reply whose results were all dropped (S4).
- **K5** Pauses. After certain replies a stage is skipped for a while, so that a used-up quota does not cost one failing request per search:

  | Reply | Pause | Meaning |
  |---|---|---|
  | HTTP 402 | 86,400 s (24 h) | quota or budget used up |
  | HTTP 432, 433 | 86,400 s (24 h) | Tavily: plan limit, pay-as-you-go limit |
  | HTTP 429 | 60 s | rate limit |
  | anything else | none | |

  - A pause belongs to the pair of stage and key, so profiles with different keys in one process do not pause each other, and a corrected key is used at once. For SearXNG and Degoog the address takes the place of the key, after trailing slashes are cut, so `http://host/` and `http://host` share a pause. The table is keyed by a SHA-256 digest of the key or address and holds neither.
  - Pauses live in memory only. A new process starts without pauses; a wrong pause ends by itself.
  - After the pause, the stage is asked again on the next call. Nothing needs to be reset when a quota renews.
  - The reason of a paused stage repeats the reply that caused the pause and the remaining time, e.g. `Exa: HTTP 402 NO_MORE_CREDITS (paused for another 17 h)`; below one hour it is given in minutes, rounded up, from one hour on as the nearest hour.
  - Hermes may run several searches at once on one provider object. The pause table is a plain dict without a lock: calls already in flight when the first quota reply arrives each get their own reply and set the same pause again.
- **K6** When no stage returned rows, the call fails, and the error names the reason of every stage that was asked or is paused, e.g. `search-chain: Exa: HTTP 402 NO_MORE_CREDITS; Parallel: timeout; Firecrawl: no results`. A valid reply without rows has the reason `no results`. Stages without a key or address are not named (D19); the log line shows them. If no stage of the order has a key or address, the error is `search-chain: no stage configured`. This is a failure and not an empty success, because Hermes caches every success for `web.cache_ttl_minutes`; an empty list that only came about because a better stage was paused would otherwise be repeated for that time.
- **K7** Each stage is asked at most once per call. No retries.
- **K8** Order setting `SEARCH_CHAIN_ORDER`, read on every call (D15), as `EXTRACT_CHAIN_ORDER` in hermes-extract-chain:
  - Comma-separated stage names (K1); entries are trimmed and lowercased; empty entries are dropped silently.
  - Only the stages named are asked, in that order. A stage left out is never asked, even with a key, and is not named in the log line or the error.
  - Unknown and repeated names are dropped. A value with unknown or repeated names gives one WARNING per process (not per profile) that names the order used, e.g. `search-chain: SEARCH_CHAIN_ORDER has unknown or repeated names; using exa,parallel`.
  - Unset or blank: the default order. If no valid name is left (e.g. `bing` or `,`): the default order, with the warning. A valid order whose stages have no key or address does not fall back to the default, so a stage the user left out is never asked.

## 6. Provider calls (direct REST)

- **A0** Every request has a timeout (httpx): Exa 10 s, Parallel 15 s, Brave 10 s, Nimble 15 s, Tavily 15 s, You.com 10 s, SearXNG 15 s, Degoog 10 s, Firecrawl 15 s. For the stages added in 0.2.0, the slowest of 177 searches in the benchmark of 2026-10-18/19 took 1.5 s (Brave), 8.7 s (Nimble), 5.5 s (Tavily), 1.2 s (You.com), 6.0 s (SearXNG) and 2.1 s (Degoog). Slowest searches measured: Exa 6.4 s (the capped call inside the plugin in the end-to-end test; the uncapped call through Hermes was as slow in both comparison runs), Parallel's beta call 6.4 s (run 1, through Hermes), Firecrawl 7.7 s (run 2, through Hermes). httpx bounds each phase of a request (connect, write, read, pool), not the total: a request that is slow in several phases takes longer than its timeout, and a reply that arrives in a trickle is not bounded at all. Hermes 0.21.6 ends a tool call after 420 s by default (D13).
- **A1** Exa:
  - `POST https://api.exa.ai/search`, header `x-api-key`; body `{"query", "numResults": <limit, at most 20>, "contents": {"highlights": {"maxCharacters": <n>}}}`.
  - `<n>` comes from the setting `SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS` in the profile's `.env`. A value of one to six decimal digits is used as the number; `0`, also written with several zeros, requests Exa's default highlights (`"highlights": true`). Unset or anything else (`-5`, `5.5`, `abc`, a longer number) means 600.
  - Rows from `results[]`: `url`, `title`, and the `highlights` joined with a space as `description`.
- **A2** Parallel:
  - Default, the call of Hermes 0.21.6 (D2): `POST https://api.parallel.ai/v1beta/search`, headers `x-api-key` and `parallel-beta: search-extract-2025-10-10`; body `{"search_queries": [<query>], "objective": <query>, "mode": "agentic", "max_results": <limit, at most 20>}`.
  - With the setting `SEARCH_CHAIN_PARALLEL_API=v1` in the profile's `.env` (case-insensitive; anything else means the default): `POST https://api.parallel.ai/v1/search`, header `x-api-key`; body `{"objective": <query>, "search_queries": [<query>], "mode": "advanced", "advanced_settings": {"max_results": <limit, at most 20>}}`.
  - Rows from `results[]`: `url`, `title`, and the `excerpts` joined with a space as `description`.
  - The cap of 20 holds for every stage (A6).
- **A3** Firecrawl:
  - `POST https://api.firecrawl.dev/v2/search` with `Authorization: Bearer <key>`; body `{"query", "limit": <limit, at most 20>}`.
  - Success means a 2xx status and `success: true`. Rows from `data.web[]`: `url`, `title`, `description`, the latter cut at 3,000 characters (D12).
  - A 2xx reply with `success: false` and a reason (found as in A4) becomes `Firecrawl: <reason>` with code `rejected`. It starts no pause, because K5 goes by the HTTP status. Without a reason it is a malformed reply.
- **A4** Errors:
  - A non-2xx status becomes `<Provider>: HTTP <status> <detail>`. The detail is the first of these that is present in the JSON body: `tag` (Exa, e.g. `NO_MORE_CREDITS`), `error`, `message`, `detail`. A dict value contributes its `message`, else its `detail`, else its `error` (Brave `{"error": {"detail": ...}}`, Tavily `{"detail": {"error": ...}}`); a list contributes its first element, or that element's `msg` (Tavily's validation errors). Otherwise the response text. A body that cannot be parsed counts as no JSON; the status still decides about a pause (K5).
  - A transport error becomes `<Provider>: timeout` or `<Provider>: <exception class>`, never the text of the exception (it may hold an address, A13); a 2xx reply that is not the expected JSON becomes `<Provider>: malformed reply`. A 2xx reply without a result list (`results`, Brave's `web` or `web.results`, You.com's `results.web`, Firecrawl's `data.web`) is a valid reply without hits (`no results`); at You.com, `results` itself must be an object (A10). A request that httpx cannot build, such as one with a key or query it cannot encode, sends nothing and also becomes `<Provider>: <exception class>` (e.g. `UnicodeEncodeError`), not `malformed reply`. A reply that httpx cannot decode, such as a broken compressed body, is a transport error whatever its status.
  - Error texts are one line: line breaks and other control characters become spaces, and runs of spaces become one space, so a reply cannot add lines to the log. Only the first 2,000 characters of a reply are looked at, and the text is cut to 200 characters after the provider name.
  - A key echoed in an error text is replaced by `[key]` if it has 8 or more characters (S3), as sent or percent-encoded and in any case, as in extract-chain.
  - Each outcome has a short code for the log (L1).
- **A7** Brave: `GET https://api.search.brave.com/res/v1/web/search`, headers `X-Subscription-Token` and `Accept: application/json`, parameters `q` and `count` = limit, as Hermes' built-in `brave_free` calls it. Rows from `web.results[]`: `url`, `title`, `description`. Brave marks query words with `<strong>`; the tags `<strong>` and `</strong>`, in any letter case, are removed from title and description before they are cut (S4). Other markup and HTML entities stay. A reply without `web` has no hits; a `web` that is not an object is malformed.
- **A8** Nimble: `POST https://sdk.nimbleway.com/v2/search`, `Authorization: Bearer <key>`; body `{"query", "search_depth": "lite", "focus": "general", "full_content": false, "max_results": <limit>}`. Rows from `results[]`: `url`, `title`, `description`.
- **A9** Tavily: `POST https://api.tavily.com/search`, `Authorization: Bearer <key>`; body `{"query", "search_depth": "basic", "max_results": <limit>, "include_answer": false}`. Rows from `results[]`: `url`, `title`, and `content` as description.
- **A10** You.com: `POST https://ydc-index.io/v1/search`, header `X-API-Key`; body `{"query", "count": <limit>}`. `results` must be an object; rows from `results.web[]`: `url`, `title`, and `description` followed by the `snippets`, joined with a space. `count` applies per section (web, news), so the rows are cut to the limit.
- **A11** SearXNG: `GET <address>/search`, parameters `q` and `format=json`, no headers of its own. Rows from `results[]`: `url`, `title`, and `content` as description, in the order the instance sends them, cut to the limit. The instance must allow the JSON format (`search.formats` in its settings; otherwise HTTP 403), and its limiter must be off or let the Hermes host pass (otherwise HTTP 429).
- **A12** Degoog: `GET <address>/api/search`, parameter `q`. Rows from `results[]`: `url`, `title`, and `snippet` as description, in the order sent, cut to the limit. Degoog's API key and rate limiter are off by default; when on, it answers 401 or 429 (the plugin sends no Degoog key, D20).
- **A13** Addresses of self-hosted stages (`SEARXNG_URL`, `DEGOOG_URL`):
  - Trailing slashes are cut; a path stays (`https://host/searx` becomes `https://host/searx/search`).
  - Valid only with the scheme `http` or `https` (any letter case), a host, a port from 0 to 65535 if one is given, and no `?`, `#`, whitespace or control character. Otherwise the stage fails with `<Provider>: invalid URL setting` (code `bad_url`) without a request. Like a wrong key, this starts no pause and shows in every call until it is fixed.
  - Credentials in the address (`http://user:password@host`) are sent as HTTP Basic authentication (httpx).
  - Redirects are not followed; an instance that redirects (e.g. HTTP to HTTPS) fails with `HTTP 301` or `HTTP 308`. Enter the address the instance answers on.
  - The address never appears in error texts or the log: a reply that echoes it is masked like a key (S3), and exceptions contribute only their class name (A4).
- **A5** One `httpx.Client` per `search` call, closed afterwards. It honours `HTTP(S)_PROXY`/`NO_PROXY`. A transport can be injected for tests.
- **A6** `limit` is kept between 1 and 20 for every stage, also for Nimble and You.com, whose APIs accept 100. Hermes rounds the model's limit up to 10, 20, 50 or 100 before it calls the provider and cuts the list to the model's limit afterwards. Exa bills every result above 10 extra and Firecrawl accepts up to 100, so an unbounded value would cost quota; 20 is the cap Hermes itself applies to Parallel. A model that asks for more than 20 results gets at most 20.

## 7. Installation and configuration

- **I1** Install the directory `search_chain/` as the plugin `search-chain`, either:
  - by copying it to `$HERMES_HOME/plugins/search-chain/` and adding `search-chain` to `plugins.enabled`, or
  - with `hermes plugins install <owner>/hermes-search-chain#search_chain --enable`.

  The keys go into the profile's `.env`.
- **I2** Configuration:
  - `web.search_backend: search-chain`.
  - `web.keyless_rescue: false`. Otherwise, when all stages fail, Hermes serves the call from anonymous free tiers without saying so in the log line of this plugin.
  - A key or address in the environment switches its stage on (K2). The names are those of Hermes' built-in providers where Hermes has one (`BRAVE_SEARCH_API_KEY`, `TAVILY_API_KEY`, `SEARXNG_URL`), else the vendor's (`YDC_API_KEY`) or a plain name (`NIMBLE_API_KEY`, `DEGOOG_URL`). A key that is there for another purpose, e.g. `TAVILY_API_KEY` for hermes-extract-chain, also switches on the search stage; `SEARCH_CHAIN_ORDER` leaves it out.
- **I3** The plugin directory contains no `pyproject.toml` and no dependencies. It is therefore not a member of Hermes' package manager and needs no environment changes.
- **I4** Egress: the host must reach the services it has keys for (HTTPS): `api.exa.ai`, `api.parallel.ai`, `api.search.brave.com`, `sdk.nimbleway.com`, `api.tavily.com`, `ydc-index.io`, `api.firecrawl.dev`, and the addresses of SearXNG and Degoog, directly or through the configured proxy. With `HTTP(S)_PROXY` set, a self-hosted address usually belongs in `NO_PROXY`; a proxy that refuses it shows as `HTTP 403`, the same status SearXNG sends without the JSON format.

## 8. Logging

- **L1** Logger `logging.getLogger(__name__)`. For each call, one INFO line: `search-chain: <stage>=<outcome> ...`, the stages in the order of K8.
  - Outcomes: `ok`, `empty`, `no_key`, `no_url`, `bad_url` (A13), `paused`, `interrupted`, `http_<status>`, `timeout`, `malformed`, `rejected` (A3), or an exception class name.
  - Each stage up to the one that ended the chain is listed, also those without a key or address: the line shows why a stage was not asked. No query text, no keys, no addresses.
  - The WARNING of K8 comes at most once per process.
  - If the call fails before the first stage (S5), the line is `search-chain: no stage ran`, after a WARNING `search-chain: call failed: <exception class>`.
  - A call with an empty query (S4) has the line `search-chain: empty_query` and no WARNING.
- **L2** When a pause starts, one WARNING line: `search-chain: <stage> paused for <seconds> s (HTTP <status> <detail>)`.
- Hermes writes INFO to `logs/agent.log` and WARNING also to `logs/errors.log` in the Hermes home.

## 9. Tests and acceptance

- **T1** Unit tests (pytest, `httpx.MockTransport`) for every rule of this document; nothing leaves the machine, and only the test of A5 opens a connection, to a closed local port. Test areas: [validation.md](validation.md).
- **T2** Live check through Hermes' real `web_search` path, without an LLM, in a profile with keys or addresses for all stages:
  - a few queries served by Exa;
  - the same with the keys of the first stages replaced by invalid ones in the process, one stage more each time, so that each stage serves once; for SearXNG and Degoog the address is replaced by one where nothing listens;
  - the status each service gives for an invalid key is recorded;
  - at most 8 requests/min per provider;
  - the script refuses to run unless the profile selects `search-chain` and has `web.keyless_rescue: false`.
  - A used-up quota (HTTP 402) is not forced in the live check; it is observed in the log during use.
- **T3** A review checks the result against this document.
- **T4** `ruff check` and `ruff format --check` are clean; CI (GitHub Actions: ruff and pytest on Python 3.11 and 3.14; pytest also runs `scripts/recompute.py`) is green.
- **T5** End-to-end test with a model (0.1.0): the model searches through Hermes' real tool path; the intended stage serves in every run; with an invalid Exa key Parallel serves, with invalid Exa and Parallel keys Firecrawl serves. Setup and results: [validation.md](validation.md). Not repeated for 0.2.0: Exa, Parallel and the path through Hermes are unchanged, and the new stages are checked live in T2.

## 10. Known limitations

The user-facing list is in the [README](../README.md#limitations). The limits that are part of the design:

- Every query is sent to the first stage that has a key or address, and possibly to the following ones (privacy). `SEARCH_CHAIN_ORDER` keeps a service out.
- A self-hosted metasearch queries Google, Bing and others from its own address. When they block it, it may return weaker hits without an error, and the chain stops there (D18). Late in the chain it is asked rarely.
- Results are passed on as the providers send them, apart from the bounds of S4. Hermes marks web search results as untrusted data; the plugin does not filter them.
- Hermes caches successful results for `web.cache_ttl_minutes` (default 20); this is why a search that finds nothing is a failure (K6).
- Parallel reserves the beta endpoint for existing integrations and names no end date. If it is switched off, the Parallel stage fails with an HTTP error on every search and the next stage with a key or address serves; the log line shows it (`parallel=http_...`), and `SEARCH_CHAIN_PARALLEL_API=v1` moves the stage to the GA endpoint.

## 11. Decisions

Every decision names its reason; where the reason is a measurement, the numbers and the data behind them are in [evaluation.md](evaluation.md) (provider comparison) and [validation.md](validation.md) (test with a model). D4 (the pause lengths), D6, D7, D8, D9, D19 and D20 are engineering judgments without a measurement behind them. D12 to D16 came out of three external code reviews of v0.1.0 (validation.md, T3). D17 to D21 came with 0.2.0 and the benchmark of 2026-10-18/19.

| ID | Decision | Reason |
|---|---|---|
| D0 | *Replaced by D17 in 0.2.0.* Exa, then Parallel, then Firecrawl; no other provider | The three scored best of seven providers: Exa 73 and Parallel 72 of 75 scored queries, Firecrawl 65 (two runs), the other four 50 to 54. Exa first (capped, about half the text of Parallel and faster inside Hermes); Firecrawl last (lowest of the three, smallest free allowance, shared with scraping). Details: evaluation.md, *Decision*. |
| D1 | Direct REST calls, not Hermes' built-in providers | The built-in Exa, Parallel and Firecrawl providers need vendor SDKs that Hermes installs on first use; in a container built from the official image, such a runtime install was seen to remove optional packages the image had shipped with (Hermes 0.21.6). Direct calls give exact status codes for K5 and reach Exa's highlight cap, which the built-in provider does not expose. |
| D2 | Parallel via the beta endpoint in mode `agentic`, as Hermes 0.21.6 calls it; `/v1/search` in mode `advanced` selectable by a setting | Measured twice against each other, the beta call was never worse: 72 against 70 of 75 queries in the comparison without a model, 36 against 34 of 36 questions in the end-to-end test with a model, at the same speed inside Hermes (3.0 against 3.3 s per search). Neither difference is statistically firm, but nothing measured favours `/v1/search`. Parallel's documentation reserves the beta endpoint for existing integrations, so the GA endpoint stays one setting away. Mode `fast` on `/v1/search` was clearly worse (49 of 75) and is not offered. |
| D3 | Exa highlights capped at 600 characters, adjustable by one setting | No detectable loss in the comparison without a model (74 against 73 of 75) at one third of the text and the same price. The end-to-end test confirmed it with a model: 36 of 36 answers correct with and without the cap, 11 % fewer input tokens (validation.md, T5). The setting switches the cap off; the bound of S4 still holds. |
| D4 | Pauses in memory, fixed lengths, only for HTTP 402, 429, and Tavily's 432 and 433 | No files, no calendar logic, self-healing. A quota does not come back within hours, so the pause after HTTP 402 is a day: at most one failing request per day and stage, and a renewed quota is picked up within a day (at once after a restart). A pause that is too short costs one failing request. A rejected key (401, 403) is a configuration error that should stay visible in every log line. Tavily reports a used-up plan with 432 and a reached pay-as-you-go limit with 433; no other service in the chain is known to send these codes. Brave reports a used-up credit, as far as known, with 429 and the code `QUOTA_LIMITED` in the body; the chain does not read the body for this (review V-01 of 0.1.0) and pauses Brave for a minute, which costs at most one failing request per minute, and Brave bills only successful requests. |
| D5 | A reply without rows moves on to the next stage; no rows at all is a failure with the reason `no results` | Cheap and rare (no empty reply in the 1,960 searches of both comparison runs); another index may have hits. A failure is not cached by Hermes (K6). |
| D6 | No note for the model about the serving stage | All three are live web searches; the model does not need to treat the results differently. The log line shows the stage. |
| D7 | Synchronous `httpx.Client` | Hermes calls `search` synchronously. |
| D8 | Constants instead of configuration, except the highlight cap, the Parallel endpoint, the order of the stages (K8) and the addresses of self-hosted stages | As little code as needed; changes come with releases. The order is a setting because which services someone has keys for, wants to pay or to send queries to differs from user to user (D20). |
| D9 | MIT license | Hermes Agent is MIT-licensed; the same license keeps reuse simple. |
| D10 | A chain, not a merge of several providers, and no model that picks results | An offline simulation on the comparison data showed no firm gain from merging (two queries won, one lost for the best cheap pair), and the ranking did not improve. Merging costs quota at every provider for every search. Details: evaluation.md, *Simulation*. |
| D11 | No forced test of a used-up quota before release | It would mean exhausting or deliberately limiting a paid account. The chain moves on after any failure, the fallback was tested with invalid keys (HTTP 401), and the log line shows HTTP 402 when it happens (validation.md, *Not verified*). |
| D12 | Bounds on what a row carries: title 300 characters, description 16,000, from Firecrawl 3,000 (S4) | The plugin exists to keep the context small, and a review put a 100,000-character title into a result with a mocked reply. The bounds follow the stored results of both comparison runs: no title was longer than 209 characters; a description had at most 600 characters from Exa with the cap, 2,967 from Parallel and 7,999 from Exa without the cap, so 16,000 only stops a faulty reply. Firecrawl's descriptions reached 13,863 characters; 26 of 400 (6.5 %) were longer than 3,000. Cutting them at 3,000 changed none of Firecrawl's 75 verdicts, nor did 5,000, 4,000, 2,000 or 1,000; at 300 two change. The check ran on the stored results, after the published verdicts of Firecrawl, Parallel and capped Exa had been reproduced from them (280 of 280). |
| D13 | No time limit for a search as a whole (A0) | httpx bounds the phases of a request; a hard limit needs a streamed read or a second thread in the request path. Unlike page extraction, where Hermes discards every result of a call that takes too long, a slow search loses nothing. The worst case needs a provider that is slow in every phase or sends its reply in a trickle, and Hermes ends the tool call after 420 s. Proposed by all three reviews of v0.1.0. With nine stages a search in which every stage runs into one timeout takes 115 s; if every stage hangs in every phase, up to about 460 s, beyond Hermes' 420 s. That needs nine services hanging at once, so 0.2.0 keeps this decision. |
| D14 | One client per call, none kept across calls (A5) | Measured: building a client takes about 9 ms, and httpx drops an idle connection after 5 s, so a kept client saves a TLS handshake only for searches within 5 s of each other. That is not worth a shared object with no place to close it. |
| D15 | The pause table stays a plain dict: no lock, no pruning, no `Retry-After`; settings are read on every call | A call reads one entry and writes one; nothing iterates over the table, and it has at most one entry per stage and key. The chain moves on after a 429 anyway, so the exact length of that pause matters little (D4). A cached setting would carry over to another profile where one process serves several. |
| D16 | Not adopted from the reviews of v0.1.0 | A range for the highlight setting: it is the operator's own value. A cap on the size of a reply: httpx has the body in memory before any cut. Masking further spellings of a key (partial, split, escaped): only a literal and a percent-encoded echo are known (A4). A length limit for URLs or queries: the longest URL in the published results has 367 characters, so a limit would sit close to real results. A type checker, the ruff groups `S` and `BLE`, a coverage gate, pinned action SHAs: `S` reported 108 findings, every one an `assert` in tests or scripts; the three broad `except` clauses are deliberate (S3, S5, A4); CI holds no secret and publishes nothing. |
| D17 | Default order Exa, Parallel, Brave, Nimble, Tavily, You.com, SearXNG, Degoog, Firecrawl | Benchmark of 2026-10-18/19, 177 queries without an LLM, scored by two independent judges on whether the answer is in a result snippet (evaluation.md, *Benchmark v2*). Exa stays first (151), Parallel second (137). From the third stage on, the chain is asked only when Exa and Parallel both fail, which did not happen once in the benchmark; between Brave (140), Nimble (135), Tavily (143) and SearXNG (131 and 131 in two runs of a re-measurement with more spacing) the answer rate differs by no significant amount, so reliability and cost decide. Keyed services come before self-hosted ones because they report a used-up quota or a wrong key as an HTTP error, so the chain moves on; a self-hosted metasearch whose upstream engines block it returns weaker hits without an error (D18) and is asked rarely late in the chain, which also keeps the risk of captchas for its address small. SearXNG before Degoog (significantly better answer rate, 131 against 124 and 120 in the re-measurement). Firecrawl last: free credits shared with page extraction. Tavily and Brave before You.com, which is significantly below Brave (121). The earlier comparison (D0, 75 technical queries through Hermes' built-in calls) had Brave at 50 to 54 against Firecrawl at 65; on the broader benchmark the two are even (140 and 138). For technical questions Firecrawl may still be the better third stage; the order is a setting (K8). |
| D18 | No quality check of replies from self-hosted stages | Measured on three runs of 177 queries: SearXNG with five or more unresponsive engines still had the answer in a snippet in 57 to 69 % of queries, against 72 to 74 % overall; with only three unresponsive engines it had 96 % in one run, so the count does not even rank the replies. Degoog's per-engine status separates good from weak replies neither by failed nor by answering engines. A rule would drop more good replies than weak ones. As for every stage, a reply without hits moves on. |
| D19 | The error text names only stages that were asked or are paused (K6) | With nine stages, a user with three keys would otherwise get up to six `no API key` reasons in every error the model reads. The log line still lists every stage of the order (L1), so a missing key stays visible where it is looked for. |
| D20 | Stages switched on by their key or address, picked and ordered by `SEARCH_CHAIN_ORDER`; variable names as in Hermes | The same mechanism as `EXTRACT_CHAIN_ORDER` in hermes-extract-chain, so both plugins are configured alike. Hermes' own names (`BRAVE_SEARCH_API_KEY`, `TAVILY_API_KEY`, `SEARXNG_URL`) mean a key set up for Hermes' built-in provider works here too; the price is that a key set for another purpose also switches on its stage, which the order setting undoes. A valid order with no usable stage does not fall back to the default, because that would send queries to services the user left out. |
| D21 | Not adopted in 0.2.0 | **DonSeTch** (self-hosted metasearch): only a command-line program and an MCP server over stdio, no HTTP interface, so the plugin would have to start a local program; too many moving parts for one stage. **Exa's keyless endpoint** as a stage: its answer rate equals Exa's with a key (150 against 151), but using it in place of a used-up keyed quota can be read as working around a technical limit, which Exa's terms forbid. **Hermes' keyless rescue ring** as a whole: about 92 hits on the expected site against 105 for Brave, and Firecrawl without a key was rate-limited on 44 % of queries. **A Degoog API key**: off by default in Degoog; can be added on request. **YaCy**: answer in a snippet for 5 of 177 queries. **Following redirects** for self-hosted addresses: the address can be entered as the instance answers. |
