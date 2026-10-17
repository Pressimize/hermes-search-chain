1. **Datei:** `engines.py`, Zeilen 20–22, 67  
   **Kategorie:** Edge Case, der zu Fehlverhalten führt  
   **Begründung:** `timeout` wird an `client.post(..., timeout=timeout)` übergeben; httpx wendet diesen Wert je Phase (Connect, Read, Write, Pool) an, nicht als Gesamt-Deadline. Eine Gegenstelle, die den Header früh sendet und den Body dann langsam über mehrere Read-Anteile liefert, kann die nominale Grenze deutlich überschreiten. Wer auf „maximal 10 s“ spekuliert (z. B. für Pause-/Budget-Logik in der Kette), bekommt im Extremfall mehr.  
   **Beispiel:** Antwort mit `Content-Length`, die in 30-chunks zu je knapp unter `EXA_TIMEOUT` ausgeliefert wird.

2. **Datei:** `engines.py`, Zeilen 76–77  
   **Kategorie:** Abweichung von Best Practices  
   **Begründung:** `except Exception as exc` in `_post` fängt auch Nicht-Transportfehler (AttributeError, TypeError aus künftigen Refactors, Fehler in Mocks) und meldet sie als `code = type(exc).__name__` im selben Format wie echte Netzwerkfehler. Damit gehen Programmierfehler als „ConnectError“ o. Ä. durch und sind im Ergebnis der Kette nicht mehr von Providerstörungen zu unterscheiden. Eingrenzung auf `httpx.HTTPError` (ggf. plus `OSError`) wäre trennschärfer.  
   **Beispiel:** Später eingefügtes `body["foo"]["bar"]` vor `_post` oder ein Fehler in `_detail` landet so als Transport-Fehlercode im Ergebnis.

3. **Datei:** `engines.py`, Zeilen 119, 127, 146  
   **Kategorie:** Edge Case, der zu Fehlverhalten führt  
   **Begründung:** `limit` wird nie auf > 0 geprüft. `parallel` rechnet nur `min(limit, MAX_RESULTS)`; `exa` und `firecrawl` schicken den Wert unverändert ins Request-Body. Ein negativer oder Null-Wert wird als `numResults`/`max_results`/`limit` gesendet und führt zu HTTP-Fehler oder undefiniertem Anbieterverhalten, statt deterministisch leer oder mit Fehler zu enden.  
   **Beispiel:** `engines.exa(client, "q", 0, "k")` bzw. `limit=-1` in allen drei Engines.

4. **Datei:** `engines.py`, Zeilen 27, 119, 127, 146  
   **Kategorie:** Abweichung von Best Practices  
   **Begründung:** Nur `parallel` deckelt auf `MAX_RESULTS` (20); `exa` und `firecrawl` übernehmen `limit` roh. Gleicher Aufrufparameter erzeugt also je Provider andere Request-Grenzen. Das erschwert Vergleiche im Bench und macht die obere Grenze nur dort wirksam, wo jemand sie explizit eingebaut hat.  
   **Beispiel:** `limit=50` → Parallel bittet um 20, Exa/Firecrawl um 50.

5. **Datei:** `engines.py`, Zeilen 46–59, 70  
   **Kategorie:** Edge Case, der zu Fehlverhalten führt  
   **Begründung:** `_detail` liefert bei leerem oder nur aus Whitespace bestehendem Body `response.text.strip()` → `""`. Der Fehlerstring wird dann `"{Provider}: HTTP {status} "` mit abschließendem Leerzeichen; `_error` kürzt und normalisiert Leerraum nur im Textteil, nicht am Ende des zusammengesetzten Strings. Logs und Tests, die auf exakte Endungen trimmen, sehen ein „HTTP 500 “ ohne Grund.  
   **Beispiel:** `httpx.Response(500, text="")` → `{"error": "Exa: HTTP 500 ", ...}`.

6. **Datei:** `engines.py`, Zeilen 49–59  
   **Kategorie:** Performance  
   **Begründung:** Bei Non-2xx mit nicht-JSON-Body greift `response.text.strip()` und materialisiert den kompletten Body, bevor `_error` auf `ERROR_SCAN`/`ERROR_MAX` kürzt. Für die spätere einzeilige Meldung sind nur die ersten ~2000 Zeichen nötig; große Error-Seiten (HTML-Firewall, Debug-Dump) erzeugen trotzdem große Zwischenstrings in jedem fehlschlagenden Aufruf.  
   **Beispiel:** HTTP 502 mit mehreren MB HTML-Body → volle `text`-Kopie, Ergebnis bleibt 200 Zeichen.

7. **Datei:** `engines.py`, Zeilen 94–104  
   **Kategorie:** Edge Case, der zu Fehlverhalten führt  
   **Begründung:** `position` wird nach dem Verwerfen nicht-`http(s)`-URLs mit `enumerate(hits, 1)` neu durchnummeriert, nicht mit dem Rang im Anbieterpayload. Das ist in der Docstring so beschrieben, bricht aber die Zuordnung „Position i = i-Treffer des Providers“, falls die Kette oder ein Judge später Originallage vergleichen will. Ohne Test, der die Semantik gegen den Upstream-Rang festschreibt, bleibt das still ein Deutungsrisiko.  
   **Beispiel:** `results = [{"url": "ftp://…"}, {"url": "https://a.example/"}]` → Ausgabezeile hat `position: 1`, obwohl es Upstream-Treffer 2 war.
