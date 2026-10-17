1. `search_chain/engines.py:116-121,143-153` — Edge Case / Abweichung von A6: Nur `parallel` (Zeile 127) und der Provider (provider.py:106) begrenzen `limit` auf 1–20; `exa` und `firecrawl` leiten `limit` unverändert weiter. Direktaufruf mit `limit=50` sendet Exa `numResults: 50` und Firecrawl `limit: 50`. Beispiel: `engines.exa(client, "q", 50, "k")`.

2. `search_chain/engines.py:48-58` — Edge Case / Abweichung von A4: `_detail` prüft `if value:` und überspringt vorhandene, aber falsy Felder (`tag: ""`, `error: null`). A4 verlangt das erste vorhandene Feld. Beispiel: Body `{"tag": "", "error": "x"}` liefert Detail `"x"` statt `""`.

3. `search_chain/provider.py:39-47,83-84` — Edge Case / Portabilität: Die Settings werden nicht selbst `strip()`-ed; `_exa`/`_parallel` und `is_available` verlassen sich darauf, dass `get_provider_env` trimmt. Wenn Heremes' echte Implementierung nicht trimmt, werden `" 300 "` bzw. `" v1 "` ungültig und ein nur aus Leerzeichen bestehender Key als gesetzt gewertet. Beispiel: `SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS=" 300 "` würde 600 statt 300 liefern.

4. `search_chain/provider.py:92-98` — Edge Case / Abweichung von S5: `search` fängt nur `Exception`; `KeyboardInterrupt` und `SystemExit` propagieren, obwohl S5 „search never raises“ behauptet. Beispiel: Ein KeyboardInterrupt während der Kette verlässt `search` unkontrolliert.

5. `search_chain/provider.py:118-123` — Abweichung von K5 (Stil/Edge Case): Der Pause-Grund speichert `result["error"]` (bereits auf 200 Zeichen gekürzt und maskiert) und baut daraus die Restzeit; bei sehr langen, gekürzten Fehlern kann der in K5 geforderte Reply-Text unvollständig in der Pause-Meldung landen. Beispiel: ein 402-Fehler mit >200 Zeichen Detail ergibt einen gekürzten Pause-Grund.
