# Data

The measurements behind [docs/evaluation.md](../docs/evaluation.md) and [docs/validation.md](../docs/validation.md), as CSV files (UTF-8, comma-separated, one header line).

`python scripts/recompute.py` recomputes the headline tables of both documents from these files.

**Not published:** the titles and snippets the search providers returned, and the pages fetched for the "with result pages" scoring. They are third-party content. Published are the queries, the URLs of the first five results, sizes, times and scores.

**Changed for publication:** in one error message used as a query, a user name inside a file path was replaced by `user` (`/home/user/.ssh/id_ed25519`). The query sent in the tests contained the original name. Column names of the original runs were translated into English.

## `provider-comparison/`

Seven search providers on the same queries without an LLM, 2026-10-09 (run 1) and 2026-10-10 (run 2).

| File | Rows | Content |
|---|---|---|
| `queries.csv` | 80 | `id`; `set` (`main`: the 60 queries of both runs, `extra`: 20 harder ones added for run 2); `category`; `query`; `scoring` (how a result counts as correct); `expected` (regular expression for the expected URL or answer, or the source of the current version); `evidence_url` (page on which the expected answer was verified beforehand); `intent_sentence` (used only by the `purpose`/`objective` variants) |
| `columns.csv` | 20 | the columns of run 2: `column`; `provider`; `variant_of` (empty for a baseline); `path` (through Hermes or direct HTTP call); `call` |
| `run1-results.csv` | 420 | one row per query and provider, see below |
| `run2-results.csv` | 1,540 | one row per query and column; `run` is `run2-main` or `run2-extra` |

Columns of the result files:

| Column | Meaning |
|---|---|
| `correct_from_result_list` | 1 or 0, judged from the first five results alone; empty for trap queries |
| `correct_with_result_pages` | 1 or 0, also accepting an error fix or fact found only on a result page; pages were fetched for the main set only |
| `detail` | what was found: the rank of the expected URL, the rank of the snippet with the answer, or for version queries what the snippets and the result pages showed |
| `chars` | size of the result as the model would get it (JSON with five results) |
| `seconds` | duration of the search call |
| `first_five_urls` | URLs of the first five results, separated by spaces |

For `trap` queries, `detail` says whether a snippet matched the pattern of the invented version. Every such flag was read by hand; none turned out to present an invented version as real (see docs/evaluation.md).

The merging simulation in docs/evaluation.md worked on the unpublished snippets and cannot be recomputed from these files.

Categories: `official` (documentation page expected), `german` (German-language source expected), `niche` (specialised topic, source expected), `error` (fix for an error message), `fact`, `current` (latest version of a project), `trap` (invented version; not scored).

## `current-versions.csv`

The latest release of each project in the `current` queries, fetched from GitHub (one from endoflife.date) right before each run (`run1`, `run2-main`, `run2-extra`, `end-to-end`): `run`, `id`, `source`, `current`, `previous`, `release_date`, `fetched_at`.

## `end-to-end/`

The plugin driven by a model, 2026-10-10: 36 questions, four setups, one run each.

| File | Rows | Content |
|---|---|---|
| `questions.csv` | 36 | `id`; `category`; `question_de` (as asked); `question_en` (translation); `solution_en` (what a correct answer must contain) |
| `results.csv` | 144 | one row per question and setup: `verdict` of the blind judges (`correct`, `wrong`); `machine_check` (pattern or version-number match, empty for error messages); `searches`; `page_fetches`; `model_steps`; `input_tokens` (including cached tokens); `output_tokens`; `search_result_chars_median`; `search_seconds_median` (steps with exactly one search); `total_seconds` (first to last message); `model_seconds`; `served_by` (stage that delivered each search); `started_at` |
| `answers.csv` | 144 | `id`; `setup`; `verdict`; `answer_de` (the model's final answer, in German as given) |

Setups: `exa-capped` and `exa-uncapped` (this plugin with and without the highlight cap), `parallel-v1` (this plugin without an Exa key, Parallel on `/v1/search`), `parallel-beta-builtin` (Hermes' built-in Parallel provider).
