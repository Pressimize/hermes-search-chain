# Nachtlauf 2026-10-17: Zusammenfassung

## In Kürze

Das Plugin wurde über Nacht von sieben kostenlosen KI-Modellen und von Claude geprüft. Die Modelle haben zusammen 144 Hinweise geliefert. Jeder Hinweis wurde am Code nachgeprüft. Fast alle waren unbegründet: Sie beschreiben Fälle, die im echten Betrieb nicht eintreten können, sie beruhen auf falschen Annahmen über Hermes, oder sie kritisieren Entscheidungen, die schon begründet im Design-Dokument stehen.

Bestätigt haben sich ein kleiner Fehler im Plugin und ein kleiner Fehler in einem Hilfsskript. Beide sind behoben und mit Tests abgesichert. Am Verhalten der Suchkette ändert sich nichts: gleiche Anbieter, gleiche Reihenfolge, gleiche Einstellungen, gleiches Ergebnisformat. Der Plugin-Fehler betrifft nur einen seltenen Sonderfall: Enthält ein API-Key versehentlich ein unsichtbares Zeichen (etwa beim Kopieren aus einer Webseite), stand im Fehlertext bisher „malformed reply“ (kaputte Antwort des Anbieters). Jetzt nennt der Fehlertext die eigentliche Ursache, `UnicodeEncodeError`. Die Kette ging in beiden Fällen schon richtig zum nächsten Anbieter weiter.

Drei weitere Punkte sind als Vorschlag notiert. Einer davon würde einen Fehlertext ändern, den das Modell sieht, und braucht deshalb Andres Entscheidung. Die beiden anderen betreffen nur Entwicklerwerkzeuge.

Außerdem zeigte sich: Die Modelle lesen beim Prüfen auch das Repository und die Antworten der anderen Modelle. Ihre Antworten sind daher nicht unabhängig voneinander (siehe unten).

## Was gemacht wurde

- **Phase 0:** `scripts/second-opinion.sh` um vier Punkte ergänzt: `mktemp -d` wird geprüft, doppelte Anhangnamen werden exakt verglichen (ohne Glob), ein Anhang namens `<modell>.md`/`<modell>.log` bricht ab, eine Sperre (`flock` auf `.opinion.lock`, in `.git/info/exclude`) verhindert parallele Läufe. Jeden Punkt einzeln getestet, dazu ein Probelauf mit Prompt-Datei. PR #1 per Squash gemergt (`5287a03`), `main` aktualisiert.
- **Ausgangslage:** 150 Tests grün, ruff sauber, `recompute.py` läuft.
- **Vier Prüfbereiche** (`plan.md`): `engines` (REST-Aufrufe), `provider` (Kette, Pausen, Manifest), `scripts` (Live-Check, Nachrechnung, CI), `spec` (Code gegen `docs/design.md`).
- **Modelle:** Je Bereich alle acht Modelle der Rangfolge (`OPINION_COUNT=8`) plus Rotation. `muse-spark-1.3-contributor-free` und `cat-jam-free` gibt es bei OpenCode nicht mehr („Model not found“), `ll-alpha-free` ebenfalls nicht. Neu ist `beam-free`; es wurde über `OPINION_POOL` an die Spitze der Rotation gestellt. Das Skript selbst und die Rangfolge sind unverändert, denn die Rangfolge ändert nur Andre.
- **Aufrufe:** 48 in der Nacht, davon 20 mit Antwort, 16 Timeouts (400 s, in der Nachholrunde 700 s), 8× „Model not found“, 3 leere Antworten, 1 Aufruf beim Zeitlimit des Hintergrundlaufs abgebrochen. **Keine Rate-Limits** in der Nacht (im Probelauf von Phase 0 eines bei DeepSeek). Die Modelle mit Timeout wurden je Bereich einmal nachgeholt, gegen denselben Codestand wie in der ersten Runde.
- **Antworten:** `docs/nachtlauf/antworten/<bereich>/`, Prompts in `docs/nachtlauf/prompts/`, Fehlversuche in `docs/modell-fehlversuche.md` (vom Skript geschrieben).
- **Prüfung:** 144 Einzelbefunde, zusammengeführt in `befunde.md`. Behauptungen über Hermes wurden am Quellcode von Hermes Agent v0.21.6 geprüft (z. B. gibt `get_provider_env` immer einen getrimmten String zurück, und `web_search_tool` übergibt immer eine ganze Zahl als `limit`).
- **Ende:** 161 Tests grün (vorher 150), ruff sauber.

## Umgesetzte Fixes

| ID | Problem | Auswirkung | Wie getestet |
|---|---|---|---|
| E-01 | Konnte httpx eine Anfrage gar nicht erst bauen (Key mit unsichtbarem Unicode-Zeichen, Suchanfrage mit einzelnem Surrogat), meldete das Plugin „malformed reply“, obwohl nichts gesendet worden war. | Irreführender Fehlertext und Logcode `malformed` statt `UnicodeEncodeError`. Die Kette lief schon vorher korrekt weiter; jetzt stimmt der Grund, wie A4 ihn vorsieht. Nur der Text dieses Sonderfalls ändert sich, nicht das Format. | Neuer Test mit 6 Fällen (3 Anbieter × Key/Query): vorher rot, danach grün; ganze Suite grün. A4 in `design.md` und `CHANGELOG.md` (Abschnitt Unreleased, keine neue Version) ergänzt. |
| S-01 | `scripts/recompute.py` gab für Firecrawl in Run 2 `None chars` aus, weil Firecrawl dort nur im Extra-Block lief. | Die veröffentlichte Zahl „3.900 Zeichen“ ließ sich mit dem Skript nicht nachrechnen. Jetzt: `3925.0 chars (extra block)`. | Neues `tests/test_recompute.py`: vorher rot, danach grün. |
| T-01 | Die Logzeile `search-chain: no stage ran` (L1) war ungetestet. | Keine; nur Absicherung. | Test ergänzt, von Anfang an grün. |
| T-02 | Eine Fehlerantwort, deren JSON kein bekanntes Feld hat, war ungetestet (A4). | Keine; nur Absicherung. | Test ergänzt, von Anfang an grün. |

Je Fix ein Commit mit der ID im Text. Keine neuen Abhängigkeiten, keine neue Versionsnummer, nichts veröffentlicht.

## Vorschläge, die Andres Entscheidung brauchen

- **V-01 (Verhalten):** Antwortet Firecrawl mit HTTP 2xx und `success: false`, meldet das Plugin „malformed reply“ und verwirft den Grund aus der Antwort. Vorschlag: den `error`-Text der Antwort übernehmen (Skizze in `befunde.md`). Das ändert einen Fehlertext, den das Modell sieht. Ob Firecrawl je so antwortet, ist nicht belegt; in beiden Vergleichsläufen kamen Fehler als Nicht-2xx.
- **V-02 (nur Entwicklerwerkzeug):** `live_check.py` zeigt einen Aufruf, der vor der ersten Stufe scheitert, als „served from Hermes' cache?“ an. Der Fehlertext steht aber in derselben Zeile. Ein Fix ist einfach (Skizze), lässt sich ohne Hermes aber nicht rot/grün testen, deshalb nicht umgesetzt.
- **V-03 (nur Entwicklerwerkzeug):** `recompute.py` rechnet nicht alle veröffentlichten Zahlen nach (Paare von Run 1, „current version … of 16“). Die Zahlen selbst stimmen.
- **Idee:** CI vergleicht die Ausgabe von `recompute.py` nicht mit einem gespeicherten Stand. Ein solcher Vergleich hätte S-01 gefunden. Das wäre ein neues Verfahren (T4), daher nur als Idee notiert.

## Abgelehnte Befunde (gruppiert, Details in `befunde.md`)

- **Nicht erreichbar** (die häufigste Gruppe, von allen Modellen genannt): Grenzen und Typ von `limit` in den Engine-Funktionen, negative Highlight-Zahl, `key=None`, Engine-Ergebnis ohne `code`. Der Provider klemmt und prüft vorher, und Hermes übergibt nur ganze Zahlen und Strings.
- **Falsche Annahmen über Hermes oder httpx:** `get_provider_env` liefere `None` oder trimme nicht; `requires_env` mache alle drei Keys zur Pflicht; `request.extensions["timeout"]` sei intern; `web_search_tool` könne `None` liefern.
- **Bewusste Entscheidungen aus `design.md`:** breite `except`-Klauseln und nur der Klassenname im Fehlertext (D16, S5), ein Client je Aufruf (D14), Pausentabelle ohne Aufräumen und ohne `Retry-After` (D15), kein Gesamtzeitlimit (D13), Ergebniszeilen als unveränderter Fremdinhalt (§10), URL-Regel und Nummerierung (S4), Form „malformed“ bei unerwarteten Listen (A4), `"Interrupted"` als Text (S6), Test-Stub und Port-9-Test (T1).
- **Sachlich falsch:** „HTTP 500 “ mit Leerzeichen (der Text wird normalisiert), falsch nachgerechnete Rundung der Restzeit (Big Pickle), grüne Tests für rot gehalten.
- **Kleinkram ohne Fehlerbild:** Python-Darstellung einer Liste im Fehlertext, Stil der Argumente, Pause nach der letzten Live-Check-Abfrage (hält das Tempo über aufeinanderfolgende Läufe), doppelte CI-Läufe, `p 0.000` statt „below 0.001“.

## Eindrücke je Modell

| Modell | Antworten | Treffer | Fehlalarme (sachlich falsch) | Tempo | Urteil |
|---|---|---|---|---|---|
| space-bunny-free | 4 von 4 | alle 7 bestätigten IDs mitgefunden (E-01, S-01, T-01, T-02, V-01–V-03) | 1 | 75–115 s | Klar das nützlichste Modell der Nacht: konkrete Zeilen, nachgerechnete Beispiele, wenig Rauschen. |
| deepseek-v4.1-flash-free | 4 von 4 | E-01 (unabhängig, reproduziert), V-02 | 1 | 65–260 s | Zuverlässig und präzise, führt Code selbst aus. Zweitbestes Modell. |
| glm-5.3-flash-free | 3 von 6 Versuchen, eine davon ohne Befunde | S-01 (teilweise) | 0 | 120–450 s, 2 Timeouts, 1 leer | Sauber begründet, aber wenig Neues; sucht per Shell außerhalb der Anhänge. |
| beam-free (neu) | 4 von 4 | E-01, S-01, V-02 – jeweils abgeschrieben | 0 | 40–370 s | Schnell und knapp, aber in zwei Bereichen fast wörtliche Kopie der Antworten, die vorher im selben Ordner lagen. Eigene Punkte ohne Treffer. |
| big-pickle | 3 von 7 Versuchen | E-01, T-02 – nach Blick ins Repo | 4 | 200–350 s, 3 Timeouts | Gibt das ganze Nachdenken mit aus (bis 126 KB). Eine gute Spec-Antwort, eine schwache provider-Antwort mit Rechenfehlern. |
| mimo-v2.6-flash-free | 1 von 7 Versuchen | – | 1 | 185 s, sonst 6 Timeouts | Hängt meist still im Stream bis zum Timeout; die eine Antwort ohne Treffer. |
| longcat-2.5-preview-free | 1 von 7 Versuchen | – | 0 | 346 s, sonst 4 Timeouts und 2 leere Antworten | Langsam und in dieser Nacht praktisch nicht nutzbar. |
| muse-spark-1.3-contributor-free, cat-jam-free | 0 von 4 je Modell | – | – | – | Bei OpenCode nicht mehr verfügbar. Andre sollte sie aus der Rangfolge nehmen; ich habe die Rangfolge nicht geändert. |

Gegenüber Andres Rangfolge fallen zwei Abweichungen deutlich aus: Muse Spark und Cat Jam fehlen ganz, und MiMo und Longcat sind praktisch unbrauchbar. Space Bunny und DeepSeek tragen die Prüfung. Eine Zeile je Antwort steht in `docs/modell-eindruecke.md`.

### Unabhängigkeit der Antworten

`opencode run` arbeitet als Agent mit Shell- und Lesezugriff. Die Modelle beschränken sich nicht auf die Anhänge: Sie lesen frühere Antworten in `.opinion/` (das Rotationsmodell läuft zuletzt im selben Ordner) und die gesicherten Antworten unter `docs/nachtlauf/antworten/`. GLM verglich die Anhänge mit dem aktuellen Repo-Stand und versuchte, Dateien außerhalb des Repos zu lesen. Für die Nachholrunden wurden die gesicherten Antworten deshalb vorübergehend aus dem Repo verschoben. Echt unabhängig wurde E-01 von Claude, Space Bunny und DeepSeek gefunden. Vorschlag für das Skript, von Andre zu entscheiden: jedes Modell in einem eigenen, leeren Ordner außerhalb des Repos laufen lassen und Shell und Lesen außerhalb dieses Ordners verbieten (opencode-Berechtigungen).

## Nachtrag: isolierte Nachholrunde (Vormittag 2026-10-17)

Auf Andres Wunsch wurden alle Fälle nachgeholt, in denen ein Modell fremde Antworten gesehen haben konnte, und alle ausgefallenen. Vorher wurde das Skript geändert: Jedes Modell arbeitet jetzt in einem eigenen leeren Ordner außerhalb des Repos, ohne Shell und ohne Zugriff nach außen. Ergebnis in `isoliert.md`, kurz:

- 35 Aufrufe, 21 Antworten; MiMo lief diesmal fast ohne Timeouts, Space Bunny wurde ab 09:24 UTC von OpenCodes Free-Tier gesperrt.
- **Ohne Shell fand kein Modell die beiden echten Fehler (E-01, S-01).** In der Nacht hatten die Modelle sie durch Ausführen des Codes gefunden. Die Antworten sind jetzt unabhängig, aber flacher.
- V-01 (Firecrawl `success: false`) nennen jetzt vier Antworten unabhängig. Neu als Vorschlag: V-04 (Einstellungen ins Manifest als `optional_env`) und V-05 (A4 präzisieren). Beide brauchen Andres Entscheidung.
- Beams Treffer der Nacht sind ohne Vorlage verschwunden. Das bestätigt, dass sie abgeschrieben waren.

## Abweichungen vom Auftrag

- Der Hintergrundlauf der ersten Runde wurde nach 2 Stunden beim letzten Modell des Bereichs `spec` abgebrochen. Die bis dahin vorliegenden Antworten wurden gesichert, die fehlenden Modelle nachgeholt.
- Die Nachholrunden liefen mit `OPINION_TIMEOUT=700`, ohne Rotation (`OPINION_POOL=" "`) und gegen die Dateien aus `main`, damit alle Modelle denselben Codestand sehen.
- Der Probelauf in Phase 0 („Sag nur OK.“) ist kein Review; dafür gibt es keine Zeilen in `modell-eindruecke.md`. Seine Fehlversuche stehen in `modell-fehlversuche.md`.
- T-01 und T-02 sind reine Testergänzungen ohne vorheriges Rot, weil das Verhalten bereits stimmte.
