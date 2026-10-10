# Plan: `search-chain` v0.1.0

Working plan for the first version. It implements [design.md](design.md); IDs refer to it. This file is removed before the repository is published.

## Layout

| Path | Content |
|---|---|
| `search_chain/__init__.py` | `register(ctx)` (S1) |
| `search_chain/plugin.yaml` | manifest (S1) |
| `search_chain/engines.py` | REST calls and row mapping for Exa, Parallel, Firecrawl (A0–A4, A6); usable without Hermes |
| `search_chain/provider.py` | Hermes interface (S2–S6), chain and pauses (K1–K7), logging (L1, L2), client (A5) |
| `tests/conftest.py` | stand-in for `agent.web_search_provider` |
| `tests/test_engines.py` | A1–A4, A6 |
| `tests/test_provider.py` | S1–S6, K1–K7, A5, L1, L2 |
| `scripts/live_check.py` | T2 |
| `pyproject.toml`, `uv.lock`, `.github/workflows/ci.yml` | tooling only (I3, T4) |
| `README.md`, `CHANGELOG.md`, `LICENSE` | user documentation |

## Steps

1. **Scaffold.** `pyproject.toml` (httpx pinned as in Hermes, dev group pytest/pyyaml/ruff, ruff rules as in `hermes-extract-chain` without `ASYNC`), `.gitignore`, `.gitattributes`, CI workflow, `LICENSE`.
2. **`engines.py`.**
   - Constants: URLs, timeouts (A0), `ERROR_MAX = 200`, `PARALLEL_MAX_RESULTS = 20`, `EXA_HIGHLIGHT_CHARS = 600`.
   - One function per provider: `exa(client, query, limit, key, highlight_chars)`, `parallel(client, query, limit, key)`, `firecrawl(client, query, limit, key)`.
   - Return value: `{"rows": [...]}` on a valid reply (possibly empty), else `{"error": "<Provider>: <text>", "code": "<code>", "status": <int or None>}`. Never raises (S5).
   - Shared helpers: `_post` (request, status check, JSON), `_detail` (A4), `_error` (cut, key masking), `_row` (S4 key order).
3. **`provider.py`.**
   - `_env(name)` as in the sibling plugin (S3); `_highlight_chars()` parses the setting (A1).
   - `SearchChainProvider(transport=None, clock=time.monotonic)`; `name`, `display_name`, `is_available`, `supports_search`, `supports_extract` (S2).
   - `search(query, limit=5)`: outer `try` so nothing escapes (S5); interrupt before the first stage (S6); `httpx.Client` per call (A5); loop over the stages (K1) with skip rules (K2), end on rows (K3), move on otherwise (K4), pause on status (K5), result at the end (K6); one INFO line in `finally` (L1); WARNING when a pause starts (L2).
   - Pause table `{(stage, key): until}` on the instance (K5).
4. **`plugin.yaml`, `__init__.py`** (S1).
5. **Tests (T1)**, one test or parametrised case per item:
   - `test_engines.py`: request URL, headers and body per provider; highlight cap values (600 default, custom, 0); Parallel cap at 20; row mapping and key order; missing fields; non-2xx with `tag` / `error` / `message` / plain text; Firecrawl `success: false`; timeout; transport error; malformed JSON; non-dict JSON; text cut to 200; key masked.
   - `test_provider.py`: manifest and `register`; properties; `is_available` for 0, 1 and 3 keys and for a raising key lookup; Exa serves (one request); Exa error → Parallel; Exa and Parallel error → Firecrawl; empty reply moves on; all empty → success with empty list; mixed empty and error → success with empty list; all fail → failure text with all reasons; no keys → failure; missing key skipped without request; pause after 402, 401, 403 (3,600 s) and 429 (60 s); no pause after 500 or timeout; paused stage skipped without request; pause ends (injected clock); pause per key; interrupt before the first stage and between stages; exception inside the chain becomes a failure; key never in result or log; INFO and WARNING lines.
6. **`scripts/live_check.py` (T2).** Modelled on the sibling's script: loads Hermes for one profile, asserts the search backend and the loaded plugin, calls `web_search_tool`, prints one line per query (stage outcomes, number of rows, characters) and the request rate per provider. Option `--break exa` / `--break exa,parallel` replaces these keys in the process with an invalid value. Pace 7.5 s per request.
7. **Checks.** `uv sync`, `ruff check`, `ruff format --check`, `pytest`.
8. **Documentation.** README (what it does, requirements, installation, configuration, log check, costs and quotas, limitations, FAQ, development), CHANGELOG.
9. **Review against the design (T3)** by a separate reviewer; fix findings; re-run step 7.
10. **Live check (T2)** in a profile that has the three keys. Until such a profile exists: smoke test of the Firecrawl stage only, with the two other keys unset.
    - Done 2026-10-10: smoke test of the provider class against the real Hermes classes (Hermes Desktop 0.21.6, Python 3.14, default profile with a Firecrawl key only): `exa=no_key parallel=no_key firecrawl=ok`, 10 rows in the S4 shape. The full live check is still open.

## Requirement coverage

| Requirement | Step | Verified by |
|---|---|---|
| S1 | 4 | `test_provider.py` (manifest, register) |
| S2, S3 | 3 | `test_provider.py` |
| S4 | 2, 3 | `test_engines.py` (rows), `test_provider.py` (shape) |
| S5, S6 | 3 | `test_provider.py` |
| K1–K7 | 3 | `test_provider.py` |
| A0–A4, A6 | 2 | `test_engines.py` |
| A5 | 3 | `test_provider.py` (injected transport), live check (proxy untested) |
| I1–I4 | 8 | README; live check uses an installed copy |
| L1, L2 | 3 | `test_provider.py` |
| T1–T4 | 5, 6, 7, 9, 10 | – |

## Not in this version

- Forcing HTTP 402 in a test account (observed in the log during use instead).
- A troubleshooting document and an evaluation document with data files, as the sibling plugin has; the README carries a short version.
- Publishing the repository and installing the plugin into profiles (separate decisions).
