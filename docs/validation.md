# Validation

How the plugin was checked against [design.md](design.md). Requirement IDs refer to that document. Why these providers were chosen is in [evaluation.md](evaluation.md).

| Check | Result |
|---|---|
| T1 Unit tests | nothing leaves the machine |
| T2 Live check through Hermes | Exa serves; with broken keys each of the seven stages after Parallel serves once (0.2.0) |
| T3 Reviews | two reviews against the design, findings fixed; three external code reviews of v0.1.0, adopted in v0.1.1; a review by seven models and a mutation run before v0.1.2; for 0.2.0 reviews of the specification, the plan and the code, and a mutation run |
| T4 Lint and CI | clean; Python 3.11 and 3.14 |
| T5 End-to-end test with a model | 0.1.0: 144 runs without a failure; 34 to 36 of 36 answers correct in every setup |
| Not verified | a really used-up quota (HTTP 402, Tavily's 432/433, and the 24-hour pause) |

## T1 – Unit tests

`uv run pytest` runs the unit tests with `httpx.MockTransport`; Hermes is replaced by a stand-in with the same abstract members. They cover every branch of the chain (K2–K7), including all stages paused or without a key, `register(ctx)` and `plugin.yaml` (S1), the properties and `is_available` (S2), keys absent from results and logs (S3), no exception escaping (S5), the pauses with an injected clock (K5), both Parallel calls and both settings (A1, A2), error texts, key masking and timeouts (A0, A4), the result shape, the URL rule and the text bounds (S4), the bounds of `limit` (A6), interrupts (S6), the proxy variables (A5) and the log lines (L1, L2). Since 0.2.0 also every request and reply shape of the six added stages (A7–A12), the address rules of the self-hosted stages (A13), the order setting with its warning (K8), the error text without unconfigured stages (K6) and the pauses per address and after 432/433 (K5).

## T2 – Live check through Hermes

`scripts/live_check.py` calls Hermes' real `web_search` tool function in a profile with the plugin installed, without a model. Run on 2026-10-10 with Hermes Desktop 0.21.6:

| Mode | Log line of the plugin | Rows | Time per search |
|---|---|---|---|
| three queries, keys as configured | `exa=ok` | 5 each | 1.6 to 6.3 s |
| `--break exa` (invalid Exa key in the process), two queries | `exa=http_401 parallel=ok` | 5 each | 2.7 and 2.8 s |
| `--break exa,parallel`, one query | `exa=http_401 parallel=http_401 firecrawl=ok` | 5 | 2.7 s |

An invalid key (HTTP 401) starts no pause, so every call tries the stage again; that is intended (design D4).

**0.2.0**, run on 2026-10-19 with Hermes Desktop 0.21.6 in a throwaway profile with keys for all seven keyed services and local SearXNG and Degoog instances (the containers of the benchmark), one query per row, the stages broken one after another with `--break`:

| `--break` | Log line of the plugin (stages before the serving one) | Rows | Time |
|---|---|---|---|
| none | `exa=ok` | 5 | 2.5 s |
| `exa,parallel` | `exa=http_401 parallel=http_401 brave=ok` | 5 | 2.6 s |
| + `brave` | `... brave=http_422 nimble=ok` | 5 | 3.4 s |
| + `nimble` | `... nimble=http_401 tavily=ok` | 5 | 4.4 s |
| + `tavily` | `... tavily=http_401 youcom=ok` | 5 | 3.2 s |
| + `youcom` | `... youcom=http_403 searxng=ok` | 5 | 3.6 s |
| + `searxng` (address with nothing listening) | `... searxng=ConnectError degoog=ok` | 5 | 5.8 s |
| + `degoog` | `... degoog=ConnectError firecrawl=ok` | 5 | 8.3 s |

Each stage served once through Hermes' real tool path. An invalid key gives HTTP 401 at Exa, Parallel, Nimble and Tavily, HTTP 422 at Brave and HTTP 403 at You.com; none of these starts a pause.

## T3 – Reviews

- **Plan against design, before coding.** Taken over: no empty success (K6), pauses only after HTTP 402 and 429 (K5), and a live check that refuses to run while the keyless rescue is on.
- **Code against design, after coding,** by an independent reviewer who also ran 21 single-line mutations of the code against the tests (19 caught). It found one real bug (a setting value longer than Python's integer-parsing limit failed the whole call) and three gaps (results without a URL counted as hits; two untested boundaries). All four are fixed and tested.
- **Smoke test against the real Hermes classes** (Hermes Desktop 0.21.6, Python 3.14): the provider instantiates against the real base class, reads keys through Hermes, and returned ten rows in the required shape from a live Firecrawl search.
- **Documents and data before publication:** a reviewer recomputed the tables of this document and of evaluation.md from the CSV files and checked the decisions for traceable reasons; the mismatches found were corrected.
- **Three external code reviews of v0.1.0** (2026-10-10 and 2026-10-11), each by an independent reviewer: no critical defect, 52 findings, many of them shared. Each was checked against the code, against Hermes 0.21.6 and, where it claimed a cost, against a measurement. What was reproduced and adopted is in the [changelog of 0.1.1](../CHANGELOG.md); the bounds on result texts were checked on the stored results of both comparison runs (D12); what was declined is in D13–D16.
- **Review of the v0.1.1 change itself:** plan and code were reviewed (23 mutations, 20 caught, tests added for the other three), and a further reviewer compared the documents with the code. A key that cannot be encoded would have stopped the whole chain instead of its own stage; that was fixed and tested before the release.
- **Before v0.1.2:** a review by seven free models and Claude, every point checked against the code ([reviews/2026-10-17.md](reviews/2026-10-17.md)); a mutation run with mutmut 3.3.1, whose 18 surviving mutants were 9 equivalent ones and 9 test gaps, now closed; and v0.1.1 and v0.1.2 run side by side on 4,101 simulated replies: the requests were identical, and every difference in the results is in the [changelog of 0.1.2](../CHANGELOG.md) except one blank-reason case it found, which was fixed.

## T4 – Lint and CI

`ruff check` and `ruff format --check` are clean. GitHub Actions runs both and the tests on Python 3.11 and 3.14, for pull requests and for pushes to `main`. The tests include a run of `scripts/recompute.py` (`tests/test_recompute.py`); the script recomputes the tables, and CI checks that it runs, not the figures.

## T5 – End-to-end test with a model

**Question.** Does the plugin work when a model drives it, does capping Exa's highlights cost answers or cause more page fetches, and does it matter which Parallel endpoint is called?

**Setup** (2026-10-10, Hermes Desktop 0.21.6)

- **Four setups**, one throwaway profile each, identical except for the search:

  | Setup | Search |
  |---|---|
  | Exa capped | this plugin, Exa with highlights capped at 600 characters |
  | Exa uncapped | this plugin, `SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS=0` |
  | Parallel `/v1/search` | this plugin without an Exa key, Parallel stage on `/v1/search` in mode `advanced` |
  | Parallel beta, built-in | Hermes' built-in Parallel provider: beta endpoint, mode `agentic` |

  When the test ran, the plugin's Parallel stage still called `/v1/search`. Because the beta call did at least as well, the plugin now uses it by default (design D2); that default was then checked live with two questions (`exa=no_key parallel=ok`, both correct).
- **Model:** GLM 5.3, a general-purpose language model, served through Mistral's API, with reasoning effort `high`; toolsets `web` and `file`; at most 12 steps; memory off. Pages are read through [hermes-extract-chain](https://github.com/Pressimize/hermes-extract-chain) in all setups.
- **Questions:** 36 in German with a known solution ([questions.csv](../data/end-to-end/questions.csv), with English translations): 10 facts, 10 error messages, 16 "latest released version of X", the version fetched from GitHub right before the run. The instruction asked the model to research on the web, not to answer from memory, to answer in at most three sentences and to name its source. It set no limit on searches.
- **Procedure:** one round per question with all four setups at the same time, rounds at least 120 s apart, one run per cell, 144 runs. After each round the runner counted the requests per provider from the logs.
- **Judging:** two judges scored all 144 answers independently against the solution, in shuffled order and without knowing the setup. They agreed on every answer. The 40 answers to error messages were also read by the test's author. A machine check (pattern for facts, version number for version questions) ran alongside and differs from the judges in one cell, noted below.
- **Rules fixed before the run:** for each of three pairs, count the questions only one setup got right. A difference below three is *no detectable difference*, from three a *hint*, and *firm* only if a sign test is below p 0.017.

**Answers** ([results.csv](../data/end-to-end/results.csv), [answers.csv](../data/end-to-end/answers.csv); [`scripts/recompute.py`](../scripts/recompute.py) recomputes the tables below from them)

| | Exa capped | Exa uncapped | Parallel `/v1/search` | Parallel beta, built-in |
|---|---|---|---|---|
| Correct, of 36 | 36 | 36 | 34 | 36 |
| Facts, of 10 | 10 | 10 | 9 | 10 |
| Error messages, of 10 | 10 | 10 | 10 | 10 |
| Version questions, of 16 | 16 | 16 | 15 | 16 |
| Failed runs, runs cut off at the step limit | 0 | 0 | 0 | 0 |
| Answered without searching | 0 | 0 | 0 | 0 |
| Searches served by another stage than intended | 0 | 0 | 0 | – |

The two wrong answers, both with Parallel on `/v1/search`:

- **Latest version of Home Assistant Core:** the answer named 2026.10.0; 2026.10.1 had been released on the day of the run. The other three setups fetched a page (PyPI or GitHub) and got it right; this one searched twice and fetched nothing. The same query had already been missed by `/v1/search` in run 2 of the evaluation.
- **SSH port for restic over SFTP on a Hetzner Storage Box:** the answer recommended port 22 and named port 23 only as an addition; the solution fixed beforehand is port 23. The answer is defensible in substance, and the machine check counts it as correct because "port 23" occurs.

| Pair | Only A correct | Only B correct | Verdict by the rules |
|---|---|---|---|
| A Exa capped, B Exa uncapped | 0 | 0 | no detectable difference |
| A Parallel `/v1/search`, B Parallel beta | 0 | 2 | no detectable difference |
| A Exa capped, B Parallel beta | 0 | 0 | no detectable difference |

**Effort and speed** (median per question; sums over all 36 questions where that says more)

| | Exa capped | Exa uncapped | Parallel `/v1/search` | Parallel beta, built-in |
|---|---|---|---|---|
| Searches, sum | 43 | 41 | 48 | 44 |
| Page fetches, sum | 11 | 9 | 9 | 10 |
| Characters per search result | 3,672 | 6,481 | 7,900 | 8,128 |
| Input tokens per question | 9,560 | 12,028 | 12,004 | 11,133 |
| Input tokens, sum | 430,606 | 484,082 | 497,072 | 494,759 |
| Time per search | 1.8 s | 2.0 s | 3.3 s | 3.0 s |
| Time to the answer | 8.5 s | 8.0 s | 8.9 s | 9.2 s |
| of which model time | 5.3 s | 5.1 s | 5.2 s | 5.2 s |

- *Time per search* runs from the model's tool call to the result, taken from the session's message timestamps, for steps with exactly one search. The plugin's own log times agree (1.8, 1.9 and 3.3 s).
- *Input tokens* include tokens served from the model provider's prompt cache. About 7,000 per question are system prompt and tool descriptions in every setup.

Input tokens by kind of question (sum):

| | Exa capped | Exa uncapped | Parallel `/v1/search` | Parallel beta, built-in |
|---|---|---|---|---|
| Facts | 98,516 | 101,243 | 103,445 | 106,172 |
| Error messages | 99,936 | 150,114 | 141,979 | 143,538 |
| Version questions | 232,154 | 232,725 | 251,648 | 245,049 |

**What it shows**

- **The plugin works in the real tool path.** No failed run, no run cut off, the intended stage served every search, and no provider got more than five requests in any minute.
- **The answers are at the ceiling.** The model often knows facts and fixes already, and for versions it fetches a page when in doubt. Good search setups therefore differ in effort, not in correctness, and 36 questions with one run each would only show large differences.
- **The cap costs no answer and saves 11 % of the input tokens,** almost all of it on error messages (33 % less), where Exa's own highlights are long (median 18,800 characters per search result against 4,300 with the cap). For facts and versions Exa's highlights are short anyway. The worry that short highlights cause more page fetches is not clearly confirmed: 11 against 9 fetches, in four questions only the capped setup fetched a page, in two only the uncapped one.
- **`/v1/search` brings no measurable advantage over the beta call:** the same tokens, the same speed (medians 3.3 s and 3.0 s; the median of the differences per question is 0.1 s), and two wrong answers against none. In run 2 of the evaluation it also stood 0 : 2 (70 against 72 of 75). Pooling the two tests, which differ in size and in who writes the queries, gives four queries in the same direction out of 111 comparisons (sign test p 0.125): a hint, not proof.
- **Exa capped against the built-in Parallel call:** equally good answers, the search faster in 20 of 25 comparable questions (median 1.1 s), the input smaller in 31 of 36 questions (13 % in total). The time to the answer drops by 0.7 s in the median; the model takes about 5 s per question and dominates the wait.

**Requests and consumption** over smoke test, fallback check and main run, counted from the logs: Exa 91 requests (3 of them rejected because of an invalid key), Parallel 101 (1 rejected), TinyFish 41 pages, Firecrawl 1 search. Highest rate in any 60 s: Exa 4, Parallel 5, TinyFish 4.

**Limits**

- One model, one run per cell, 36 questions.
- The model writes its own search queries in every setup; a difference of one or two questions can come from that.
- Every run is a new process with a fresh connection to the provider, so the time per search is higher than in a long-running gateway. The comparison between the setups is not affected: same conditions, same moment.
- Firecrawl as third stage ran only in the fallback checks.
- Judging follows the solution fixed beforehand; for the Hetzner port that is stricter than the matter.
- Request counts, rates and log times come from the runs' logs, which are not published.

## Not verified

A really used-up quota: the HTTP 402 reply (and Tavily's 432 and 433) and the 24-hour pause are covered by unit tests only. For 0.2.0 also unverified: how Brave reports a used-up monthly credit (most likely HTTP 429 with `QUOTA_LIMITED`, which pauses Brave for a minute), and Nimble's error bodies, which Nimble does not document. Exa documents the reply (`NO_MORE_CREDITS`); Parallel does not document its reply at all. Expected in use, not observed so far: `exa=http_402 parallel=ok` once, then `exa=paused parallel=ok`.
