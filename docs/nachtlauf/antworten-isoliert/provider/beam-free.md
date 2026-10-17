1. `provider.py:132-137` – Edge Case, der zu Fehlverhalten führt – Der Fehlerpfad dereferenziert `result["code"]`, `result["status"]` und `result["error"]` ohne Prüfung; gibt ein Engine im Fehlerfall z. B. `{"success": False, "error": "boom"}` ohne `code`/`status` zurück, fliegt ein `KeyError`, den `search()` nur zu `"search-chain: KeyError"` umwandelt, statt die Stage korrekt als Fehler zu zählen und zu loggen.

2. `provider.py:133,136` – Security – `result["error"]` und `detail` werden unverändert übernommen; Zeilenumbrüche in Fehlertexten (z. B. 402-Body-Tag `"NO_CREDITS\nERROR forged line"`) werden nicht bereinigt, sodass Logzeilen gefälscht werden können und die in `test_pause_warning_is_one_line` erwartete Normalisierung nicht vom Provider selbst abgesichert ist.

3. `provider.py:106` – Edge Case, der zu Fehlverhalten führt – `limit = max(1, min(limit, engines.MAX_RESULTS))` bricht bei nicht-ganzzahligem `limit` (z. B. `search("q", "5")`) mit `TypeError` ab, weil `str` und `int` verglichen werden; `search()` fängt das zwar ab, liefert aber nur `"search-chain: TypeError"` statt eines sinnvollen Ergebnisses.

4. `provider.py:73,135` – Performance – `_paused` wird nie bereinigt: abgelaufene Pausen werden nicht entfernt, sondern nur bei identischem Slot überschrieben; bei vielen verschiedenen Keys/Profilen über die Prozesslebensdauer akkumulieren sich Einträge im Dict.

5. `provider.py:118-119,135` – Abweichung von Best Practices – `_paused` wird ohne Synchronisation gelesen und geschrieben; bei gleichzeitigen `search()`-Aufrufen mit unterschiedlichen Keys kann das zu verlorenen Pausen oder inkonsistentem Zustand führen.

6. `provider.py:24-29` – Edge Case, der zu Fehlverhalten führt – Der Fallback für `is_interrupted` fängt nur `ImportError`; existiert `tools.interrupt`, aber ohne `is_interrupted`, fliegt ein `AttributeError` statt des Fallbacks.

7. `conftest.py:33-37` – Edge Case, der zu Fehlverhalten führt – `get_provider_env` gibt bei einem Bytes-Wert `str(value).strip()` zurück, was `"b'...'"` statt der dekodierten Zeichenkette ergibt.
