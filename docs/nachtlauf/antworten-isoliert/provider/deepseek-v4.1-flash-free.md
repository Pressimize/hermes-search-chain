1. **provider.py:106 — Edge Case / potenzieller Bug**
`limit = max(1, min(limit, engines.MAX_RESULTS))` validiert `limit` nicht, während die Query direkt darüber (Zeile 103) per `isinstance` abgesichert ist. Übergibt Hermes `limit=None` oder `limit="5"`, wirft `min`/`max` einen `TypeError`, der erst in `search()` (Zeile 96–98) gefangen wird. Beispiel: `p.search("q", limit=None)` → `{"success": False, "error": "search-chain: TypeError"}` statt einer geklemmten Zahl.

2. **provider.py:132/134 — potenzieller Bug**
`result["code"]` und `result["status"]` werden ohne `get`/Absicherung indexiert; nur der Pfad mit vorhandenem `"rows"`-Schlüssel umgeht sie. Liefert eine Stufe (z. B. bei einem Contract-Bruch in `engines.py`, das hier nicht angehängt ist) ein Dict ohne diese Schlüssel, entsteht ein `KeyError`, der die gesamte Kette abbricht, statt zur nächsten Stufe zu gehen. Beispiel: Rückgabe `{"error": "HTTP 500 boom"}` für Exa → `search-chain: KeyError`, Parallel/Firecrawl werden nie gefragt. (Vorbehalt: `engines.py` nicht einsehbar.)

3. **provider.py:41–42 und 47 — Edge Case / Testkopplung**
`_env` gibt den Wert unverändert zurück (Zeile 32–36), aber `_exa` prüft `value.isascii() and value.isdecimal()` und `_parallel` vergleicht `.lower() == "v1"`. Das funktioniert nur, weil der Stand-in `get_provider_env` in `conftest.py:37` selbst `str(value).strip()` macht; ob das echte Hermes das auch tut, ist hier nicht belegt. Beispiel: `SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS=" 1200 "` → Test grün durch Stripping, produktiv aber `isdecimal() == False` und Fallback auf 600, falls Hermes nicht strippt.

4. **provider.py:112 — schlechter Stil / inkonsistentes Fehlerformat**
Alle anderen Fehler beginnen mit `"search-chain: "` (Zeile 98, 105, 138), der Interrupt-Fall gibt aber `_failed("Interrupted")` ohne Präfix zurück. Aufrufer, die Fehler über den Provider-Namen filtern oder anzeigen, erkennen diesen Fall nicht als `search-chain`-Fehler. Beispiel: `p.search("q")` bei gesetztem Interrupt → `{"success": False, "error": "Interrupted"}`.

5. **provider.py:108 — Performance**
Pro `search()`-Aufruf wird ein neuer `httpx.Client` erzeugt und geschlossen. Dadurch entfallen Keep-Alive-Verbindungen und TLS-Session-Wiederverwendung zwischen aufeinanderfolgenden Suchen; jede Suche handelt neu aus. Für einen Provider, der wiederholt aufgerufen wird, wäre ein geteilter Client (bzw. Pool) günstiger.

6. **provider.py:73 mit 135 — Performance / Edge Case**
`self._paused` wird nur befüllt/überschrieben, nie bereinigt; abgelaufene Einträge (bis 86400 s) bleiben für jede jemals gesehene `(stage, key-Digest)`-Kombination im Speicher. Bei rotierenden Keys oder mehreren Profilen im selben Prozess wächst das Dict monoton. Beispiel: viele unterschiedliche `EXA_API_KEY`-Werte in einem langlebigen Prozess → wachsende Pause-Tabelle ohne Nutzen.

7. **provider.py:35–36 (via `_env`) — Abweichung von Best Practices**
`except Exception: return ""` verschluckt jede Ausnahme der Key-Auflösung vollständig und ohne Logging. Eine Fehlkonfiguration (z. B. `UnscopedSecretError`) ist damit nicht von einem schlicht fehlenden Key unterscheidbar. Beispiel: `get_provider_env` wirft `RuntimeError` → Stufe wird still als `no_key` übersprungen, ohne jeden Hinweis im Log.

8. **provider.py:110 — Edge Case**
`is_interrupted()` wird nur am Anfang jeder Stufe geprüft, also zwischen den Requests. Ein laufender Request kann nicht abgebrochen werden; die Abbruch-Latenz entspricht dem httpx-Timeout pro Stufe. Beispiel: Exa hängt bis zum Client-Timeout, dann erst greift die Interrupt-Prüfung vor der Parallel-Stufe.

9. **provider.py:137 — Security (mit Vorbehalt)**
Der Warnlog schreibt `detail = result["error"].partition(": ")[2]` ungefiltert ins Log und verlässt sich darauf, dass `engines.py` Keys zu `[key]` und Zeilenumbrüche entfernt (was `test_key_never_in_result_or_log`/`test_pause_warning_is_one_line` belegen, aber gegen die hier nicht angehängte `engines.py`). Käme der API-Key oder ein `\n` doch in den Fehlertext, landete er im Log bzw. könnte Logzeilen fälschen. (Vorbehalt: `engines.py` nicht einsehbar.)
