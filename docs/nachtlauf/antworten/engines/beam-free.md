1. `search_chain/engines.py:118` — Edge Case. `highlights = {"maxCharacters": highlight_chars} if highlight_chars else True` arbeitet mit Truthiness; ein negativer `highlight_chars` (z. B. `-1`) ist truthy und wird als `maxCharacters: -1` gesendet, statt als 0/Default behandelt zu werden. Beispiel: `engines.exa(client, "q", 5, "k", -1)` erzeugt `contents.highlights.maxCharacters == -1`.

2. `search_chain/engines.py:127` — Edge Case (Abweichung von A6). `results = min(limit, MAX_RESULTS)` begrenzt nur nach oben; ein `limit` von 0 oder negativ wird unverändert als `max_results` gesendet. Beispiel: `engines.parallel(client, "q", 0, "k")` erzeugt `max_results: 0`.

3. `search_chain/engines.py:119,146` — Abweichung von A6. Anders als `parallel` begrenzen `exa` und `firecrawl` `limit` nicht auf 20, sondern leiten `numResults`/`limit` unverändert weiter. Beispiel: `engines.exa(client, "q", 50, "k")` sendet `numResults: 50` (der Provider kapppt global, die Engine-Funktionen selbst sind inkonsistent).

4. `search_chain/engines.py:94` — Edge Case. Die URL-Prüfung prüft nur das Präfix, speichert aber die ursprüngliche Zeichenkette inklusive führender/nachgestellter Leerzeichen; `"https://a.example/ "` (mit nachgestelltem Leerzeichen) wird akzeptiert und mit Leerzeichen ausgegeben. Beispiel: ein Item mit `url="https://a.example/ "` bleibt erhalten und erscheint so in der Zeile.

5. `search_chain/engines.py:55-56` — Edge Case. `_detail` entpackt dict-wertige Felder nur eine Ebene tief; bei `{"error": {"message": {"message": "x"}}}` wird das innere Dict als String statt `"x"` zurückgegeben. Beispiel: eine zweifach geschachtelte Fehlermeldung wird nicht vollständig aufgelöst.

6. `search_chain/engines.py:49-51,76-77` — Edge Case. `_detail` fängt nur `ValueError` und `RecursionError`; ein `httpx.DecodingError` (z. B. defektes gzip) propagiert und wird in `_post` vom generischen `except Exception` als Transportfehler behandelt, wodurch der HTTP-Status verloren geht (`status=None`) und bei 402/429 keine Pause eingetragen wird. Beispiel: eine 402-Antwort mit `Content-Encoding: gzip` und ungültigem Body liefert `{"code": "DecodingError", "status": None}`.

7. `tests/test_engines.py:19-20` — schlechter Stil. Der Testhelfer `capture` ruft `json.loads(request.content)` bedingungslos auf; bei einer Anfrage ohne JSON-Body bricht der Helfer mit `JSONDecodeError` ab und verdeckt den eigentlichen Fehler. Beispiel: ein Test mit einem Transport, der leere Anfragebodies sendet, würde hier scheitern.
