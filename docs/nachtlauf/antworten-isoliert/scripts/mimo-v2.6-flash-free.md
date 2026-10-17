1. **recompute.py:108-111 – potenzieller Bug**  
   `cell[(a, q)]` setzt voraus, dass results.csv für jedes Setup jedes `id` aus questions.csv enthält. Fehlt auch nur eine Zelle (z. B. weil ein Setup abgebrochen ist), crasht `recompute.py` mit `KeyError` statt die Paarung auf der Schnittmenge zu bilden — anders als die Schleifen oben (Zeilen 83-94), die nur über tatsächlich vorhandene Zeilen laufen.

2. **recompute.py:119 – Edge Case**  
   `statistics.median(diffs)` wirft `StatisticsError`, wenn `diffs` leer ist. Das passiert, wenn für ein Feld (z. B. `search_seconds_median`) in allen Fragen eine Seite einen leeren String stehen hat; die Liste wird in Zeile 116 leer gefiltert, dann trotzdem gemittelt.

3. **recompute.py:87-90 – Edge Case**  
   `int(r["input_tokens"])`, `int(r["searches"])` und `int(r["page_fetches"])` stürzen auf leerem CSV-Feld mit `ValueError` ab (`int("")`), während `median()` in Zeile 43 gerade erst `""` herausfiltert. Ein fehlender Token-Wert bei nur einer Question reicht, um den gesamten Rechenlauf abzubrechen.

4. **live_check.py:102-107 – Edge Case**  
   Die Provider-Zählung und die Anzeige der Stufen hängen am genauen Logformat (`"="` in der Zeile, `": "` als Trenner). Ändert Hermes die Meldung (z. B. `"search-chain: stages exa, parallel"` ohne `=`), bleibt `info` leer, `steps` wird zum Platzhalter „no log line…", und `requests per provider` meldet überall 0, obwohl Requests liefen — ohne jeden Fehlercode.

5. **recompute.py:50 vs. 60-61 – Abweichung von Best Practices**  
   Für Run 1 ist die Spaltenliste hartkodiert (`"exa", "parallel", …`), für Run 2 wird sie aus `columns.csv` gelesen. Neue Provider in `columns.csv` erscheinen damit plötzlich nur noch in Run 2; eine entfernte Spalte führt in Run 1 zu stillen Nullen, ohne dass die beiden Blöcke dasselbe Quellenmodell haben.

6. **recompute.py:83-90 – Edge Case**  
   `by_category` zählt nur die drei Kategorien `"fact", "error", "current"`, `searches` und `fetches` summieren dagegen alle Zeilen des Setups. Eine Question mit anderer Kategorie (und ein in results.csv unbekanntes `id` erzeugt zusätzlich `KeyError` auf `category[r["id"]]`) geht in „correct" nicht ein, wohl aber in die fetch-/search-Summen im selben Print — die Kennzahlen beziehen sich damit auf unterschiedliche Mengen.

7. **live_check.py:109 – Performance**  
   `time.sleep(args.pace)` läuft auch nach der letzten Abfrage; bei den drei Standard-Queries und `--pace 7.5` kostet das am Ende 7,5 s Wartezeit ohne Ratenlimit-Nutzen. Ein `break`/`else` beziehungsweise Sleep nur zwischen den Iterationen wäre ausreichend.

8. **recompute.py:71-75 – Edge Case**  
   Existiert für `c["variant_of"]` im Run-2-Datensatz keine Spalte, liefert `scores()` ein leeres Dict, `pairs()` liefert `(0, 0)` und `sign_test` gibt `p 1.000` aus. Im Report sieht das aus wie „kein Unterschied", tatsächlich wurde aber gar nichts verglichen — es fehlt jede Kennzeichnung von „keine Daten".

9. **live_check.py:87-89 – Abweichung von Best Practices**  
   Der `Collect`-Handler wird dem Root-Logger hinzugefügt und nie wieder entfernt, und `setLevel` legt die Root-Schwelle dauerhaft auf INFO (bzw. niedriger). Für ein Kurzlebens-CLI unkritisch, aber ein `try/finally` mit `removeHandler` und Wiederherstellung des vorherigen Levels wäre robuster, gerade weil `hermes_env` den Prozess ohnehin global konfiguriert.

10. **ci.yml:4-5 – Abweichung von Best Practices**  
    `on: push` und `on: pull_request` ohne `concurrency` führen bei PRs im selben Repository zu zwei kompletten Matrix-Läufen (3.11/3.14) pro Push. Üblich ist `push` auf die Hauptbranches zu begrenzen oder eine `concurrency`-Gruppe mit `cancel-in-progress` zu setzen.
