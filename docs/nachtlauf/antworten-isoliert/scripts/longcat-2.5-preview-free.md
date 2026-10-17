1. **live_check.py:97-101, Edge Case, führt zu Absturz.** `json.loads(raw)` kann jeden gültigen JSON-Typ liefern; wird `data` kein Dict, schlägt `data.get("data")` mit `AttributeError` feh und der Live-Test bricht ab, obwohl das Plugin korrekt geantwortet hat. Beispiel: `web_search_tool` liefert `"null"` oder `"[]"` (z. B. bei leerem Erfolgs-Payload eines Plugin-Updates) → `AttributeError: 'NoneType'/'list' object has no attribute 'get'`.

2. **live_check.py:102-103, potenzieller Bug.** Der Filter prüft `"=" in line`, die Aufspaltung erfolgt aber mit `split(": ", 1)` und Index `[1]`. Enthält die Log-Zeile `=` ohne dahinter folgendes `": "`, ein IndexError. Beispiel: Plugin-Log `search-chain: exa=5 parallel=3` (Leerzeichen statt Doppelpunkt) → IndexError.

3. **live_check.py:87-89, Abweichung von Best Practices.** Der Handler wird an den Root-Logger gehängt und dessen Level global auf INFO gesetzt. Das ändert das Logging-Verhalten der gesamten Hermes-Installation in diesem Prozess statt nur des Plugins. Besser: den Plugin-Logger gezielt anfassen, z. B. `logging.getLogger("search-chain")`.

4. **live_check.py:84, Edge Case.** `is not False` prüft Identität, nicht Wahrheit. Eine Config mit `keyless_rescue: 0` (int, z. B. aus einer anderen YAML-Quelle) würde fälschlich als nicht-deaktiviert gewertet und das Script mit Fehler beenden. Idiomatisch wäre ein Wahrheits-Test wie `if _load_web_config().get("keyless_rescue", True):`.

5. **live_check.py:109, Performance.** `time.sleep(args.pace)` läuft auch nach der letzten Query, d. h. das Script wartet sinnlos weitere `--pace` Sekunden (bis zu 3599 s). Beispiel: `python -I scripts/live_check.py default --pace 7.5` mit nur 3 Queries → ~7,5 s Leerlauf vor Exit.

6. **live_check.py:75-77, Abweichung von Best Practices.** Das Script importiert interne Hermes-Module (`agent.web_search_registry`, `tools.web_tools`) ohne jede Versionsprüfung oder defensiven Versions-Hinweis zur Laufzeit. Nach einem Hermes-Update crasht es mit `ImportError`, ohne dass im Output steht, welche Version erwartet wurde.

7. **live_check.py:24, Edge Case.** `LOCALAPPDATA` existiert nur unter Windows; unter macOS/Linux degeneriert `ROOT` zum relativen Pfad `hermes`, der unbefugt auf Arbeitsverzeichnisse verweist. Der Docstring nennt Windows nicht als Voraussetzung, ein guard (z. B. Fehlermeldung bei fehlender Verzeichnisstruktur) fehlt.

8. **recompute.py:102, 108-109, Edge Case.** Das Dict `cell` und die nachfolgenden Index-Zugriffe erfordern jede Frage in allen vier Setups. Fehlt ein Eintrag (abgebrochener Lauf, unvollständiges CSV), crasht das Script mit `KeyError` statt einer aussagekräftigen Fehlermeldung.

9. **recompute.py:65, Inkonsistenz/Stil.** `seconds` wird über alle Runs (run2-main und run2-extra) gemittelt, `chars` nur über run2-main. Dieselbe Größe wird nach unterschiedlichen Filterkriterien aggregiert, was die Vergleichbarkeit der Spalte untergräbt.

10. **pyproject.toml:1-11, Stil.** Der Header-Kommentar sagt, das Plugin werde als Verzeichnis ohne diese Datei kopiert, aber `[project].dependencies` deklariert `httpx==0.28.1`. Da `[tool.uv] package = false` gilt, wird nichts installiert — die Dependency-Angabe ist dekorativ und für Leser irreführend (entweder aus [project] entfernen oder als Development-Hinweis kennzeichnen).
