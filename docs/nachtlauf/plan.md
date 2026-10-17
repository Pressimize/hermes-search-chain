# Nachtlauf 2026-10-17: Plan

Branch `review/nachtlauf-2026-10-17`, abgezweigt von `main` nach dem Merge von PR #1 (`5287a03`).

## Ausgangslage

- Testsuite auf `main`: `uv run --locked pytest -q` → **150 passed** (0,65 s); `ruff check` und `ruff format --check` sauber; `scripts/recompute.py` läuft ohne Fehler.
- Code: `search_chain/` (engines.py 153 Zeilen, provider.py 138, `__init__.py` 8, plugin.yaml 20), Tests 827 Zeilen, Skripte 240 Zeilen.

## Prüfbereiche

Je Bereich ein Aufruf von `scripts/second-opinion.sh` mit allen Dateien als Anhang (jeweils unter 800 Zeilen).

| Bereich | Dateien | Zeilen |
|---|---|---|
| `engines` | `search_chain/engines.py`, `tests/test_engines.py` | 479 |
| `provider` | `search_chain/provider.py`, `search_chain/__init__.py`, `search_chain/plugin.yaml`, `tests/conftest.py`, `tests/test_provider.py` | 667 |
| `scripts` | `scripts/live_check.py`, `scripts/recompute.py`, `.github/workflows/ci.yml`, `pyproject.toml` | 289 |
| `spec` | `docs/design.md`, `search_chain/engines.py`, `search_chain/provider.py` (Abgleich Code ↔ Spezifikation) | 482 |

Prompts: `docs/nachtlauf/prompts/<bereich>.txt`. Antworten: `docs/nachtlauf/antworten/<bereich>/`.

## Modelle

Aufruf `OPINION_COUNT=8 scripts/second-opinion.sh …` (alle acht Modelle der Rangfolge plus ein Rotationsmodell).

Stand OpenCode am 2026-10-17 (`opencode models opencode`): **nicht mehr verfügbar** sind `muse-spark-1.3-contributor-free`, `cat-jam-free` und `ll-alpha-free` („Model not found“). Neu und unbewertet ist `beam-free`. Die Rangfolge im Skript ändert nur Andre, daher bleibt sie unverändert; die beiden fehlenden Modelle scheitern je Lauf in rund 5 s und werden als Fehlversuch gezählt.

Entscheidung: `beam-free` wird über `OPINION_POOL` vorn in die Rotation gestellt (Skript unverändert), damit möglichst viele Modelle antworten. Nemotron bleibt laut CLAUDE.md außen vor.
