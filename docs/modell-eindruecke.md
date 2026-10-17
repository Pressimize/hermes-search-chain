# Eindrücke der Review-Modelle

Eine Zeile je Modell und Review. Spalten: Modell-ID (exakt, ohne `opencode/`), Datum, PR/Branch, Dauer, Punkte gesamt / übernommen / Fehlalarme, Kurzurteil.

| Modell | Datum | PR | Dauer | Punkte ges./übern./Fehlalarm | Kurzurteil |
|---|---|---|---|---|---|
| muse-spark-1.3-contributor-free | 2026-10-16 | chore/second-opinion | 30s | 5/0/2 | Knapp, mit Zeilen. Fehlalarme: `big-pickle` sei falsche ID (ist korrekt), `kill` lasse opencode verwaist (timeout leitet SIGTERM weiter). Rest berechtigt, aber bewusst so gewollt (npm-Install, exclude-Eintrag, Basename-Kollision). |
| space-bunny-free | 2026-10-16 | chore/second-opinion | 20s | 5/0/1 | Gründlichste Antwort. Treffer: kein `--` vor dem Prompt, alte `.opinion/*.md` bleiben liegen, Rotation schweigt bei leerem Pool. Fehlalarm: verwaister opencode-Prozess. |
| cat-jam-free | 2026-10-16 | chore/second-opinion | 10s | 5/0/1 | Schnell, ohne Zeilennummern, überschneidet sich mit den anderen (Basename, `-`-Prompt). Regex-Hinweis zu `count_rows` praktisch folgenlos. |
| muse-spark-1.3-contributor-free | 2026-10-16 | chore/second-opinion | 35s | 5/0/3 | Zeilennummern passen nicht zur Datei. Treffer: `rm -rf` vor der Anhang-Prüfung, gelöschte Rate-Limit-Zeile verliert Info. Fehlalarme: fehlender Guard für `rm -rf` (WORK nie leer), Top-Modelle doppelt in der Rotation (TRIED verhindert das), `count_rows` nicht numerisch. |
| deepseek-v4.1-flash-free | 2026-10-16 | chore/second-opinion | 40s | 5/0/0 | Sachlich, mit Gewichtung. Wichtigster Treffer: Modelle ohne Antwort bleiben bei 0 Zeilen und werden immer wieder rotiert. Zwei Punkte beanstanden bewusste Entscheidungen (Leeren von `.opinion/`, eigener POOL). |
| big-pickle | 2026-10-16 | chore/second-opinion | 135s | 5/0/0 | Bester Beitrag dieses Laufs, sagt das Verhungern an `ll-alpha-free` konkret voraus (im selben Lauf 400s Timeout). Dazu: Prompt-Datei ungeprüft, `cp`-Fehler ignoriert. Langsam. |
| muse-spark-1.3-contributor-free | 2026-10-16 | chore/second-opinion | 55s | 5/0/2 | Antwort beginnt mit Statuszeilen („Kurzer Review läuft …“). Treffer: Glob im Duplikat-Check, kein Abbruch, wenn `mktemp -d` scheitert. Fehlalarme: Regex-Punkt in `count_rows` (praktisch folgenlos), rc 124 von opencode selbst. |
| deepseek-v4.1-flash-free | 2026-10-16 | chore/second-opinion | 45s | 5/0/2 | Treffer: Glob im Duplikat-Check, fehlende Tests (Fake-`opencode` + bats). `--` vor dem Prompt bewusst abgelehnt. Fehlalarme: Regex-Punkt, rc 143 statt Rate-Limit (kill folgt erst nach Log-Treffer). |
| longcat-2.5-preview-free | 2026-10-16 | chore/second-opinion | 190s | 5/0/3 | Langsam und oberflächlich, ohne Zeilennummern. Fehlalarme: `docs/` fehlt, `fail()` nicht atomar, Regex-Punkt. Dirty Tree durch `fail()` ist gewollt. |
| space-bunny-free | 2026-10-17 | review/nachtlauf-2026-10-17 (engines) | 75s | 9/1/0 | Gründlich, mit Zeilen und Beispielen. Treffer: fehlender Test für JSON-Fehler ohne bekanntes Feld (T-02). Übrige Punkte meist bewusste Entscheidungen (D14–D16, §10). |
| deepseek-v4.1-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (engines) | 186s | 7/0/0 | Prüft selbst nach („verifiziert“). Keine Treffer: Limit-Grenzen und `key=None` sind über den Provider nicht erreichbar. |
| mimo-v2.6-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (engines) | 185s | 7/0/1 | Strukturiert, aber ohne Treffer. Fehlalarm: leerer Fehlerkörper ergebe „HTTP 500 “ mit Leerzeichen. In den anderen drei Bereichen sechsmal Timeout (hängt still im Stream). |
| longcat-2.5-preview-free | 2026-10-17 | review/nachtlauf-2026-10-17 (engines) | 346s | 6/0/0 | Langsam, ohne Treffer; Kritik an bewusst gewählten Punkten (Key in Ergebniszeilen, Teilstring-Maskierung). Sonst nur Timeouts und leere Antworten. |
| beam-free | 2026-10-17 | review/nachtlauf-2026-10-17 (engines) | 85s | 7/0/0 | Neu (Rotation). Kurz, mit Beispielen, ohne Treffer; mehrere Punkte nicht erreichbar (negative Highlight-Zahl, Limit). |
| glm-5.3-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (engines, Nachholung) | 450s | 0/0/0 | Antwort enthält nur drei Statuszeilen, keine Befunde. Hat die Anhänge per Shell mit dem Repo-Stand verglichen. |
| big-pickle | 2026-10-17 | review/nachtlauf-2026-10-17 (engines, Nachholung) | 350s | 5/2/0 | Antwort enthält das ganze Nachdenken (126 KB). Treffer E-01 und T-02, aber erst nach dem Fix und mit Blick ins Repo, also nicht unabhängig. |
| space-bunny-free | 2026-10-17 | review/nachtlauf-2026-10-17 (provider) | 80s | 10/2/1 | Bester Beitrag: findet E-01 (Key mit Lone Surrogate → „malformed reply“) und Testlücke T-01. Fehlalarm: `get_provider_env` trimme vielleicht nicht (tut es). |
| deepseek-v4.1-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (provider) | 65s | 10/0/1 | Schnell. Fehlalarm: `requires_env` mache alle Keys zur Pflicht (Hermes lädt unabhängig davon). Rest bewusste Entscheidungen. |
| glm-5.3-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (provider) | 371s | 7/0/0 | Sauber begründet, ohne Treffer; fast alles in D14–D16 schon entschieden. |
| beam-free | 2026-10-17 | review/nachtlauf-2026-10-17 (provider) | 370s | 10/1/0 | Treffer E-01, aber Punkte und Beispiele fast wörtlich wie Space Bunny, dessen Antwort im selben Ordner lag. |
| big-pickle | 2026-10-17 | review/nachtlauf-2026-10-17 (provider, Nachholung) | 200s | 10/0/4 | Schwach: rechnet die Rundung der Restzeit falsch nach, hält grüne Tests für rot, widerlegt Punkt 10 selbst. |
| space-bunny-free | 2026-10-17 | review/nachtlauf-2026-10-17 (scripts) | 105s | 10/3/0 | Stark: findet `None chars` in recompute.py (S-01), Fehlanzeige im Live-Check (V-02) und nicht nachgerechnete Zahlen (V-03), mit Nachrechnung. |
| deepseek-v4.1-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (scripts) | 260s | 8/1/0 | Treffer V-02 mit konkretem Auslöser. Rest Kleinkram (Pause nach letzter Query, doppelte CI-Läufe). |
| glm-5.3-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (scripts) | 120s | 6/1/0 | Treffer S-01 (unterschiedliche Basis der Mediane), aber ohne das `None` zu bemerken. |
| beam-free | 2026-10-17 | review/nachtlauf-2026-10-17 (scripts) | 40s | 10/2/0 | Treffer S-01 und V-02, aber Zusammenstellung der Antworten von DeepSeek und GLM aus demselben Ordner. |
| space-bunny-free | 2026-10-17 | review/nachtlauf-2026-10-17 (spec) | 115s | 8/1/0 | Findet V-01 (Firecrawl `success: false` verliert den Grund). Übrige Punkte Dubletten oder bewusst. |
| deepseek-v4.1-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (spec) | 260s | 5/1/0 | Findet E-01 unabhängig und reproduziert es mit httpx 0.28.1; knapp und präzise. |
| beam-free | 2026-10-17 | review/nachtlauf-2026-10-17 (spec, Nachholung) | 105s | 5/0/0 | Kurz, ohne Treffer; erwartet ein `strip()`, das Hermes schon macht. |
| big-pickle | 2026-10-17 | review/nachtlauf-2026-10-17 (spec, Nachholung) | 230s | 4/1/0 | Gute Endfassung mit E-01, aber zitiert Space Bunnys Antwort aus dem Repo; gibt das Nachdenken mit aus (92 KB). |
| space-bunny-free | 2026-10-17 | review/nachtlauf-2026-10-17 (Isolation im Skript) | 70s | 10/1/2 | Erster Lauf mit Isolation, sah nur den Diff. Treffer: Temp-Ordner könnte bei passendem TMPDIR im Repo liegen (übernommen). Fehlalarme: Ordnerkollision zwischen Läufen und fehlendes Aufräumen (STAGE ist je Lauf neu und wird per trap gelöscht). |
| deepseek-v4.1-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (Isolation im Skript) | 70s | 10/1/2 | Gleicher Treffer (Lage von STAGE). Fehlalarme: Ordnerkollision, angeblich ungequotete Expansion. Zweifel an OPENCODE_CONFIG_CONTENT durch Probelauf widerlegt. |
| mimo-v2.6-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (Isolation im Skript) | 120s | 10/0/2 | Diesmal ohne Timeout. Kein Treffer; Fehlalarme: Ordnerkollision, „read nicht gesperrt“ (external_directory greift auch für read, im Probelauf belegt). |
| space-bunny-free | 2026-10-17 | review/nachtlauf-2026-10-17 (engines, isoliert) | 126s | 10/1/0 | Gründlich, ohne Shell aber kein bestätigter Fehler; nennt V-01 (Firecrawl `success: false`) mit Pausen-Aspekt. |
| glm-5.3-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (engines, isoliert) | 185s | 7/0/0 | Sachlich, nur bekannte bewusste Entscheidungen (Retry-After, Phasen-Timeout). |
| mimo-v2.6-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (engines, isoliert) | 545s | 8/2/0 | Isoliert viel besser als nachts: V-01 und V-05 unabhängig gefunden. |
| big-pickle | 2026-10-17 | review/nachtlauf-2026-10-17 (engines, isoliert) | 435s | 9/0/0 | Ohne fremde Antworten nur bekannte Punkte; Länge der Fehlertexte falsch als Bug gelesen (A4 legt sie so fest). |
| beam-free | 2026-10-17 | review/nachtlauf-2026-10-17 (engines, isoliert) | 45s | 8/0/0 | Schnell, oberflächlich, keine Treffer. |
| deepseek-v4.1-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (engines, isoliert, nach Rate-Limit) | 110s | 9/0/1 | Hält die Dateiablage der Anhänge für einen Importfehler; sonst bekannte Punkte. |
| space-bunny-free | 2026-10-17 | review/nachtlauf-2026-10-17 (provider, isoliert) | 110s | 10/1/0 | Findet V-04 (Einstellungen fehlen im Manifest); kann E-01 ohne engines.py und Shell nicht belegen. |
| deepseek-v4.1-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (provider, isoliert) | 75s | 9/0/0 | Knapp, nur bekannte Punkte. |
| glm-5.3-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (provider, isoliert) | 325s | 8/1/1 | V-04 gefunden, aber mit falscher Begründung (Einstellungen seien im Scope wirkungslos). |
| big-pickle | 2026-10-17 | review/nachtlauf-2026-10-17 (provider, isoliert) | 460s | 6/0/0 | Bekannte Punkte, Thread-Sicherheit schon in K5 beschrieben. |
| beam-free | 2026-10-17 | review/nachtlauf-2026-10-17 (provider, isoliert) | 35s | 7/0/0 | Kurz, keine Treffer. |
| mimo-v2.6-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (provider, isoliert, nach Rate-Limit) | 270s | 10/0/0 | Ordentlich, nur bekannte bewusste Entscheidungen. |
| deepseek-v4.1-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (scripts, isoliert) | 70s | 10/0/0 | Bemerkt `None chars` ohne Ausführen nicht. |
| glm-5.3-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (scripts, isoliert) | 461s | 9/0/0 | Nennt wieder nur die unterschiedliche Basis der Mediane (Teil von S-01). |
| mimo-v2.6-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (scripts, isoliert) | 305s | 10/0/0 | Gründlich, aber nur Robustheit bei veränderten Daten. |
| longcat-2.5-preview-free | 2026-10-17 | review/nachtlauf-2026-10-17 (scripts, isoliert) | 140s | 10/0/1 | Einzige brauchbare Longcat-Antwort; `IndexError` beim Zerlegen der Logzeile kann nicht auftreten. |
| big-pickle | 2026-10-17 | review/nachtlauf-2026-10-17 (scripts, isoliert) | 581s | 10/0/1 | Erfindet ein Logformat („paused for“ in der INFO-Zeile). |
| beam-free | 2026-10-17 | review/nachtlauf-2026-10-17 (scripts, isoliert) | 35s | 10/0/1 | Behauptet fehlendes `uv.lock` (liegt im Repo, nur nicht im Anhang). |
| space-bunny-free | 2026-10-17 | review/nachtlauf-2026-10-17 (spec, isoliert) | 260s | 7/2/0 | V-01 und V-05; Zeilenlänge vorsichtig als „falls nicht anders konfiguriert“ formuliert. |
| deepseek-v4.1-flash-free | 2026-10-17 | review/nachtlauf-2026-10-17 (spec, isoliert) | 351s | 6/1/0 | V-01 unabhängig; E-01 diesmal nicht (nachts nur durch Ausführen gefunden). |
| beam-free | 2026-10-17 | review/nachtlauf-2026-10-17 (spec, isoliert) | 85s | 10/0/1 | Rundung der Restzeit fälschlich als Abweichung gewertet. |
