1. `live_check.py:24,39` — Security: `HERMES_ROOT` aus der Umgebung bestimmt den Pfad, der per `sys.path.insert` geladen wird; ein Angreifer kann so beliebigen Code ausführen (`HERMES_ROOT=/tmp/evil`).
2. `live_check.py:37-38` — Abweichung von Best Practices: Es werden alle Variablen mit Suffix `_API_KEY` gelöscht, nicht nur die drei Provider-Keys; ein in der Shell gesetztes `OPENAI_API_KEY`, das nicht in der Profil-`.env` steht, fehlt danach.
3. `live_check.py:99-100` — Edge Case: Nur `ValueError` wird abgefangen; liefert `web_search_tool` `None` oder Bytes, wirft `json.loads` einen uncaught `TypeError`/`AttributeError` (API von `web_search_tool` nicht im Anhang verifizierbar).
4. `live_check.py:70` — Edge Case: `sys.stdout.reconfigure` existiert nur bei `TextIOWrapper`; bei umgeleitetem/ersetztem stdout (z. B. in Tests) wirft das `AttributeError`.
5. `recompute.py:43` — Edge Case: `median` filtert nur leere Strings (`v != ""`), nicht Whitespace; ein Feldwert `" "` passiert den Filter und `float(" ")` wirft `ValueError`.
6. `recompute.py:55` — potenzieller Bug: `seconds` wird über alle Runs gemittelt, `chars` nur über `run2-main`; extra-Run-Daten beeinflussen also die Sekunden-Median, nicht die Zeichen-Median.
7. `recompute.py:88` — Edge Case: `category[r["id"]]` wird ohne Prüfung verwendet; eine Zeile mit unbekannter `id` in `end-to-end/results.csv` führt zu `KeyError`.
8. `recompute.py:102` — Edge Case: `cell` ist ein Dict mit Schlüssel `(setup, id)`; doppelte Zeilen überschreiben sich still und verfälschen die Paarvergleiche.
9. `recompute.py:119` — Edge Case: `statistics.median(diffs)` wirft `StatisticsError`, wenn `diffs` leer ist (keine gemeinsamen gültigen Felder).
10. `ci.yml:21-24` — Abweichung von Best Practices: Alle `uv run --locked`-Schritte setzen eine `uv.lock` voraus, die unter den angehängten Dateien fehlt; ohne Lockfile schlägt CI beim Install fehl (Annahme, da Lockdatei nicht angehängt).
