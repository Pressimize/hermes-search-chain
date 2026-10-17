1. **recompute.py:84** (auch 108, 115) – potenzieller Bug: `category[r["id"]]` bzw. `cell[(a, q)]` sind ungeschützte Dict-Zugriffe. Fehlt eine ID aus `end-to-end/results.csv` in `end-to-end/questions.csv` oder fehlt einem Setup eine Frage, bricht das ganze Skript mit `KeyError` ab statt den Datensatz zu melden. Eingabe-Beispiel: eine Zeile mit `id=q99` in results.csv, die in questions.csv nicht existiert.

2. **recompute.py:83-86** – Edge Case: Die Kategorien sind als Tupel `("fact", "error", "current")` fest verdrahtet. Jede Frage mit einer anderen Kategorie in questions.csv wird stillschweigend aus `by_category` und damit aus der gedruckten `correct`-Summe ausgeschlossen, ohne Warnung. Beispiel: eine Frage mit `category=opinion` zählt nirgends mit.

3. **recompute.py:44-45** – Edge Case, der zu Fehlverhalten führt: `median` filtert nur `v != ""` und ruft dann `float(v)` auf. Ein nicht-numerischer Zellwert wie `N/A` oder `-` löst eine `ValueError` aus und beendet das komplette Skript, statt die Spalte zu überspringen.

4. **recompute.py:102** – Edge Case: `cell = {(r["setup"], r["id"]): r ...}` überschreibt bei doppelten Zeilen stillschweigend den vorherigen Eintrag. Ein versehentlich doppelt vorhandenes (setup, id)-Paar in results.csv wird nicht erkannt, sondern verfälscht die Paarvergleiche.

5. **live_check.py:98-100** – potenzieller Bug: Nur `ValueError` wird um `json.loads(raw)` abgefangen. Ich bin mir über den Rückgabetyp von `web_search_tool` nicht sicher; liefert es ein `dict` statt eines Strings, wirft `json.loads` `TypeError`, was hier nicht gefangen wird und die Query-Schleife abbricht. `len(raw)`/`data.get` in Zeile 107/108 setzen ohnehin stillschweigend einen String voraus.

6. **live_check.py:68-69** – Edge Case/Abweichung von der Doku: Erlaubt ist `0 <= pace < 3600`, d. h. `--pace 0` deaktiviert die Drosselung vollständig, obwohl das Flag genau die Ratenbegrenzung schützen soll. Zusätzlich ist der Default 7.5 s gleich 8 Requests/min, also nicht „below 8“, wie der Docstring in Zeile 11 behauptet.

7. **live_check.py:105** – schlechter Stil/potenzieller Bug: Die Zählung nutzt Substring-Prüfungen (`f"{stage}=" in steps`). Das ist gegen Namens-/Status-Kollisionen empfindlich (z. B. eine Stufe `exa` vs. `exa2`) und erfasst nur `no_key`/`paused` als Ausschluss, während laut Zweck auch Fehler und „ohne Treffer“ übersprungen werden. Robuster wäre, die Statuszeile in Tokens zu parsen und gegen eine Whitelist zu prüfen.

8. **live_check.py:39, 76-77** – Abweichung von Best Practices: Das Skript greift auf interne/private Hermes-APIs zu (`agent.web_search_registry.get_provider`, `tools.web_tools._ensure_web_plugins_loaded`, `_get_search_backend`, `_load_web_config`). Der Kommentar in Zeile 75 räumt selbst ein, dass diese Namen sich mit einem Update verschieben können, was das Werkzeug fragil macht und beim Hermes-Upgrade sofort bricht.

9. **pyproject.toml:11** – Abweichung von Best Practices: `httpx==0.28.1` ist exakt gepinnt, gilt aber nur für die Entwicklungs-/CI-Umgebung, da das Plugin mit dem httpx von Hermes läuft. Liefert Hermes eine andere httpx-Version, testet CI eine Version, die in Produktion nie ausgeführt wird, und kann echte Inkompatibilitäten verschleiern.

10. **ci.yml:24 (und 21-23)** – Best Practice/Performance: `python scripts/recompute.py > /dev/null` verwirft die Ausgabe, ist also nur ein Smoke-Test; eine zahlenmäßige Regression der Kennzahlen lässt CI nicht fehlschlagen. Außerdem wird `uv run --locked` viermal separat aufgerufen, was die Umgebung mehrfach synchronisieren kann; ein einmaliges `uv sync --locked` plus `uv run --no-sync` wäre effizienter.
