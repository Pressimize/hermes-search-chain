1. `scripts/live_check.py:102-103` — potenzieller Bug. `info` behält nur Logzeilen mit `"="`; im Fehlerpfad von `search()` (z. B. `search-chain: call failed: X` bzw. `search-chain: no stage ran`) enthält keine Zeile ein `=`, daher wird `"(no log line: served from Hermes' cache?)"` ausgegeben und ein echter Fehler wie ein Cache-Treffer dargestellt. Beispiel: `HTTPS_PROXY='http://[::1' <hermes-python> -I scripts/live_check.py default`.

2. `scripts/live_check.py:37-38` — Edge Case, der zu Fehlverhalten führt. Die Schleife entfernt jede Umgebungsvariable, die auf `_API_KEY` endet, nicht nur die drei Plugin-Keys; Keys, die nur über die Shell kamen (z. B. `OPENAI_API_KEY`), fehlen anschließend im Bootstrap. Beispiel: `OPENAI_API_KEY=... <hermes-python> -I scripts/live_check.py default`.

3. `scripts/live_check.py:104-106` — potenzieller Bug. Als Anfrage wird jede Stufe gezählt, die nicht `no_key`/`paused` ist; `interrupted` (provider.py) enthält ein `=`, obwohl kein HTTP-Request gesendet wurde. Beispiel: Lauf mit `/stop` während der Suche erhöht `counts["exa"]`.

4. `scripts/live_check.py:97-100` — Edge Case, der zu Fehlverhalten führt. `json.loads(raw)` fängt nur `ValueError`; liefert `web_search_tool` `None` oder einen Nicht-String, wirft `json.loads` `TypeError` und das Skript bricht ab. Beispiel: hypothetischer Hermes-Pfad mit `None`-Rückgabe.

5. `scripts/live_check.py:109` — Performance. `time.sleep(args.pace)` steht innerhalb der Schleife und wartet auch nach der letzten Query vor der Ausgabe der Summen. Beispiel: Standardlauf mit `--pace 7.5` wartet am Ende unnötig 7,5 s.

6. `scripts/recompute.py:65` — potenzieller Bug. In der Run-2-Zeile wird der Sekunden-Median über beide Blöcke (`run2-main` und `run2-extra`) gemittelt, der Zeichen-Median aber nur über `run2-main`; Firecrawl läuft nur im Extra-Block und ergibt in der angehängten Version `None chars`. Beispiel: `python scripts/recompute.py | grep firecrawl`.

7. `scripts/recompute.py:88, 90` — Edge Case, der zu Fehlverhalten führt. `sum(int(r["input_tokens"]))` und `sum(int(r["searches"]))` haben keinen Guard auf leere Zellen, während der Paarvergleich unten leere Werte filtert; eine Zeile mit `input_tokens=""` lässt `recompute.py` mit `ValueError` abbrechen. Beispiel: abgebrochener Lauf mit leerer Token-Spalte in `data/end-to-end/results.csv`.

8. `scripts/recompute.py:108-109` — Edge Case, der zu Fehlverhalten führt. `cell[(a, q)]` und `cell[(b, q)]` sind ungeschützte Dict-Zugriffe; fehlt ein Setup×Frage-Paar, bricht das Skript mit `KeyError` ab statt die Lücke zu melden. Beispiel: Zeile `k37,exa-capped,...` in `data/end-to-end/results.csv` anhängen.

9. `.github/workflows/ci.yml:24` — Abweichung von Best Practices. Die Umleitung `> /dev/null` verwirft die gesamte Ausgabe; CI prüft nur, dass das Skript durchläuft, und erkennt Zahlendrift (z. B. den `None chars`-Fall) nicht. Beispiel: Drift in `recompute.py` bleibt grün.

10. `pyproject.toml:11` — Abweichung von Best Practices. `httpx==0.28.1` ist als exakt gepinnte Runtime-Dependency erklärt, obwohl das Plugin ohne diese Datei ausgeliefert wird (`package = false`); bei Hermes-Update auf eine andere httpx-Version blockiert der Pin das Lockfile. Beispiel: `uv lock`-Konflikt bei httpx 0.29.
