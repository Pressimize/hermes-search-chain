1. `engines.py:116,145` (vs. Zeile 127) — Edge Case / Abweichung von A6: `exa` (`numResults: limit`) und `firecrawl` (`limit: limit`) leiten `limit` unverändert durch, während `parallel` mit `results = min(limit, MAX_RESULTS)` klemmt. Der Provider klemmt zwar vorher, aber direkte Engine-Aufrufe (Tests/Mocks) können >20 senden. Beispiel: `engines.exa(client, q, 100, key)` sendet `numResults: 100`.

2. `engines.py:89` — Edge Case: `_rows` wirft bei einem Nicht-Dict-Eintrag im `results`-Array `_malformed` und bricht die Stufe ab, statt den Eintrag zu verwerfen. Spec S4 definiert Verwerfen nur über die URL, nicht den Item-Typ. Beispiel: `{"results": [{"url": "http://x"}, 42]}` → `malformed reply` statt einer Zeile.

3. `engines.py:48–59` — Edge Case: `_detail` fängt nur `ValueError, RecursionError`; `response.json()`/`response.text` können bei kaputtem komprimiertem Body eine `httpx.DecodingError` werfen. Der Aufruf in `_post` (Zeile 68) liegt im `try`, wird als Transportfehler abgefangen, aber der HTTP-Status geht verloren, sodass ein 402/429 mit kaputtem Body weder pausiert noch mit Status gemeldet wird. (Unsicher bei httpx: falls `DecodingError` von `ValueError` erbt, wäre sie bereits abgefangen.) Beispiel: non-2xx mit kaputtem gzip-Body → `"DecodingError"` statt `"HTTP 402 …"`.

4. `engines.py:34–38` — Performance: `text.replace(key, "[key]")` läuft auf dem kompletten `str(detail)` (bei `_detail`-Fallback der ganze Response-Body), erst danach Trunkierung auf `ERROR_SCAN=2000`. Bei großen Antworten unnötige Arbeit/Speicher. Beispiel: 10 MB Body mit Key → Replace scannt 10 MB.

5. `provider.py:106` — Edge Case: `limit = max(1, min(limit, engines.MAX_RESULTS))` wirft bei `limit=None`/`str`/`NaN` (`TypeError`/`ValueError`), was zwar von `search` abgefangen wird, aber als `"search-chain: TypeError"` endet. Beispiel: `provider.search("q", limit=None)` → `{"success": False, "error": "search-chain: TypeError"}`.

6. `provider.py:94–100` — Abweichung von S5: `search` fängt nur `Exception`; `KeyboardInterrupt`/`SystemExit` propagieren, obwohl S5 "search never raises" verlangt. Beispiel: KeyboardInterrupt während `_chain` bricht nach außen durch.

7. `provider.py:60` — Edge Case: `_left` rundet Stunden per `math.floor(seconds/3600 + 0.5)` (half-up), "nearest hour" kann je nach Konvention Banker's Rounding bedeuten; bei x,5 h (z. B. 2,5 h) Abweichung. Beispiel: 9000 s (2,5 h) → Code `"3 h"`, Python `round()` → `"2 h"`.

8. `provider.py:40–42,47` — Edge Case: `_exa`/`_parallel` rufen `_env(...).isascii()`/`.lower()` auf; gibt `get_provider_env` einen Nicht-`str` (z. B. `None`) zurück, wirft `AttributeError`, die als unerwartete Exception endet. S3 behandelt nur Lese-Exceptions als "unset", nicht falsche Typen. Beispiel: `get_provider_env` liefert `None` → `"search-chain: AttributeError"`.

9. `provider.py:118` — Edge Case / Security: `key.encode("utf-8", "surrogatepass")` für den Digest setzt voraus, dass `key` ein `str` ist; bei Nicht-`str` (`None`) `AttributeError` statt "unset". Konsistent zu Befund 8.

10. `engines.py:118` — Edge Case: `highlights = {"maxCharacters": highlight_chars} if highlight_chars else True` nutzt Truthiness statt `== 0`; ein direkt übergebener String `"0"` (truthy) würde als Cap `0` gesendet statt Exas Default-Highlights. Beispiel: `engines.exa(client, q, 5, key, "0")` → `"maxCharacters": "0"`.
