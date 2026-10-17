1. `provider.py:106` – Edge Case: `limit` wird nur geklemmt, aber nicht typgeprüft/konvertiert. `search("q", None)` und `search("q", "5")` lösen `TypeError` aus (wird von `search()` abgefangen, Ergebnis `search-chain: TypeError`, keine Stufe wird gefragt); `search("q", 5.7)` sendet `numResults: 5.7` bzw. `max_results: 5.7`/`limit: 5.7` an die APIs. Beispiel: `provider.search("q", None)`.

2. `provider.py:132–134` – Edge Case/Robustheit: Wenn eine Engine ein Dict ohne `code`/`status` zurückgibt (Vertragsbruch), wirft der Zugriff `result['code']`/`result['status']` ein `KeyError`; die ganze Kette bricht ab (`search-chain: KeyError`), obwohl spätere Stufen noch laufen könnten. Beispiel: Engine liefert `{"error": "x"}`.

3. `provider.py:118` mit `search_chain/engines.py:70–77` – potenzieller Bug: Ein Key mit Lone Surrogate (z. B. `"k\ud800y12345"`) führt zu `UnicodeEncodeError`, das als `ValueError`-Unterklasse in den `malformed reply`-Zweig fällt; das Ergebnis meldet irreführend `Exa: malformed reply`, statt den Transportfehler zu benennen. Beispiel: `ENV["EXA_API_KEY"] = "k\ud800y12345"`.

4. `provider.py:24–29` – potenzieller Bug: Der Fallback für fehlendes `tools.interrupt` wird einmalig beim Import gebunden; ändert sich der Importpfad in Hermes, ist `/stop` für die ganze Prozesslaufzeit still deaktiviert, ohne Warnung. Die Tests patchen `is_interrupted` immer, sodass weder echter Import noch Fallback je ausgeführt werden.

5. `provider.py:32–36` – schlechter Stil: `_env` fängt pauschal `Exception` und behandelt jeden Fehler wie „nicht gesetzt", auch echte Programmfehler (z. B. `TypeError` in der Lookup-Funktion); Diagnose wird verschleiert. Beispiel: `get_provider_env` wirft `TypeError`.

6. `provider.py:96–98` – Abweichung von Best Practices/Diagnostik: Unerwartete Exceptions werden auf den Klassennamen reduziert, `steps`/`reasons` gehen verloren; die Logzeile zeigt eine scheinbar kürzere Kette. Beispiel: monkeypatchte Stage wirft `RuntimeError`.

7. `provider.py:73,119–135` – Performance/Speicher: `_paused` wird nie bereinigt; bei wechselnden Keys (mehrere Profile) bleiben abgelaufene Einträge dauerhaft liegen. Beispiel: viele verschiedene `EXA_API_KEY`-Werte im selben Prozess.

8. `conftest.py:40–44` – Abweichung (Test-Isolation): `sys.modules["agent.web_search_provider"]` wird unbedingt überschrieben, während `agent` nur per `setdefault` geschützt wird; in einer Hermes-Umgebung testet die Suite still gegen den Stub.

9. `conftest.py:33–37` – Test-Fidelity/Edge Case: `get_provider_env` macht `str(value).strip()`; `None` wird zu `"None"` (truthy), `is_available()` meldet fälschlich `True` und Header würden `None` tragen. Beispiel: `ENV["EXA_API_KEY"] = None`.

10. `test_provider.py:417–425` – Test-Reliabilität: Der einzige Test ohne `MockTransport` macht einen echten Verbindungsaufbau nach `127.0.0.1:9`; er hängt von schneller Connection-Refusal ab und kann bei Firewall oder laufendem Dienst auf Port 9 fehlschlagen.
