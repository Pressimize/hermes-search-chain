# hermes-search-chain

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin that makes `web_search` fall back across up to nine search services: **Exa → Parallel → Brave → Nimble → Tavily → You.com → SearXNG → Degoog → Firecrawl**.

Hermes uses exactly one search provider. If it fails, for example because the free quota is used up, the model gets an error, or Hermes' keyless rescue serves the call from anonymous free tiers. This plugin registers one provider, `search-chain`, that asks the next service when one fails, returns nothing, or has run out of quota. A service you have no key or address for is skipped, and you can pick and order the services yourself.

It is the search counterpart of [hermes-extract-chain](https://github.com/Pressimize/hermes-extract-chain), which does the same for `web_extract`.

## How it works

```mermaid
flowchart LR
    Q[query] --> S1[Exa]
    S1 -. "error / no results / no key / paused" .-> S2[Parallel]
    S2 -.-> S3[Brave]
    S3 -.-> S4[Nimble]
    S4 -.-> S5[Tavily]
    S5 -.-> S6[You.com]
    S6 -.-> S7[SearXNG]
    S7 -.-> S8[Degoog]
    S8 -.-> S9[Firecrawl]
    S9 -.-> X[error with the reasons]
```

The first stage that returns results ends the chain, and its results go to the model. The dotted arrows are the same case everywhere: the stage failed, found nothing, has no key or address, or is paused.

- Each service is asked at most once per search; there are no retries.
- A service without a key or address is skipped.
- Every service is asked for at most 20 results; a result without an `http(s)` address is dropped.
- After **HTTP 402** (quota or budget used up) a service is skipped for 24 hours, after **HTTP 429** (rate limit) for one minute. Tavily's **432** and **433** (plan limit, pay-as-you-go limit) pause it for 24 hours like a 402. Then the service is asked again, so nothing has to be reset when a quota renews. Pauses live in memory only; restarting Hermes ends them.
- If no service returns results, the model gets one error with the reason of every service that was asked or is paused, e.g. `search-chain: Exa: HTTP 402 NO_MORE_CREDITS (paused for another 17 h); Parallel: timeout; Firecrawl: no results`. Services without a key or address are not named there; the log names them. If none is configured, the error is `search-chain: no stage configured`.

The model gets the same result format as from any Hermes search provider. It is not told which service answered; the log is (see *Check*).

## Why this order

In a benchmark of 177 queries (2026-10-18/19), two LLM judges scored whether the answer is in a result snippet. Of 177: Exa 151, Tavily 143, Brave 140, Firecrawl 138, Parallel 137, Nimble 135, SearXNG 131, Degoog 124, You.com 121 (SearXNG and Degoog from a re-measurement with more spacing between queries).

- **Exa first, Parallel second.** Exa leads, and neither failed once in the benchmark. From the third stage on, the chain is asked only when both fail.
- **Brave, Nimble, Tavily, then You.com.** Brave, Nimble, Tavily and SearXNG do not differ significantly in the answer rate, so reliability and cost decide. You.com is significantly below Brave.
- **Services with a key before self-hosted ones.** A service with a key reports a used-up quota or a wrong key as an HTTP error, and the chain moves on. A self-hosted metasearch whose upstream engines block it returns weaker hits without an error, and the chain stops there. Late in the chain it is asked rarely.
- **SearXNG before Degoog.** Its answer rate is significantly better (131 against 124).
- **Firecrawl last.** Its free credits are shared with page extraction. For technical questions it may still be the better third stage; the order is a setting (see *Settings*).

Method, tables, significance tests and the services that did not make the chain: [docs/evaluation.md](docs/evaluation.md). The decisions with their reasons: [docs/design.md](docs/design.md), D17 to D21.

## Requirements

- Hermes Agent ≥ 0.21 (written against v0.21.6).
- At least one key or address; a service without one is skipped. Prices and free allowances are the vendors' statements as read on 2026-10-19; check them before relying on them.

  | Stage | Key or address | Cost and free allowance |
  |---|---|---|
  | [Exa](https://exa.ai) | `EXA_API_KEY` | Free plan with $10 of credits per month, about 1,400 searches at $7 per 1,000. |
  | [Parallel](https://parallel.ai) | `PARALLEL_API_KEY` | The pricing page names 5,000 free requests per month. |
  | [Brave Search](https://brave.com/search/api/) | `BRAVE_SEARCH_API_KEY` | $5 of credit per month, about 1,000 searches; a payment card is required even for the free credit. Then $5 per 1,000. |
  | [Nimble](https://www.nimbleway.com) | `NIMBLE_API_KEY` | Depth `lite`: $1.10 per 1,000, billed only for successful requests. A trial of 5,000 pages exists; whether it covers search is unclear. |
  | [Tavily](https://tavily.com) | `TAVILY_API_KEY` | 1,000 credits per month without a card, 1 credit per basic search. Same key and credits as Tavily in hermes-extract-chain. |
  | [You.com](https://you.com) | `YDC_API_KEY` | $5 per 1,000 calls. Whether a start credit exists is unconfirmed. |
  | [SearXNG](https://docs.searxng.org) | `SEARXNG_URL` | Free, self-hosted. |
  | [Degoog](https://github.com/degoog-org/degoog) | `DEGOOG_URL` | Free, self-hosted. |
  | [Firecrawl](https://firecrawl.dev) | `FIRECRAWL_API_KEY` | Free plan with 1,000 credits per month, 2 credits per search of up to 10 results, 10 searches per minute; shared with scraping. |

- **SearXNG:** add `json` to `search.formats` in the instance's settings; by default only `html` is on, and the instance answers HTTP 403 otherwise. Keep the limiter off (the default) or let the address of the Hermes host pass, otherwise it answers HTTP 429.
- **Degoog:** its API key and rate limiter are off by default. If you turn them on, it answers 401 or 429; the plugin sends no Degoog key.
- **Addresses** are `http://` or `https://` with a host and no `?` or `#`. Credentials in the address (`http://user:password@host`) are sent as HTTP Basic authentication. Redirects are not followed: enter the address the instance answers on, or the stage fails with `HTTP 301` or `HTTP 308`.
- **Network:** HTTPS access to `api.exa.ai`, `api.parallel.ai`, `api.search.brave.com`, `sdk.nimbleway.com`, `api.tavily.com`, `ydc-index.io` and `api.firecrawl.dev` for the services you have keys for, and to the addresses of SearXNG and Degoog. `HTTPS_PROXY` is honoured. If a proxy is set, put the self-hosted addresses into `NO_PROXY`; a proxy that refuses an address shows up as `HTTP 403`, the same status SearXNG sends without the JSON format.

No extra Python packages: the plugin only uses `httpx`, which ships with Hermes.

## Installation

**Manual (recommended):** copy the directory `search_chain/` as `plugins/search-chain/` into your Hermes home.

| Setup | Target directory |
|---|---|
| Linux / macOS | `$HERMES_HOME/plugins/search-chain/`; the Hermes home is usually `~/.hermes` |
| Official Docker image | `/opt/data/plugins/search-chain/` (`/opt/data` is the mounted Hermes home) |
| Hermes Desktop (Windows), per profile | `%LOCALAPPDATA%\hermes\profiles\<profile>\plugins\search-chain\` |

```bash
git clone https://github.com/Pressimize/hermes-search-chain.git   # for an update: git -C hermes-search-chain pull --ff-only
target="${HERMES_HOME:-$HOME/.hermes}/plugins/search-chain"       # or the directory of your row in the table above
mkdir -p "$target" && cp -r hermes-search-chain/search_chain/. "$target/"
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

`web.keyless_rescue` also applies to `web_extract`. With it on, a search that fails at every stage is served from anonymous free tiers, and neither the model nor this plugin's log line shows it.

Put the keys and addresses into the profile's `.env`. Every line is optional; a stage is switched on by its key or address:

```bash
EXA_API_KEY=...
PARALLEL_API_KEY=...
#BRAVE_SEARCH_API_KEY=...
#NIMBLE_API_KEY=...
#TAVILY_API_KEY=...
#YDC_API_KEY=...
#SEARXNG_URL=http://searxng.example:8080
#DEGOOG_URL=http://degoog.example:4444
#FIRECRAWL_API_KEY=...
```

The names are those of Hermes' built-in providers where Hermes has one (`BRAVE_SEARCH_API_KEY`, `TAVILY_API_KEY`, `SEARXNG_URL`). A key you already set for a built-in provider therefore switches the stage on without a second entry. The same holds for a key set for another purpose: `TAVILY_API_KEY`, which hermes-extract-chain also reads, switches on the Tavily search stage and spends its credits. Leave a stage out with `SEARCH_CHAIN_ORDER` (see *Settings*).

Restart Hermes (or the gateway).

**With Hermes' installer:**

```bash
hermes plugins install Pressimize/hermes-search-chain#search_chain --enable
```

It clones only the `search_chain` subdirectory, asks for the three keys of `requires_env` (Exa, Parallel, Firecrawl; you can skip them) and enables the plugin. The other keys and addresses go into the `.env` yourself, and the `web:` settings above are still needed. Enabling through Hermes' CLI also syncs Hermes' package environment; the manual route avoids that step.

**Check:** let the agent search for something. `logs/agent.log` in the Hermes home then shows a line per search, with the stages in the order used up to the one that ended the chain:

```text
search-chain: exa=ok
search-chain: exa=http_402 parallel=ok
search-chain: exa=paused parallel=ok
search-chain: exa=http_402 parallel=timeout brave=no_key nimble=no_key tavily=no_key youcom=no_key searxng=no_url degoog=no_url firecrawl=ok
```

The last line is long on purpose: it shows why each stage was not asked. When a pause starts, `logs/errors.log` gets a line such as `search-chain: exa paused for 86400 s (HTTP 402 NO_MORE_CREDITS)`.

## Settings

Optional settings in the profile's `.env`:

```bash
SEARCH_CHAIN_ORDER=exa,parallel,brave,nimble,tavily,youcom,searxng,degoog,firecrawl   # default
SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS=600   # default; 0 = Exa's own highlight length (about three times the text)
SEARCH_CHAIN_PARALLEL_API=v1           # unset (default): the call Hermes makes; v1 = /v1/search in mode advanced
```

**Order and choice of stages.** `SEARCH_CHAIN_ORDER` lists the stages to use, comma-separated, in the order they are asked: `exa`, `parallel`, `brave`, `nimble`, `tavily`, `youcom`, `searxng`, `degoog`, `firecrawl`. A stage left out is never asked, even if its key is set. Unknown and repeated names are dropped with one warning in the log; if no valid name is left, the default order is used. Examples:

```bash
SEARCH_CHAIN_ORDER=searxng,degoog                         # only your own instances, no paid service (they still query Google, Bing and others)
SEARCH_CHAIN_ORDER=searxng,exa,parallel,firecrawl         # privacy first: your own instance, then paid services
SEARCH_CHAIN_ORDER=exa,parallel,brave,nimble,youcom,searxng,degoog,firecrawl   # default without Tavily
```

If the order names only stages without a key or address, every search fails with `no stage configured`; it does not fall back to the default, so a service you left out never gets a query.

**Exa and Parallel.** Exa returns excerpts ("highlights") per result. Capped at 600 characters, a search of five results is about 4,000 characters instead of 12,000, with no loss of hits or answers in the tests (design D3). Set `0` to switch the cap off.

Parallel is called on its beta endpoint in mode `agentic`, exactly as Hermes' built-in provider does. `v1` moves the stage to the GA endpoint `/v1/search` in mode `advanced`; see the FAQ.

## Validation

Unit tests without network cover every rule of the chain, the provider calls and the settings. A live check of 0.2.0 through Hermes' real `web_search` path broke one stage after another with invalid keys or addresses, and each of the seven stages after Parallel served once. An end-to-end test with a model ran on 2026-10-10 with the three-stage chain of 0.1.x (36 questions, four setups, 144 runs through Hermes' real tool path): no failed run, and the intended stage served every search; with an invalid Exa key Parallel served, with invalid Exa and Parallel keys Firecrawl (then the third stage). Not verified: a really used-up quota (HTTP 402, Tavily's 432 and 433, and the 24-hour pause).

Setup, judging, all tables, limits and the external code reviews: [docs/validation.md](docs/validation.md). Questions, per-run results and answers: [`data/end-to-end/`](data/end-to-end).

## Update and uninstall

- **Update:** delete `plugins/search-chain/`, copy the new `search_chain/` in its place as in *Installation*, and restart Hermes. Do not run `cp -r search_chain` onto an existing `plugins/search-chain`: that puts the new copy one level deeper, into `plugins/search-chain/search_chain/`, and Hermes keeps loading the old files. After an install with `hermes plugins install`, use `hermes plugins update search-chain`. See [CHANGELOG.md](CHANGELOG.md).
- **Uninstall:**
  1. Delete `plugins/search-chain/`.
  2. Remove `search-chain` from `plugins.enabled`.
  3. Set `web.search_backend` back to your previous provider.
  4. Restart Hermes.

## Costs and quotas

The chain reacts to a service's reply; it does not know the remaining quota in advance. Whether a service answers HTTP 402 or charges a stored payment method when the free quota is used up depends on your account settings. For a hard cost cap, keep auto recharge off at Exa and Firecrawl and store no payment method you do not want charged. Brave needs a payment card even for its free credit, and charges $5 per 1,000 searches after it. The prices of all services are in *Requirements*. A key you set for another purpose switches its stage on (see *Installation*); `SEARCH_CHAIN_ORDER` keeps a service out.

Count which service answered:

```bash
grep -o "search-chain: .*" logs/agent.log | grep -o "[a-z]*=ok" | sort | uniq -c
```

## Limitations

- **Fixed set of services.** The nine services are built in; the order is a setting (`SEARCH_CHAIN_ORDER`). Another service needs a release.
- **No results is an error.** If no service finds anything, the model gets an error with `no results` instead of an empty list, because Hermes caches every successful result for `web.cache_ttl_minutes` (default 20).
- **Different result lengths.** In the comparison runs of 0.1.x, Exa (capped) returned about 4,000 characters per search, Parallel about 8,200, Firecrawl about 3,900 (extra block only); for the stages added in 0.2.0 no such figure is published. A title is cut at 300 characters and a description at 16,000; a description from Firecrawl is cut at 3,000. In the comparison 26 of Firecrawl's 400 descriptions (6.5 %) were longer than that; cutting them changed no verdict.
- **At most 20 results per search.** Hermes lets the model ask for up to 100; every service is asked for at most 20, because Exa bills each result above 10 extra.
- **Result texts are third-party content.** Titles and descriptions reach the model as the services send them, apart from the length bounds above. Hermes marks web search results as untrusted data; the plugin does not filter them.
- **Parallel's quota replies are not documented.** The chain moves on after any failure; only the 24-hour pause depends on the status code being 402.
- **After a restart** the first search asks every service again, including one with a used-up quota. Without a restart, a renewed or topped-up quota is used only after the 24-hour pause.
- **Privacy.** Every query is sent to the first stage that has a key or address, and possibly to the following ones. A key set for another purpose switches its stage on. `SEARCH_CHAIN_ORDER` keeps a service out or puts your own instance first.
- **Self-hosted search may return weaker hits without an error.** SearXNG and Degoog query Google, Bing and others from your own address. When these block it, the hits get worse but the reply is still valid, and the chain stops there. The plugin does not try to tell good replies from weak ones (design D18). A self-hosted stage late in the chain is asked rarely.
- **Redirects are not followed** for self-hosted addresses. Enter the address the instance answers on.
- **An address in an error page.** The full address of a self-hosted instance is masked if its reply echoes it. A part of it, for example only the host, is not.
- **Timeouts** are 10 s (Exa, Brave, You.com, Degoog) and 15 s (Parallel, Nimble, Tavily, SearXNG, Firecrawl) for each phase of a request (connect, send, wait for the reply), not for the search as a whole. A search in which every service runs into one timeout takes 115 s. It takes longer when a service is slow in several phases or sends its reply in a trickle, in the worst case about 460 s, beyond the 420 s after which Hermes ends a tool call by default. That needs all nine services to hang at once.

## FAQ

**Why not reuse Hermes' built-in providers?**
Exa, Parallel and Firecrawl need vendor SDKs that Hermes installs on first use. Calling the REST APIs directly needs nothing extra, gives exact status codes, and reaches Exa's highlight cap, which the built-in provider does not expose.

**Which Parallel endpoint, and why?**
The beta endpoint in mode `agentic`, the call Hermes 0.21.6 makes; it was never worse than `/v1/search` in two tests (design D2). If Parallel switches the beta endpoint off, set `SEARCH_CHAIN_PARALLEL_API=v1`.

**Does it merge or re-rank results from several services?**
No. A simulation on the comparison data showed no measurable gain from merging; all results of one search come from one service.

**Why not DonSeTch, Exa without a key, or Hermes' keyless ring?**
DonSeTch has only a command-line program and an MCP server over stdio, no HTTP interface. Exa's keyless endpoint answers as well as Exa with a key, but using it when a keyed quota is used up can be read as working around a limit, which Exa's terms forbid. Hermes' keyless ring as a whole finds fewer expected sites than Brave, and its Firecrawl part was rate-limited on 44 % of the queries. Details: design D21 and [docs/evaluation.md](docs/evaluation.md).

**Does it do page extraction?**
No. `web.extract_backend` is unaffected; see [hermes-extract-chain](https://github.com/Pressimize/hermes-extract-chain).

## Development

```bash
uv sync                                   # Python >= 3.11, httpx as in Hermes
uv run ruff check && uv run ruff format --check
uv run pytest
uv run python scripts/recompute.py         # recomputes the tables of runs 1 and 2 and the end-to-end test; the tests run it
```

| Path | Content |
|---|---|
| `search_chain/` | The plugin: `provider.py` (Hermes interface, chain, pauses), `engines.py` (REST clients) |
| `tests/` | Unit tests without network (`httpx.MockTransport`; Hermes is stubbed in `conftest.py`) |
| `scripts/recompute.py` | Recomputes the tables of runs 1 and 2 (evaluation) and of the end-to-end test (validation) from the CSV files in `data/` |
| `scripts/live_check.py` | Calls Hermes' real `web_search` path in a profile, without an LLM and with rate limiting; can break keys to force the fallback (`--break` covers all nine stages; for SearXNG and Degoog it replaces the address) |
| `docs/` | [evaluation](docs/evaluation.md) (provider choice, test method, results), [design](docs/design.md) (requirements and decisions with their reasons), [validation](docs/validation.md) (tests, reviews, end-to-end test with a model), [reviews](docs/reviews) (points settled in external reviews) |
| `data/` | Test data as CSV: queries, per-query results of both comparison runs, questions and answers of the end-to-end test ([description](data/README.md)) |
| `.github/workflows/ci.yml` | CI on pull requests and pushes to `main`: ruff and pytest on Python 3.11 and 3.14 |

`pyproject.toml` only configures the tooling and sits at the repository root because Hermes treats a plugin directory with a `pyproject.toml` as a package-manager member.

## Authors

- [Pressimize](https://github.com/Pressimize): idea, requirements and decisions.
- Claude, Anthropic's AI model, working in Claude Code: design, code, tests, evaluation and documentation.

## License

[MIT](LICENSE)
