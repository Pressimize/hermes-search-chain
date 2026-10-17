# Design: `search-chain`, a fallback chain for Hermes' `web_search`

Requirements carry IDs (`S`, `K`, `A`, `I`, `L`, `T`, decisions `D`). Tests and reviews refer to them.

## 1. Purpose

Hermes Agent uses exactly one provider for `web_search` (`web.search_backend`). When that provider fails, for example because its free quota is used up, Hermes does not try a second configured provider. The only built-in fallback is the *keyless rescue*: it serves the failed call from anonymous free tiers, without the configured keys.

This plugin registers its own search provider that chains three services per call:

1. **Exa**, with highlights capped at 600 characters per result.
2. **Parallel**, called as Hermes' built-in provider calls it (beta endpoint, mode `agentic`).
3. **Firecrawl**.

The next stage is asked when a stage fails, returns no hits, has no key, or is paused after a quota or rate-limit reply (K5).

**Why these three, in this order.** Full account with method, all results and data: [evaluation.md](evaluation.md). In short, the choice comes from a comparison of seven providers (Exa, Parallel, Firecrawl, TinyFish, Brave, Tavily, Keenable) on 2026-10-09 and 2026-10-10, without an LLM: 80 queries (official documentation, error messages, facts, current versions, German-language and niche topics), 75 of them scored on whether the first five results contain the expected source or answer.

| | Correct, of 75 | Text per search (median) | Time per search (median) |
|---|---|---|---|
| Exa, highlights capped at 600 characters | 74 | 4,000 characters | 0.6 s |
| Exa, as Hermes calls it | 73 | 12,000 characters | 2.0 s |
| Parallel, as Hermes calls it (beta endpoint, `agentic`) | 72 | 8,200 characters | 2.9 s |
| Parallel, `/v1/search`, `advanced` | 70 | 8,400 characters | 1.8 s |
| Firecrawl, as Hermes calls it | 65 \* | 3,900 characters | 1.3 s |
| TinyFish, Brave, Tavily, Keenable | 50 to 54 | | |

\* Firecrawl's figure combines two runs: 49 of the 55 queries of the first run (2026-10-09) and 16 of the 20 harder queries added for the second run, a day later. In the second run it ran only on those 20, to save its small free allowance; it has no second mode to compare. Results shift by a few queries from one day to the next, so the 65 is less exact than the other figures. Its text and time are from those 20 queries.

- The times of the capped Exa call and of `/v1/search` were measured as direct calls, the others through Hermes, so they are not comparable across rows. In the end-to-end test (T5), inside Hermes, a search took 1.8 s with Exa capped, 2.0 s with Exa uncapped, 3.0 s with Parallel's beta call and 3.3 s with `/v1/search` (medians).
- Exa and Parallel are not distinguishable on this data: a difference of up to four queries is within the day-to-day variation of the providers (evaluation.md, Run 2).
- Firecrawl is third, ahead of the other four. On the 20 harder queries added for the second run it got 16 (Exa 19, Parallel 18). On the other 55, in the first run, it got 49 from the result list (Exa 55, Parallel 52) and 53 with result pages (Exa 55, Parallel 53): its snippets are short, so the fix for an error message is often only on the page.
- The other four are clearly behind on the same queries.
- Exa comes first because the capped call returns about half the text of Parallel for the same hits and was faster inside Hermes. Being first, it is also the first to use up its free allowance, which is smaller than Parallel's; the chain then carries on with Parallel. Firecrawl comes last: from the result list it scored lowest of the three, and its free allowance is the smallest and shared with scraping, so the chain spares it.

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
- **S3** Keys and the settings (A1, A2) are read only via `agent.web_search_provider.get_provider_env(...)`, so per-profile `.env` files work.
  - If reading a value raises (e.g. `UnscopedSecretError`), it counts as unset.
  - A key of 8 or more characters that a reply echoes never appears in error texts or logs. A shorter value is not masked (A4). The pause table holds only a SHA-256 digest of the key (K5).
- **S4** `search(query, limit=5)` is synchronous, as in every Hermes search provider. On success it returns `{"success": True, "data": {"web": [...]}}`. Each row has the keys `url`, `title`, `description`, `position`, in this order; `position` counts from 1. All rows of one call come from one stage.
  - A result counts as a row only if its `url` is a string that starts with `http://` or `https://`, in any letter case; anything else is dropped, and the URL is passed on as sent. Hermes refuses other schemes and private addresses when it fetches a URL; the plugin does not repeat that check.
  - `title` and `description` are text; a value of another type becomes empty. A title is cut at 300 characters and a description at 16,000, from Firecrawl at 3,000, without a marker (D12).
  - A query that is not text, or is empty or only whitespace, fails at once with `search-chain: empty query`; no stage is asked. Hermes passes such a query on unchecked.
- **S5** `search` never raises. A failure is `{"success": False, "error": "<text>"}`. An unexpected exception fails the call with `search-chain: <exception class>`.
- **S6** Interrupts, as in Hermes' built-in providers: the plugin checks `tools.interrupt.is_interrupted()` before each stage. If it is set, the chain stops without a further request, the call returns the failure `Interrupted`, and the log line shows `<stage>=interrupted`. A request in flight is not cancelled; its timeout (A0) still applies. Hermes checks the flag itself before it calls the provider, so the check matters between stages. Outside Hermes (tests) the module is not importable; then interrupts are not checked.

## 5. Chain (per call)

- **K1** The stages are asked in the fixed order Exa, Parallel, Firecrawl.
- **K2** A stage is skipped without a request when its key is unset (`no_key`) or the stage is paused (`paused`, K5).
- **K3** A stage that returns at least one row ends the chain; the call succeeds with these rows.
- **K4** Otherwise the next stage is asked. This covers an API error (HTTP status outside 200–299), a transport error, a timeout, a malformed reply, and a valid reply without rows (`empty`), which includes a reply whose results were all dropped (S4).
- **K5** Pauses. After certain replies a stage is skipped for a while, so that a used-up quota does not cost one failing request per search:

  | Reply | Pause | Meaning |
  |---|---|---|
  | HTTP 402 | 86,400 s (24 h) | quota or budget used up |
  | HTTP 429 | 60 s | rate limit |
  | anything else | none | |

  - A pause belongs to the pair of stage and key, so profiles with different keys in one process do not pause each other, and a corrected key is used at once. The table is keyed by a SHA-256 digest of the key and holds no key itself.
  - Pauses live in memory only. A new process starts without pauses; a wrong pause ends by itself.
  - After the pause, the stage is asked again on the next call. Nothing needs to be reset when a quota renews.
  - The reason of a paused stage repeats the reply that caused the pause and the remaining time, e.g. `Exa: HTTP 402 NO_MORE_CREDITS (paused for another 17 h)`; below one hour it is given in minutes, rounded up, from one hour on as the nearest hour.
  - Hermes may run several searches at once on one provider object. The pause table is a plain dict without a lock: calls already in flight when the first quota reply arrives each get their own reply and set the same pause again.
- **K6** When no stage returned rows, the call fails, and the error names the reason of every stage, e.g. `search-chain: Exa: HTTP 402 NO_MORE_CREDITS; Parallel: no API key; Firecrawl: timeout`. A valid reply without rows has the reason `no results`. This is a failure and not an empty success, because Hermes caches every success for `web.cache_ttl_minutes`; an empty list that only came about because a better stage was paused would otherwise be repeated for that time.
- **K7** Each stage is asked at most once per call. No retries.

## 6. Provider calls (direct REST)

- **A0** Every request has a timeout (httpx): Exa 10 s, Parallel 15 s, Firecrawl 15 s. Slowest searches measured: Exa 6.4 s (the capped call inside the plugin in the end-to-end test; the uncapped call through Hermes was as slow in both comparison runs), Parallel's beta call 6.4 s (run 1, through Hermes), Firecrawl 7.7 s (run 2, through Hermes). httpx bounds each phase of a request (connect, write, read, pool), not the total: a request that is slow in several phases takes longer than its timeout, and a reply that arrives in a trickle is not bounded at all. Hermes 0.21.6 ends a tool call after 420 s by default (D13).
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
- **A4** Errors:
  - A non-2xx status becomes `<Provider>: HTTP <status> <detail>`. The detail is the first of these that is present in the JSON body: `tag` (Exa, e.g. `NO_MORE_CREDITS`), `error`, `message` (a dict value contributes its `message`); otherwise the response text. A body that cannot be parsed counts as no JSON; the status still decides about a pause (K5).
  - A transport error becomes `<Provider>: timeout` or `<Provider>: <exception class>`; a 2xx reply that is not the expected JSON becomes `<Provider>: malformed reply`. A request that httpx cannot build, such as one with a key or query it cannot encode, sends nothing and also becomes `<Provider>: <exception class>` (e.g. `UnicodeEncodeError`), not `malformed reply`. A reply that httpx cannot decode, such as a broken compressed body, is a transport error whatever its status.
  - Error texts are one line: line breaks and other control characters become spaces, and runs of spaces become one space, so a reply cannot add lines to the log. Only the first 2,000 characters of a reply are looked at, and the text is cut to 200 characters after the provider name.
  - A key echoed in an error text is replaced by `[key]` if it has 8 or more characters (S3). Other spellings of the key, such as a URL-encoded one, are not recognised.
  - Each outcome has a short code for the log (L1).
- **A5** One `httpx.Client` per `search` call, closed afterwards. It honours `HTTP(S)_PROXY`/`NO_PROXY`. A transport can be injected for tests.
- **A6** `limit` is kept between 1 and 20 for every stage. Hermes rounds the model's limit up to 10, 20, 50 or 100 before it calls the provider and cuts the list to the model's limit afterwards. Exa bills every result above 10 extra and Firecrawl accepts up to 100, so an unbounded value would cost quota; 20 is the cap Hermes itself applies to Parallel. A model that asks for more than 20 results gets at most 20.

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
  - A call with an empty query (S4) has the line `search-chain: empty_query` and no WARNING.
- **L2** When a pause starts, one WARNING line: `search-chain: <stage> paused for <seconds> s (HTTP <status> <detail>)`.
- Hermes writes INFO to `logs/agent.log` and WARNING also to `logs/errors.log` in the Hermes home.

## 9. Tests and acceptance

- **T1** Unit tests (pytest, `httpx.MockTransport`; nothing leaves the machine, and only the test of A5 opens a connection, to a closed local port):
  - every branch of K2–K6, with missing keys and pauses, including all stages paused or without key; at most one request per stage (K7);
  - pauses per status, their end (injected clock), and per key (K5);
  - requests and row mapping of A1–A3 (both Parallel calls), the values of the settings of A1 and A2, the cap of A2; error texts on one line, codes and key masking (A4); the proxy variables (A5);
  - result shape and key order, the URL rule, the text bounds and the empty query (S4); the bounds of `limit` (A6); no exception escapes (S5); interrupts (S6);
  - `register(ctx)` and `plugin.yaml` (S1); properties and `is_available` (S2); keys absent from results and logs (S3); log lines (L1, L2).
- **T2** Live check through Hermes' real `web_search` path, without an LLM, in a profile with the three keys:
  - a few queries served by Exa;
  - the same with the Exa key replaced by an invalid one in the process (HTTP 401): Parallel serves;
  - the same with the Exa and Parallel keys replaced: Firecrawl serves;
  - at most 8 requests/min per provider;
  - the script refuses to run unless the profile selects `search-chain` and has `web.keyless_rescue: false`.
  - A used-up quota (HTTP 402) is not forced in the live check; it is observed in the log during use.
- **T3** A review checks the result against this document.
- **T4** `ruff check` and `ruff format --check` are clean; CI (GitHub Actions: ruff, pytest and `scripts/recompute.py` on Python 3.11 and 3.14) is green.
- **T5** End-to-end test with a model (2026-10-10, Hermes Desktop 0.21.6, 36 questions, four setups, one run each): the model searches through Hermes' real tool path; the intended stage serves in every run; with an invalid Exa key Parallel serves, with invalid Exa and Parallel keys Firecrawl serves. Results: [validation.md](validation.md).

## 10. Known limitations

- The chain reacts to quota replies; it does not know the remaining quota in advance.
- Whether a provider answers HTTP 402 or bills a stored payment method when the free quota is used up depends on the account settings (auto recharge, budgets). For a hard cost cap, keep auto recharge off.
- Parallel does not document its replies for a used-up quota. The chain moves on after any failure, so only the length of the pause depends on the status code.
- After a restart the first call asks every stage again, including one with a used-up quota.
- A renewed or topped-up quota is used only when the 24-hour pause ends or Hermes restarts.
- A search that finds nothing at any stage is reported as a failure with `no results` (K6).
- Results of different stages differ in length: Exa capped about 4,000 characters per search, Parallel about 8,200, Firecrawl about 3,900 (medians for 5 results). A description from Firecrawl is cut at 3,000 characters (D12).
- Parallel reserves the beta endpoint for existing integrations and names no end date. If it is switched off, the Parallel stage fails with an HTTP error on every search and Firecrawl serves; the log line shows it (`parallel=http_...`), and `SEARCH_CHAIN_PARALLEL_API=v1` moves the stage to the GA endpoint.
- Hermes caches successful results for `web.cache_ttl_minutes` (default 20).
- Every query is sent to Exa, and possibly to Parallel and Firecrawl (privacy).
- Titles and descriptions are third-party content and reach the model as the providers send them, apart from the bounds of S4. Hermes marks web search results as untrusted data; the plugin does not filter them.
- A model that asks for more than 20 results gets at most 20 (A6).
- A search has no time limit as a whole (A0, D13).
- Providers and their order are fixed.

## 11. Decisions

Every decision names its reason; where the reason is a measurement, the numbers and the data behind them are in [evaluation.md](evaluation.md) (provider comparison) and [validation.md](validation.md) (test with a model). D4 (the pause lengths), D6, D7, D8 and D9 are engineering judgments without a measurement behind them. D12 to D16 came out of three external code reviews of v0.1.0 (validation.md, T3).

| ID | Decision | Reason |
|---|---|---|
| D0 | Exa, then Parallel, then Firecrawl; no other provider | The three scored best: Exa 73 and Parallel 72 of 75 scored queries in the second run, Firecrawl 65 over both runs (49 of 55 in the first, 16 of the 20 it ran in the second), the other four providers 50 to 54. All three almost always show the current version of a project in the snippet. Exa first: with the cap it returns about half the text of Parallel and was faster inside Hermes; being first, it is also the first to use up its free allowance, and the chain carries on with Parallel. Firecrawl last: from the result list it scored lowest of the three, and its free allowance is the smallest and shared with scraping, so the chain spares it. Details: evaluation.md, *Decision*. |
| D1 | Direct REST calls, not Hermes' built-in providers | The built-in Exa, Parallel and Firecrawl providers need vendor SDKs that Hermes installs on first use; in a container built from the official image, such a runtime install was seen to remove optional packages the image had shipped with (Hermes 0.21.6). Direct calls give exact status codes for K5 and reach Exa's highlight cap, which the built-in provider does not expose. |
| D2 | Parallel via the beta endpoint in mode `agentic`, as Hermes 0.21.6 calls it; `/v1/search` in mode `advanced` selectable by a setting | Measured twice against each other, the beta call was never worse: 72 against 70 of 75 queries in the comparison without a model, 36 against 34 of 36 questions in the end-to-end test with a model, at the same speed inside Hermes (3.0 against 3.3 s per search). Neither difference is statistically firm, but nothing measured favours `/v1/search`. Parallel's documentation reserves the beta endpoint for existing integrations, so the GA endpoint stays one setting away. Mode `fast` on `/v1/search` was clearly worse (49 of 75) and is not offered. |
| D3 | Exa highlights capped at 600 characters, adjustable by one setting | No detectable loss in the comparison without a model (74 against 73 of 75) at one third of the text and the same price. The end-to-end test confirmed it with a model: 36 of 36 answers correct with and without the cap, 11 % fewer input tokens (validation.md, T5). The setting switches the cap off; the bound of S4 still holds. |
| D4 | Pauses in memory, fixed lengths, only for HTTP 402 and 429 | No files, no calendar logic, self-healing. A quota does not come back within hours, so the pause after HTTP 402 is a day: at most one failing request per day and stage, and a renewed quota is picked up within a day (at once after a restart). A pause that is too short costs one failing request. A rejected key (401, 403) is a configuration error that should stay visible in every log line. |
| D5 | A reply without rows moves on to the next stage; no rows at all is a failure with the reason `no results` | Cheap and rare (no empty reply in the 1,960 searches of both comparison runs); another index may have hits. A failure is not cached by Hermes (K6). |
| D6 | No note for the model about the serving stage | All three are live web searches; the model does not need to treat the results differently. The log line shows the stage. |
| D7 | Synchronous `httpx.Client` | Hermes calls `search` synchronously. |
| D8 | Constants instead of configuration, except the highlight cap and the Parallel endpoint | As little code as needed; changes come with releases. |
| D9 | MIT license | Hermes Agent is MIT-licensed; the same license keeps reuse simple. |
| D10 | A chain, not a merge of several providers, and no model that picks results | An offline simulation on the comparison data showed no firm gain from merging (two queries won, one lost for the best cheap pair), and the ranking did not improve. Merging costs quota at every provider for every search. Details: evaluation.md, *Simulation*. |
| D11 | No forced test of a used-up quota before release | It would mean exhausting or deliberately limiting a paid account. The chain moves on after any failure, the fallback was tested with invalid keys (HTTP 401), and the log line shows HTTP 402 when it happens (validation.md, *Not verified*). |
| D12 | Bounds on what a row carries: title 300 characters, description 16,000, from Firecrawl 3,000 (S4) | The plugin exists to keep the context small, and a review put a 100,000-character title into a result with a mocked reply. The bounds follow the stored results of both comparison runs: no title was longer than 209 characters; a description had at most 600 characters from Exa with the cap, 2,967 from Parallel and 7,999 from Exa without the cap, so 16,000 only stops a faulty reply. Firecrawl's descriptions reached 13,863 characters; 26 of 400 (6.5 %) were longer than 3,000. Cutting them at 3,000 changed none of Firecrawl's 75 verdicts, nor did 2,000 or 1,000; at 300 two change (validation.md, T3). |
| D13 | No time limit for a search as a whole (A0) | httpx bounds the phases of a request; a hard limit needs a streamed read or a second thread in the request path. Unlike page extraction, where Hermes discards every result of a call that takes too long, a slow search loses nothing. The worst case needs a provider that is slow in every phase or sends its reply in a trickle, and Hermes ends the tool call after 420 s. Proposed by all three reviews of v0.1.0. |
| D14 | One client per call, none kept across calls (A5) | Measured: building a client takes about 9 ms, and httpx drops an idle connection after 5 s, so a kept client saves a TLS handshake only for searches within 5 s of each other. That is not worth a shared object with no place to close it. |
| D15 | The pause table stays a plain dict: no lock, no pruning, no `Retry-After`; settings are read on every call | A call reads one entry and writes one; nothing iterates over the table, and it has at most one entry per stage and key. The chain moves on after a 429 anyway, so the exact length of that pause matters little (D4). A cached setting would carry over to another profile where one process serves several. |
| D16 | Not adopted from the reviews of v0.1.0 | A range for the highlight setting: it is the operator's own value. A cap on the size of a reply: httpx has the body in memory before any cut. Masking other spellings of a key (URL-encoded, partial): only a literal echo is known. A length limit for URLs or queries: the longest URL in the published results has 367 characters, so a limit would sit close to real results. A type checker, the ruff groups `S` and `BLE`, a coverage gate, pinned action SHAs: `S` reported 108 findings, every one an `assert` in tests or scripts; the three broad `except` clauses are deliberate (S3, S5, A4); CI holds no secret and publishes nothing. |
