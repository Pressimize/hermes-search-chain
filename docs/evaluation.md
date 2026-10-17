# Evaluation: how the providers were chosen

The chain Exa → Parallel → Firecrawl is the result of four steps taken on 2026-10-09 and 2026-10-10 with Hermes Agent 0.21.6:

1. **Run 1 – provider comparison:** seven search providers exactly as Hermes calls them, 60 queries, without an LLM.
2. **Run 2 – mode comparison:** the same providers (Firecrawl only on the 20 added queries) plus 13 variants that use better modes or parameters of their APIs, 80 queries, without an LLM.
3. **Simulation:** would merging the results of several providers help?
4. **End-to-end test with a model:** the finished plugin in four setups, 36 questions. It is described in [validation.md](validation.md).

Every query, every per-cell score and the first five result URLs of every search are in [`data/`](../data). Titles and snippets returned by the providers are not published.

## Method of runs 1 and 2

- **No LLM.** A script calls Hermes' own `web_search` tool function in a throwaway profile per provider. What is scored is exactly what a model would get: the first five results with title, URL and description.
- **Variants** that Hermes cannot produce are called directly over HTTP and brought into the same shape. Before run 2, the direct rebuild of each baseline call was compared with Hermes on three queries per provider; this found and fixed one real difference.
- **Same moment, limited rate.** All columns of a provider get a query within the same round; no provider gets more than eight requests per minute.
- **Queries and scoring** ([queries.csv](../data/provider-comparison/queries.csv)):

  | Category | Queries (main set + extra block) | Counted as correct when |
  |---|---|---|
  | official | 15 + 4 | the expected documentation page is among the first five results |
  | german | 5 + 2 | the same, for German-language sources |
  | niche | 5 + 8 | the same, for specialised topics |
  | error | 10 + 0 | the fix for an error message is in a result snippet |
  | fact | 10 + 0 | the fact is in a result snippet |
  | current | 10 + 6 | the current version of a project is in a result snippet (the version is fetched from GitHub right before the run) |
  | trap | 5 + 0 | not scored: invented versions, checked only for snippets that confirm them |

  The topics are self-hosting, system administration and developer tooling. That makes 55 scored queries in the main set and 20 in the extra block, which was added for run 2 because the main set separated the best providers too little.
- **Two scorings.** *Result list* counts only what is in the list. *With result pages* also accepts an error fix or a fact that is not in a snippet but on one of the five result pages (pages fetched separately). Run 1 was reported with result pages; run 2 is reported mainly by result list, because that is what the search provider controls.
- **Statistics.** Two columns are compared on the queries where exactly one of them is correct (paired sign test). The rules were fixed before run 2: p below 0.05 is called *firm*, a difference of three or more queries a *hint*, anything else *no detectable difference*. With 19 comparisons in one run, a single p just below 0.05 is expected by chance; only p below 0.003 survives a strict correction.

## Run 1 – seven providers as Hermes calls them (2026-10-09)

Calls: Exa via its SDK with highlights, Parallel via its SDK on the beta endpoint in mode `agentic`, Firecrawl via its SDK; the four providers outside the chain (TinyFish, Brave, Tavily, Keenable) in their default modes, see *Providers outside the chain*. Data: [run1-results.csv](../data/provider-comparison/run1-results.csv).

| | Exa | Parallel | Firecrawl |
|---|---|---|---|
| **Correct, of 55** (with result pages) | **55** | **53** | **53** |
| Correct, of 55, from the result list alone | 55 | 52 | 49 |
| official: found, of 15 (at rank 1) | 15 (14) | 15 (13) | 15 (14) |
| german: found, of 5 | 5 | 5 | 5 |
| niche: found, of 5 | 5 | 4 | 4 |
| error: fix in a snippet, of 10 | 10 | 9 | 6 |
| error and fact: with result pages | all | all | all |
| current: current version in a snippet, of 10 | 10 | 9 | 9 |
| current: snippet names only an older version | 0 | 1 | 0 |
| Time per search, median | 1.3 s | 3.7 s | 1.2 s |
| Characters per search, median | 11,100 | 7,700 | 3,500 |

No request failed and no provider returned an empty list.

**Paired against Exa** (queries only Exa got right : queries only the other got right): Parallel 2 : 0 and Firecrawl 2 : 0 (p 0.5, no detectable difference).

**What the numbers say**

- **Facts and error messages hardly separate the providers.** With the result pages, every provider gets all 20. The difference is whether the answer is already in the snippet: Exa and Parallel, with long snippets, deliver it there; Firecrawl, with short ones, needs a page fetch afterwards.
- **Official sources:** Exa, Parallel and Firecrawl find all 15, mostly at rank 1.
- **Freshness separates them most.** Exa names the current version in all ten snippets, including releases from the day before; Parallel and Firecrawl in nine. The four providers outside the chain often show an older version in the snippet. The result pages themselves almost always carry the current version, so a model that reads the page gets it right; a model that answers from the snippet does not.
- **Traps:** the pattern check flagged two snippets (Exa and TinyFish for "Hermes Agent v0.35"). Read by hand, neither presents an invented version as real: both are genuine hits for another project with a similar name that does have a v0.35. That is a risk of confusion for a model, not an error of the search.
- **Context cost differs widely:** about 3,000 tokens per search with Exa and Keenable, about 500 with TinyFish and Brave (at roughly four characters per token).

## Run 2 – better modes of the same providers (2026-10-10)

Hermes calls every provider in a simple mode. Run 2 repeated the baselines and added variants, each compared with its own baseline in the same run. Columns and their exact calls: [columns.csv](../data/provider-comparison/columns.csv); results: [run2-results.csv](../data/provider-comparison/run2-results.csv). Firecrawl ran only on the extra block, to save its small free allowance: it has no variant to compare, and its main-set results are in run 1.

**Baselines**

| | Exa | Parallel | Firecrawl |
|---|---|---|---|
| **Correct, of 75** (result list) | **73** | **72** | 65 \* |
| Main set, result list, of 55 | 54 | 54 | not run |
| Main set, with result pages, of 55 | 54 | 55 | not run |
| For comparison: run 1, with result pages | 55 | 53 | 53 |
| For comparison: run 1, result list | 55 | 52 | 49 |
| Extra block, of 20 | 19 | 18 | 16 |
| current version in a snippet, both sets, of 16 | 16 | 16 | 6 of 6 |
| Characters per search, median (main set) | 12,000 | 8,200 | 3,900 (extra block) |

\* Firecrawl has no figure of 75 from one run. The 65 is 49 of the 55 (result list, run 1) plus 16 of the 20 on the extra block (run 2). Counted the same way, the baseline calls of Exa and Parallel reach 74 and 70. Because of the day-to-day variation described below, a figure put together from two days is less exact than one from a single run.

- **The order stays.** Exa and Parallel lead, Firecrawl follows on the block it ran, then the four providers outside the chain with a clear gap.
- **The extra block separates what the main set did not:** the top three stay at 16 to 19 of 20, the other four fall to 6 to 11.
- **Day-to-day variation:** between run 1 and run 2, up to 8 of the 45 non-version queries changed per provider. The same baseline call repeated an hour later returned a different list in 4 of 18 cases. A difference of two to four queries between two columns is therefore noise.
- **Traps:** four flags, read by hand. Three are the v0.35 of the other project again (all three Exa columns); one matched a date on a release-history page (Parallel `/v1/search`, `advanced`). No snippet presented an invented version as real.

**Variants against their baseline** (both sets, 75 queries, result list; pairs = queries only the variant got right : only the baseline). Variants of the other four providers: *Providers outside the chain*.

| Variant | Correct, of 75 | Baseline | Pairs | Verdict by the rules | Characters per search (baseline) | Time per search, median (baseline) |
|---|---|---|---|---|---|---|
| Exa, highlights capped at 600 characters | 74 | 73 | 1 : 0 | no detectable difference | 4,000 (12,000) | 0.6 s (2.0 s) |
| Exa, `type: instant` | 66 | 73 | 0 : 7 | worse, p 0.016 | 13,500 (12,000) | 0.6 s (2.0 s) |
| Parallel, beta endpoint, mode `fast` | 71 | 72 | 1 : 2 | no detectable difference | 15,700 (8,200) | 1.1 s (2.9 s) |
| Parallel, `/v1/search`, mode `advanced` | 70 | 72 | 0 : 2 | no detectable difference | 8,400 (8,200) | 1.8 s (2.9 s) |
| Parallel, `/v1/search`, mode `fast` | 49 | 72 | 1 : 24 | worse, p below 0.001 | 9,300 (8,200) | 0.8 s (2.9 s) |
| Parallel, `/v1/search`, `fast` with an intent sentence as `objective` | 55 | 72 | 1 : 18 | worse, p below 0.001 | 8,000 (8,200) | 0.8 s (2.9 s) |

The times of variants called directly and of baselines called through Hermes are not strictly comparable; see the note on Parallel below.

**What this means per provider**

- **Exa.** Capping the highlights keeps the hits and the current versions (74 against 73) at a third of the text and the same price. `instant` is cheaper and loses seven queries without winning one, in the same direction in both sets.
- **Parallel.** Only one result is firm under strict correction: mode `fast` on `/v1/search` is a different product from `fast` on the beta endpoint. It loses on version questions (0 : 15), documentation (0 : 5) and niche topics (0 : 3). Three direct calls per case to both endpoints confirmed that the difference lies in the service. `advanced` on `/v1/search` is close to the beta call (70 against 72). It looked faster here (1.8 s against 2.9 s), but it was called directly and the beta call through Hermes; inside Hermes, in the end-to-end test, both took about 3 s.

## Providers outside the chain

TinyFish, Brave, Tavily and Keenable were measured in both runs and with their variants. None made the chain. Same rows as the tables above, with the cost figures of the free-tier table.

| | TinyFish | Brave | Tavily | Keenable |
|---|---|---|---|---|
| **Run 1: correct, of 55** (with result pages) | 50 | 46 | 41 | 40 |
| Run 1: correct, of 55, from the result list alone | 46 | 42 | 40 | 40 |
| official: found, of 15 (at rank 1) | 15 (13) | 13 (12) | 11 (3) | 10 (7) |
| german: found, of 5 | 5 | 5 | 5 | 3 |
| niche: found, of 5 | 5 | 4 | 4 | 3 |
| error: fix in a snippet, of 10 | 6 | 6 | 9 | 10 |
| current: current version in a snippet, of 10 | 5 | 4 | 1 | 4 |
| current: snippet names only an older version | 4 | 6 | 9 | 6 |
| Time per search, median | 1.3 s | 1.0 s | 2.3 s | 0.3 s |
| Characters per search, median | 1,900 | 2,500 | 7,000 | 12,200 |
| **Run 2: correct, of 75** (result list) | 54 | 53 | 50 | 50 |
| Main set, result list, of 55 | 43 | 43 | 39 | 44 |
| Main set, with result pages, of 55 | 47 | 46 | 41 | 44 |
| Extra block, of 20 | 11 | 10 | 11 | 6 |
| current version in a snippet, both sets, of 16 | 6 | 5 | 5 | 4 |
| Characters per search, median (main set) | 1,850 | 2,500 | 7,050 | 11,800 |
| Counted like Firecrawl's 65 (run 1 result list plus extra block) | 57 | 52 | 51 | 46 |
| Price per search | free | $5 per 1,000 | 1 credit (`basic`), 2 (`advanced`) | not priced per search |
| Free allowance | 12,000 searches per day | $5 of credits per month, credit card required | 1,000 credits per month, shared with extraction | 100,000 requests per month, shared with fetching |
| Rate limit | 30 per minute | 50 per second | not stated | 10 per second |

- **Against Exa in run 1** (queries only Exa got right : only the other): TinyFish 5 : 0 (p 0.06), Brave 9 : 0 (p 0.004), Tavily 14 : 0 and Keenable 15 : 0 (p below 0.001).
- **Sources:** Tavily often returns forum threads and issues instead of the documentation (3 at rank 1). Keenable often returns guide and mirror sites.
- **Variants** (75 queries, against their baseline in the same run): Tavily `search_depth: advanced` (52 against 50, 10 : 8, twice the price), Keenable with snippets capped at 600 characters (48 against 50, 0 : 2) and Brave with extra snippets (54 against 53) show no detectable difference.
- **Brave, LLM Context endpoint:** better with a lean token budget (62 against 53, 13 : 4, p 0.049; 61 with the default budget). It names the current version in 14 to 15 of 16 version questions (web search: 5) and puts the fix into the snippet for all ten error messages (web search: 7). It finds the official documentation less often, and without the version questions it stands 4 : 4. Even with it, Brave stays behind Exa and Parallel.
- **TinyFish's `purpose`** could not be measured: the variants sent the same query 7.5 to 15 s after the baseline, and the service answered from a cache that ignores `purpose` (median 0.6 s instead of 2.3 s, identical lists). A separate probe with fresh queries and opposite purposes showed no visible redirection of the results.

## Simulation – would merging several providers help?

Before run 2, a script merged the stored result lists of run 1 offline (reciprocal rank fusion over the first five results of each provider, duplicates joined by URL, best five kept) and scored the merged list like a provider.

| Combination | Single scores, of 55 | Upper bound (any one correct) | Merged, snippet of the best rank | Merged, snippets joined | Characters per search, joined (median) |
|---|---|---|---|---|---|
| TinyFish + Parallel | 50 / 53 | 55 | 49 | 54 | 6,175 |
| TinyFish + Firecrawl | 50 / 53 | 54 | 49 | 53 | 3,469 |
| Parallel + Firecrawl | 53 / 53 | 54 | 52 | 53 | 7,995 |
| TinyFish + Parallel + Firecrawl | 50 / 53 / 53 | 55 | 50 | 55 | 8,205 |
| TinyFish + Brave | 50 / 46 | 50 | 45 | 46 | 2,658 |
| all seven | best 55 | 55 | 49 | 55 | 17,634 |

- **No firm gain.** TinyFish + Parallel against Parallel alone: two queries won, one lost. Exa alone already had all 55.
- **Not recomputable from `data/`:** the simulation worked on the stored titles and snippets, which are not published. Only the single scores and the upper bounds can be recomputed.
- **The order does not get better.** After merging, the expected page is at rank 1 as often as with the best single provider.
- **The gain comes from joined snippets, not from ranking:** where one provider's snippet shows an old version and another's the current one, joining keeps the current one. Taking only the snippet of the best-ranked copy loses it.
- **Weak providers hurt.** TinyFish + Brave scores below TinyFish alone, because Brave results push good ones out of the first five.
- **Cost:** every search uses quota at every provider and takes as long as the slowest.

Only 21 of the 55 queries separated the providers at all, and only five results per provider were stored, so a selection step over more candidates could not be simulated. On this evidence, merging and a model that picks results solve a problem the measurements do not show. The plugin therefore chains providers and does not merge.

## Free tiers and costs

As read on the vendors' pages on 2026-10-09 and 2026-10-10; check them before relying on them. Hermes asks a provider for 10 results even when the model wants 5.

| Provider | Price per search as called | Free allowance | Free searches per month, roughly | Rate limit |
|---|---|---|---|---|
| Exa | $7 per 1,000 with up to 10 results, highlights included (the reply's `costDollars` showed $0.007) | $10 of credits, reset on the first of each month | 1,400 | 10 per second |
| Parallel | $1 to $5 per 1,000 by mode (`advanced` $5); the beta mode `agentic` is no longer priced in the documentation | 5,000 requests per month according to the pricing page; the pricing documentation does not mention a free allowance | up to 5,000 | 600 per minute |
| Firecrawl | 2 credits per 10 results | 1,000 credits per month, shared with scraping | 500 | 10 searches per minute on the free plan |

## Decision

- **Exa first.** Best or tied for best in both runs (run 1, with result pages: 55 of 55; run 2, result list: 73 of 75), with the current version in the snippet for all 16 version questions of run 2. With highlights capped it returns about half the text of Parallel for the same hits (about as little as Firecrawl), and inside Hermes it was the faster of the two (1.8 s against 3.0 s per search, [validation.md](validation.md)). Being first, it is also the first to use up its free allowance, which is smaller than Parallel's; the chain then carries on with Parallel.
- **Parallel second.** Not distinguishable from Exa on the hits (run 1, with result pages: 53 of 55; run 2, result list: 72 of 75), also 16 of 16 on current versions, with the largest free allowance of the three. It is called on the beta endpoint in mode `agentic`, as Hermes does: this call was never worse than `/v1/search` in two tests ([design.md](design.md), D2).
- **Firecrawl third.** In run 1 it got 49 of 55 from the result list (Exa 55, Parallel 52) and 53 of 55 with result pages (Exa 55, Parallel 53), on the extra block 16 of 20 (Exa 19, Parallel 18), with the current version in all six of its version questions there. Against Exa in run 1, Exa alone was right on 6 queries from the result list (p 0.03: below 0.05, but far from the 0.003 of the strict correction) and on 2 with result pages (p 0.5). Four of its six misses from the result list are error messages whose fix is only on the result page: its snippets are short. From the result list it scored lowest of the three, and it is ahead of the other four. Its free allowance is the smallest of the three and shared with scraping, so the chain spares it: it is the last resort.
- **Not in the chain:** TinyFish is free and finds official documentation well, but its snippets often show an older version (6 of 16 current in run 2), and it falls behind on the harder block (11 of 20). Brave improves a lot with the LLM Context endpoint but stays behind the top three and needs a credit card. Tavily and Keenable often miss the official source and show old versions.
- **No merging and no model in the plugin** (simulation above).
- **Highlights capped at 600 characters** (run 2; confirmed with a model in [validation.md](validation.md)).

## Limits of this evaluation

- One run per configuration, two days, 75 scored queries on technical topics, mostly in English. Only large gaps are firm; the ranking within the top three is not.
- Providers change their indexes and defaults; the numbers describe October 2026.
- Run 1 and run 2 measure the result list, not what a model makes of it. The end-to-end test in [validation.md](validation.md) does, on a smaller set.
- TinyFish's `purpose` was not measured (cache, see above).
- Prices and free allowances are vendor statements, partly contradictory (Parallel), and were not exhausted in a test.

## Data files

Every query, score and result is in [`data/`](../data); the files and their columns are described in [`data/README.md`](../data/README.md). [`scripts/recompute.py`](../scripts/recompute.py) recomputes the totals, the paired comparisons and their p values in this document from them.
