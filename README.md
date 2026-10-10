# hermes-search-chain

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin that makes `web_search` fall back across three search services: **Exa → Parallel → Firecrawl**.

Hermes uses exactly one search provider. If it fails, for example because the free quota is used up, the model gets an error, or Hermes' keyless rescue serves the call from anonymous free tiers. This plugin registers one provider, `search-chain`, that asks the next service when one fails, returns nothing, or has run out of quota.

It is the search counterpart of [hermes-extract-chain](https://github.com/Pressimize/hermes-extract-chain), which does the same for `web_extract`.

## How it works

```mermaid
flowchart LR
    Q[query] --> E[Exa<br>highlights capped]
    E -- results --> R[results]
    E -- error / no results / no key / paused --> P[Parallel<br>mode agentic]
    P -- results --> R
    P -- error / no results / no key / paused --> F[Firecrawl]
    F -- results --> R
    F -- error / no results / no key / paused --> X[error with all reasons]
```

- Each service is asked at most once per search; there are no retries.
- A service without a key is skipped.
- After **HTTP 402** (quota or budget used up) a service is skipped for 24 hours, after **HTTP 429** (rate limit) for one minute. Then it is asked again, so nothing has to be reset when a quota renews. Pauses live in memory only; restarting Hermes ends them.
- If no service returns results, the model gets one error with every reason, e.g. `search-chain: Exa: HTTP 402 NO_MORE_CREDITS (paused for another 17 h); Parallel: timeout; Firecrawl: no results`.

The model gets the same result format as from any Hermes search provider. It is not told which service answered; the log is (see *Check*).

## Why these three

They come from a comparison of seven search providers on 80 queries without an LLM (official documentation, error messages, facts, current versions, German-language and niche topics; 75 scored on whether the first five results contain the expected source or answer):

| | Correct, of 75 | Text per search (median) | Time per search (median) |
|---|---|---|---|
| Exa, highlights capped at 600 characters | 74 | 4,000 characters | 0.6 s |
| Exa, as Hermes calls it | 73 | 12,000 characters | 2.0 s |
| Parallel, as Hermes calls it | 72 | 8,200 characters | 2.9 s |
| Parallel, `/v1/search`, mode `advanced` | 70 | 8,400 characters | 1.8 s |
| Firecrawl, as Hermes calls it | 65 \* | 3,900 characters | 1.3 s |
| TinyFish, Brave, Tavily, Keenable | 50 to 54 | | |

\* Firecrawl's figure combines two runs: 49 of the 55 queries of the first run (2026-10-09) and 16 of the 20 harder queries added for the second run, a day later. In the second run it ran only on those 20, to save its small free allowance; it has no second mode to compare. Results shift by a few queries from one day to the next, so the 65 is less exact than the other figures. Its text and time are from those 20 queries.

The times of the capped Exa call and of `/v1/search` were measured as direct calls, the others through Hermes, so they are not comparable across rows; inside Hermes both Parallel calls took about 3 s and Exa about 2 s (see *Validation*).

Exa and Parallel are not distinguishable on this data; a difference of a few queries is within the day-to-day variation of the providers. Firecrawl is third, ahead of the other four. On the 20 harder queries it got 16 (Exa 19, Parallel 18). On the 55 queries of the first run it got 49 when only the result list counts (Exa 55, Parallel 52), and 53 when an answer found only on a result page counts as well (Exa 55, Parallel 53): its snippets are short, so the fix for an error message is often only on the page. Exa comes first because the capped call returns about half the text of Parallel for the same hits and was faster inside Hermes (1.8 s against 3.0 s per search in the end-to-end test). Being first, it is also the first to use up its free allowance, which is smaller than Parallel's; the chain then carries on with Parallel. Firecrawl comes last: from the result list it scored lowest of the three, and its free allowance is the smallest and shared with scraping, so the chain spares it.

The full comparison, with all seven providers, the tested modes, a simulation of merging providers, costs and the reasons for each choice, is in [docs/evaluation.md](docs/evaluation.md). Every query and per-query result is in [`data/`](data).

## Requirements

- Hermes Agent ≥ 0.21 (written against v0.21.6).
- API keys; a service without a key is skipped, at least one is needed:
  - [Exa](https://exa.ai): free plan with $10 of credits per month, about 1,400 searches at $7 per 1,000.
  - [Parallel](https://parallel.ai): the pricing page names 5,000 free requests per month.
  - [Firecrawl](https://firecrawl.dev): free plan with 1,000 credits per month, 2 credits per search of up to 10 results, 10 searches per minute.
- Network access to `api.exa.ai`, `api.parallel.ai` and `api.firecrawl.dev` (HTTPS; `HTTPS_PROXY` is honoured).

No extra Python packages: the plugin only uses `httpx`, which ships with Hermes.

## Installation

**Manual (recommended):** copy the directory `search_chain/` as `plugins/search-chain/` into your Hermes home.

| Setup | Target directory |
|---|---|
| Linux / macOS | `$HERMES_HOME/plugins/search-chain/`; the Hermes home is usually `~/.hermes` |
| Official Docker image | `/opt/data/plugins/search-chain/` (`/opt/data` is the mounted Hermes home) |
| Hermes Desktop (Windows), per profile | `%LOCALAPPDATA%\hermes\profiles\<profile>\plugins\search-chain\` |

```bash
git clone https://github.com/Pressimize/hermes-search-chain.git
cp -r hermes-search-chain/search_chain "${HERMES_HOME:-$HOME/.hermes}/plugins/search-chain"
```

Then enable it in the profile's `config.yaml` (user plugins are opt-in) and select it:

```yaml
plugins:
  enabled:
    - search-chain           # add to your existing entries
web:
  search_backend: search-chain
  keyless_rescue: false      # required: otherwise Hermes silently replaces a failed chain
```

`web.keyless_rescue` also applies to `web_extract`. With it on, a search that fails at all three services is served from anonymous free tiers, and neither the model nor this plugin's log line shows it.

Put the keys into the profile's `.env`:

```bash
EXA_API_KEY=...
PARALLEL_API_KEY=...
FIRECRAWL_API_KEY=...
```

Restart Hermes (or the gateway).

**With Hermes' installer:**

```bash
hermes plugins install Pressimize/hermes-search-chain#search_chain --enable
```

It clones only the `search_chain` subdirectory, asks for the three keys and enables the plugin. The `web:` settings above are still needed. Enabling through Hermes' CLI also syncs Hermes' package environment; the manual route avoids that step.

**Check:** let the agent search for something. `logs/agent.log` in the Hermes home then shows a line per search:

```text
search-chain: exa=ok
search-chain: exa=http_402 parallel=ok
search-chain: exa=paused parallel=ok
```

When a pause starts, `logs/errors.log` gets a line such as `search-chain: exa paused for 86400 s (HTTP 402 NO_MORE_CREDITS)`.

## Settings

Two optional settings in the profile's `.env`:

```bash
SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS=600   # default; 0 = Exa's own highlight length (about three times the text)
SEARCH_CHAIN_PARALLEL_API=beta         # default: the call Hermes makes; v1 = /v1/search in mode advanced
```

Exa returns excerpts ("highlights") per result. Capped at 600 characters, a search of five results is about 4,000 characters instead of 12,000, with no detectable loss of hits in the comparison. In the end-to-end test (see *Validation*) the model answered all 36 questions correctly with and without the cap; the cap saved a third of the input tokens on error-message questions, where Exa's own highlights are long, and nothing on version questions. Set `0` to switch the cap off.

Parallel is called on its beta endpoint in mode `agentic`, exactly as Hermes' built-in provider does. `v1` moves the stage to the GA endpoint `/v1/search` in mode `advanced`; see the FAQ.

## Validation

- **Unit tests** without network for every rule of the chain, the provider calls and the settings.
- **End-to-end with a model** (2026-10-10, Hermes Desktop 0.21.6; the model was GLM 5.3, served through Mistral's API): 36 questions in German (10 facts, 10 error messages, 16 "latest version of X"), each asked once in four setups through Hermes' real tool path, 144 runs. No run failed, and the intended stage served every search.

  | | Exa capped | Exa uncapped | Parallel `/v1/search` | Parallel beta (as Hermes) |
  |---|---|---|---|---|
  | Correct answers, of 36 | 36 | 36 | 34 | 36 |
  | Time per search, median | 1.8 s | 2.0 s | 3.3 s | 3.0 s |
  | Input tokens, all questions | 430,606 | 484,082 | 497,072 | 494,759 |

  Two blind judges scored all answers and agreed on every one. With 36 questions only large differences would show; the answers are at the ceiling, so the setups differ in effort, not in correctness.
- **Fallback:** with an invalid Exa key the log showed `exa=http_401 parallel=ok`, with invalid Exa and Parallel keys `exa=http_401 parallel=http_401 firecrawl=ok`; the model got usable results both times.
- **Not verified:** a really used-up quota (HTTP 402 and the 24-hour pause).

Setup, judging, all tables and limits: [docs/validation.md](docs/validation.md). Questions, per-run results and answers: [`data/end-to-end/`](data/end-to-end).

## Update and uninstall

- **Update:** replace the `plugins/search-chain/` directory with the new `search_chain/` and restart Hermes. After a Git install, use `hermes plugins update search-chain`. See [CHANGELOG.md](CHANGELOG.md).
- **Uninstall:**
  1. Delete `plugins/search-chain/`.
  2. Remove `search-chain` from `plugins.enabled`.
  3. Set `web.search_backend` back to your previous provider.
  4. Restart Hermes.

## Costs and quotas

The chain reacts to a service's reply; it does not know the remaining quota in advance. Whether a service answers HTTP 402 or charges a stored payment method when the free quota is used up depends on your account settings. For a hard cost cap, keep auto recharge off at Exa and Firecrawl and store no payment method you do not want charged.

Count which service answered:

```bash
grep -o "search-chain: .*" logs/agent.log | grep -o "[a-z]*=ok" | sort | uniq -c
```

## Limitations

- **Fixed providers and order.**
- **No results is an error.** If no service finds anything, the model gets an error with `no results` instead of an empty list, because Hermes caches every successful result for `web.cache_ttl_minutes` (default 20).
- **Different result lengths.** Exa (capped) returns about 4,000 characters per search, Parallel about 8,200, Firecrawl about 3,900.
- **Parallel's quota replies are not documented.** The chain moves on after any failure; only the 24-hour pause depends on the status code being 402.
- **After a restart** the first search asks every service again, including one with a used-up quota. Without a restart, a renewed or topped-up quota is used only after the 24-hour pause.
- **Privacy.** Every query is sent to Exa, and possibly to Parallel and Firecrawl.
- **Timeouts** are 10 s (Exa) and 15 s (Parallel, Firecrawl) for each phase of a request (connect, send, wait for the reply). A search in which every service hangs takes about 40 s; there is no hard limit on the total.

## FAQ

**Why not reuse Hermes' built-in Exa, Parallel and Firecrawl providers?**
They need vendor SDKs that Hermes installs on first use. Calling the REST APIs directly needs nothing extra, gives exact status codes, and reaches Exa's highlight cap, which the built-in provider does not expose.

**Which Parallel endpoint, and why?**
The beta endpoint in mode `agentic`, the call Hermes 0.21.6 makes. Measured twice against `/v1/search` in mode `advanced`, it was never worse (72 against 70 of 75 queries without a model, 36 against 34 of 36 questions with a model) and equally fast inside Hermes. The differences are not statistically firm, but nothing measured favours `/v1/search`. Parallel reserves the beta endpoint for existing integrations; if it is switched off, set `SEARCH_CHAIN_PARALLEL_API=v1`. Mode `fast` on `/v1/search` was clearly worse (49 of 75) and is not offered.

**Does it merge or re-rank results from several services?**
No. A simulation on the comparison data showed no measurable gain from merging; all results of one search come from one service.

**Does it do page extraction?**
No. `web.extract_backend` is unaffected; see [hermes-extract-chain](https://github.com/Pressimize/hermes-extract-chain).

## Development

```bash
uv sync                                   # Python >= 3.11, httpx as in Hermes
uv run ruff check && uv run ruff format --check
uv run pytest
```

| Path | Content |
|---|---|
| `search_chain/` | The plugin: `provider.py` (Hermes interface, chain, pauses), `engines.py` (REST clients) |
| `tests/` | Unit tests without network (`httpx.MockTransport`; Hermes is stubbed in `conftest.py`) |
| `scripts/recompute.py` | Recomputes the tables of the evaluation and validation documents from the CSV files in `data/` |
| `scripts/live_check.py` | Calls Hermes' real `web_search` path in a profile, without an LLM and with rate limiting; can break keys to force the fallback |
| `docs/` | [evaluation](docs/evaluation.md) (provider choice, test method, results), [design](docs/design.md) (requirements and decisions with their reasons), [validation](docs/validation.md) (tests, reviews, end-to-end test with a model) |
| `data/` | Test data as CSV: queries, per-query results of both comparison runs, questions and answers of the end-to-end test ([description](data/README.md)) |

`pyproject.toml` only configures the tooling. It sits at the repository root on purpose: Hermes treats a plugin directory that contains a `pyproject.toml` as a package-manager member.

## Authors

- [Pressimize](https://github.com/Pressimize): idea, requirements and decisions.
- Claude, Anthropic's AI model, working in Claude Code: design, code, tests, evaluation and documentation.

## License

[MIT](LICENSE)
