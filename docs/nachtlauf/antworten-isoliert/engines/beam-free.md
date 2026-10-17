1. `engines.py:68-77` — potenzieller Bug: `_detail()` wird innerhalb des `try`-Blocks von `_post()` ausgewertet; wirft `_detail()` eine dort nicht abgefangene Ausnahme, fällt die Antwort in den generischen `except Exception`-Zweig und verliert HTTP-Status sowie Detail. Beispiel: Eine non-2xx-Antwort, deren Body in `_detail()` fehlschlägt, ergibt einen Transportfehler statt `{"code": "http_<status>", "status": <status>}`. Ich bin mir bei der genauen httpx-Dekodierung nicht sicher; `_detail` fängt nur `ValueError` und `RecursionError` ab.

2. `engines.py:34-38` — Performance: `_error` erstellt `str(detail)` für die gesamte Antwort und ersetzt den Key im gesamten Text, obwohl nur die ersten `ERROR_SCAN` (2000) Zeichen ausgegeben werden. Beispiel: Ein 10 MB großer Klartext-Fehlerbody wird komplett verarbeitet, obwohl nur 200 Zeichen im Ergebnis erscheinen.

3. `engines.py:119,146` — Abweichung von Best Practices: `MAX_RESULTS = 20` wird nur in `parallel()` angewendet, während `exa()` (`numResults=limit`) und `firecrawl()` (`limit=limit`) den übergebenen Wert ungeprüft weiterleiten. Beispiel: `engines.exa(client, "q", 1000, "k")` sendet `numResults: 1000`, `engines.parallel(..., 1000, ...)` dagegen `max_results: 20`.

4. `engines.py:127` — Edge Case, der zu Fehlverhalten führt: `results = min(limit, MAX_RESULTS)` geht von einer Zahl aus; bei `limit=None` oder einem String wirft `min()` `TypeError`, und negative Werte werden als negative `max_results` gesendet. Beispiel: `engines.parallel(client, "q", "10", "k")` wirft statt eines Fehlerdicts, entgegen der Dokumentation, dass diese Funktionen nie werfen.

5. `engines.py:118` — Edge Case: `highlights = {"maxCharacters": highlight_chars} if highlight_chars else True` validiert den Wert nicht; negative oder nicht-numerische Werte werden als `maxCharacters` in den Request übernommen. Beispiel: `engines.exa(client, "q", 5, "k", -5)` sendet `{"maxCharacters": -5}`.

6. `engines.py:35-36` — Security: Die Key-Maskierung ist ein exakter Stringvergleich; gibt der Provider den Key in veränderter Form aus (Klein-/Großschreibung, URL-Encoding, als Teilstring), bleibt er im Fehlertext. Beispiel: Key `SECRET-KEY` und Fehlerdetail `secret-key` oder `SECRET%2DKEY` wird nicht zu `[key]`.

7. `engines.py:52-58` — schlechter Stil/Edge Case: `_detail()` gibt den ersten truthy Wert aus `tag`, `error` oder `message` zurück und wandelt nicht-String-Werte per `str()` um; so kann eine Python-Repräsentation als Fehlerdetail entstehen. Beispiel: Body `{"error": ["a", "b"]}` liefert `"['a', 'b']"` statt eines klaren Fehlertexts.

8. `engines.py:151` — Edge Case: `data.get("success") is not True` akzeptiert nur exakt das Python-`True`; eine truthy, aber nicht identische Erfolgsmarkierung wie `1` gilt als malformed. Beispiel: `{"success": 1, "data": {"web": []}}` ergibt `Firecrawl: malformed reply`, obwohl der Request logisch erfolgreich war.
