# Nachtlauf 2026-10-17: Befunde

Jeder Befund der Modelle wurde am Code geprüft, wo möglich mit einem Skript oder Test. Mehrfachnennungen sind zusammengeführt. Grundlage für Aussagen über Hermes ist der Quellcode von Hermes Agent v0.21.6 (`agent/web_search_provider.py`, `tools/web_tools.py`, `hermes_cli/`), gegen den das Plugin geschrieben ist.

Kürzel der Modelle: **SB** space-bunny-free, **DS** deepseek-v4.1-flash-free, **GLM** glm-5.3-flash-free, **MM** mimo-v2.6-flash-free, **LC** longcat-2.5-preview-free, **BP** big-pickle, **BF** beam-free, **C** Claude (eigene Prüfung). Bereiche: `eng` engines, `prov` provider, `scr` scripts, `spec` Spezifikationsabgleich.

Urteile: **bestätigt** (nachvollzogen und reproduziert), **abgelehnt** (falsch, nicht erreichbar oder bewusste Entscheidung in `docs/design.md`), **unklar**.

## Bestätigt und umgesetzt

| ID | Kategorie | Fundstelle | Modelle | Urteil und Begründung | Commit |
|---|---|---|---|---|---|
| E-01 | Bug (Edge Case) | `search_chain/engines.py` `_post` | C; SB (prov #3, #9), BF (prov #3), DS (spec #1), BP (spec #1) | **bestätigt.** `client.post` lag im selben `try` wie `response.json()`. Kann httpx eine Anfrage nicht bauen (Key mit unsichtbarem Unicode-Zeichen wie U+200B aus Copy-and-paste, Query mit einzelnem Surrogat), wirft es `UnicodeEncodeError`, eine Unterklasse von `ValueError`; das landete im Zweig „malformed reply“, obwohl nichts gesendet wurde. A4 verlangt für Fehler ohne Antwort `<Provider>: <exception class>`. Reproduziert mit `engines.exa(client, "q", 5, "abc​defghij")` → `Exa: malformed reply`. Fix: eigener `except ValueError` nur um `client.post`. Kette, Pausen und Rückgabeformat unverändert; nur der Fehlertext in diesem Sonderfall lautet jetzt `Exa: UnicodeEncodeError`. Test: `test_request_that_cannot_be_built_is_no_malformed_reply` (6 Fälle, vorher rot). A4 in `design.md` und `CHANGELOG.md` (Unreleased) ergänzt. | `ee8f5a0` |
| S-01 | Bug (Dev-Werkzeug) | `scripts/recompute.py` Run-2-Zeilen | SB (scr #1), GLM (scr #3), BF (scr #6) | **bestätigt.** Firecrawl lief in Run 2 nur im Extra-Block; der Zeichen-Median wurde nur über den Haupt-Block gebildet, das Skript druckte `None chars`. `evaluation.md` und README nennen 3.900 Zeichen (Extra-Block); aus den Daten ergibt sich 3.925. Fix: Fällt der Haupt-Block leer aus, wird der Extra-Block genommen und mit „(extra block)“ gekennzeichnet. Test: `tests/test_recompute.py` (vorher rot). | `c9e1087` |
| T-01 | Testlücke | `tests/test_provider.py` | SB (prov #6) | **bestätigt.** Die in L1 festgelegte Logzeile `search-chain: no stage ran` wurde nie geprüft. Nur Test ergänzt; das Verhalten stimmte schon (Test von Anfang an grün). | `7c5c7dd` |
| T-02 | Testlücke | `tests/test_engines.py` | SB (eng #9b) | **bestätigt.** Eine Fehlerantwort, deren JSON weder `tag` noch `error` noch `message` hat, war ungetestet (A4: dann der Antworttext). Nur Test ergänzt; Verhalten stimmte schon. | `c5171d8` |

## Bestätigt, nicht umgesetzt (Vorschläge)

| ID | Kategorie | Fundstelle | Modelle | Befund und Grund, warum nicht umgesetzt | Skizze |
|---|---|---|---|---|---|
| V-01 | Diagnose | `search_chain/engines.py` `firecrawl()` | SB (spec #4) | **bestätigt (Code), Auswirkung unklar.** Eine 2xx-Antwort von Firecrawl mit `success: false` wird zu `Firecrawl: malformed reply`; ein Grund im Body (`error`) geht verloren. Ob Firecrawl so antwortet, ist nicht belegt (Fehler kamen in beiden Vergleichsläufen als Nicht-2xx). Würde den Fehlertext ändern (nach außen sichtbar) → Andres Entscheidung. | Bei `success is False` und einem `error`-Text: `_error("Firecrawl", f"HTTP {status} {error}", "rejected", key, status)` statt `_malformed`; Test analog `test_firecrawl_unexpected_reply`. Pause bleibt aus, weil der Status 2xx ist. Nachtrag: In der isolierten Runde unabhängig von SB, MM (engines), SB und DS (spec) genannt; SB und MM weisen darauf hin, dass ein so gemeldetes leeres Kontingent keine 24-h-Pause auslöst. Wer das will, könnte bei einem `error`-Text mit „Payment Required“/„credits“ den Status 402 annehmen (heuristisch, deshalb nur Vorschlag). |
| V-02 | Bug (Dev-Werkzeug) | `scripts/live_check.py` Auswertung der Logzeilen | DS (scr #1), SB (scr #8), BF (scr #1) | **bestätigt (Codelesen).** Scheitert ein Aufruf vor der ersten Stufe (`search-chain: no stage ran`) oder ist die Query leer (`search-chain: empty_query`), enthält keine Logzeile ein `=`; das Skript meldet dann „(no log line: served from Hermes' cache?)“. Der Fehlertext erscheint aber in derselben Zeile. Nicht umgesetzt, weil das Skript nur mit einer echten Hermes-Installation läuft und sich der Fehler ohne Umbau nicht rot/grün testen lässt. | Filter auf `"paused for" not in line and "call failed" not in line` statt `"=" in line`; dann ist die letzte INFO-Zeile immer die des Plugins. |
| V-03 | Lücke (Dev-Werkzeug) | `scripts/recompute.py` | SB (scr #5) | **bestätigt.** Nicht jede veröffentlichte Zahl wird nachgerechnet: die Paarvergleiche von Run 1 (`evaluation.md`: Exa gegen Firecrawl, p 0,03) und „current version in a snippet, both sets, of 16“. Die Zahlen selbst stimmen (SB hat 6:0, p 0,031 nachgerechnet). Erweiterung, kein Fehler. | Zwei Ausgabeblöcke ergänzen: Run-1-Paare mit `pairs()`/`sign_test()`, „current version“ über `run2-results.csv` beider Blöcke. |

| V-04 | Konfiguration | `search_chain/plugin.yaml` | SB, GLM (isoliert, provider) | **bestätigt (Lücke), kein Fehler.** `SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS` und `SEARCH_CHAIN_PARALLEL_API` stehen nicht im Manifest. Sie wirken trotzdem: `build_profile_secret_scope` in Hermes v0.21.6 übernimmt die ganze Profil-`.env` (GLMs Gegenbehauptung ist falsch). Eine Manifest-Änderung ist Andres Entscheidung. | Beide als `optional_env` mit `description` (Standard 600 bzw. Beta-Endpunkt) in `plugin.yaml` aufnehmen; `test_manifest_and_register` erweitern. |
| V-05 | Spezifikation | `search_chain/engines.py` `_rows`, design.md A4 | SB (isoliert, spec), MM (isoliert, engines) | **bestätigt (Unschärfe).** Fehlt in einer 2xx-Antwort von Exa oder Parallel das Feld `results`, wertet der Code das absichtlich als „no results“ (`if items is None`); A4 lässt sich so lesen, dass das `malformed` wäre. Die Kette läuft in beiden Fällen weiter. | A4 um einen Satz ergänzen: „Eine 2xx-Antwort ohne Ergebnisliste zählt als gültige Antwort ohne Treffer.“ Kein Code. |

## Abgelehnt

Gruppiert; je Gruppe der Grund. Die Nummern in Klammern verweisen auf die Antwortdateien in `antworten/<bereich>/`.

### A. `limit` in den Engine-Funktionen (Obergrenze nur bei Parallel, keine Untergrenze, kein Typ-Check)
Genannt von allen Modellen: SB (eng #1, #2; prov #1; spec #3), DS (eng #1, #2; prov #4; spec #2, #5), MM (eng #3, #4), LC (eng #3), BF (eng #2, #3; prov #1; spec #1), GLM (prov #2), BP (spec #2).
**Abgelehnt: nicht erreichbar.** Der Provider klemmt `limit` vor jedem Aufruf auf 1 bis 20 (A6, `test_limit_is_kept_between_1_and_20`). Hermes übergibt immer eine ganze Zahl: `web_search_tool` macht `int(limit)` und rundet auf einen Bucket. Die Engine-Funktionen sind interne Funktionen dieses Plugins. `None`, Text oder Kommazahlen kommen nicht an; käme doch einer, fängt S5 den Fehler.

### B. Rückgabewert von `get_provider_env` könnte `None` sein oder nicht getrimmt
SB (prov #9; spec #5), DS (eng #3; prov #10), BF (prov #9; spec #3).
**Abgelehnt: falsche Annahme über die API.** In Hermes v0.21.6 gibt `get_provider_env` immer `(val or "").strip()` zurück, also einen getrimmten String. Der Test-Stub in `conftest.py` bildet genau das nach.

### C. Breite `except`-Klauseln, verlorene Ausnahmetexte, `_env` schluckt jeden Fehler
SB (eng #6), DS (eng #6; prov #6, #9), MM (eng #2), LC (eng #5), GLM (prov #4, #5), BF (prov #5, #6; spec #4: `KeyboardInterrupt`).
**Abgelehnt: dokumentierte Entscheidung** (D16: „the three broad except clauses are deliberate (S3, S5, A4)“). Nur der Klassenname gelangt in Fehlertexte, damit kein Key und kein Fremdtext mitkommt. `KeyboardInterrupt`/`SystemExit` abzufangen wäre falsch.
Anmerkung: Aus genau diesem Umfeld kam der bestätigte Befund E-01, der aber einen anderen Mechanismus hat (`ValueError` im falschen Zweig).

### D. Ein `httpx.Client` je Aufruf, kein Verbindungs-Pool
SB (prov #4), DS (prov #5), GLM (prov #1).
**Abgelehnt: D14** (gemessen: 9 ms je Client, httpx schließt Leerlauf-Verbindungen nach 5 s).

### E. Pausentabelle wird nie aufgeräumt, `Retry-After` ignoriert
SB (prov #7), DS (prov #2, #8), GLM (prov #6), BF (prov #7).
**Abgelehnt: D15** (höchstens ein Eintrag je Stufe und Key; nach 429 geht die Kette ohnehin weiter).

### F. Kein Zeitlimit für die ganze Suche, httpx-Timeouts je Phase
SB (prov #5), MM (eng #1).
**Abgelehnt: A0 und D13.**

### G. Ergebniszeilen werden nicht bereinigt (Key, Steuerzeichen); roher Antworttext im Fehlertext
SB (eng #5, #7; spec #2), LC (eng #1).
**Abgelehnt.** Design §10: Titel und Beschreibungen sind Fremdinhalt und erreichen das Modell, wie der Anbieter sie schickt; Hermes markiert Suchergebnisse als nicht vertrauenswürdig. S3 verlangt die Maskierung für Fehlertexte und Logs; die Logzeile (L1) enthält keine Ergebnisse. Dass ein Suchanbieter den Key des Aufrufers in einem Treffer zurückgibt, ist kein realistischer Pfad. Der Antworttext als Detail ist in A4 so festgelegt.

### H. Form der Antworten: ein Nicht-Objekt in der Liste macht die ganze Antwort „malformed“; fehlendes `results` gilt als „keine Treffer“; `excerpts`/`highlights` als String
SB (eng #3, #4; spec #1), DS (eng #5; spec #3), BP (spec #3).
**Abgelehnt.** A4: eine 2xx-Antwort, die nicht das erwartete JSON ist, ist `malformed`; so festgehalten in `test_malformed_reply`. In beiden Fällen fragt die Kette die nächste Stufe (K4), nur der Grund im Fehlertext unterscheidet sich. Hermes' eigene Exa- und Parallel-Provider behandeln `highlights`/`excerpts` ebenfalls als Liste (`" ".join(r.highlights or [])`). Eine Änderung würde das Verhalten ändern.

### I. URL-Regel und Nummerierung
SB (eng #5: Großschreibung, Steuerzeichen in URL), BF (eng #4: Leerzeichen am Ende), MM (eng #7: `position` neu durchgezählt), SB (eng #8: Weiterleitungen).
**Abgelehnt: S4** („the URL is passed on as sent“, Position zählt ab 1 über die übernommenen Zeilen; Hermes prüft URLs selbst, bevor es sie abruft). Weiterleitungen: Die drei APIs leiten nicht weiter; `test_only_2xx_is_a_reply` legt 302 als Fehler fest.

### J. Leerer Fehlerkörper ergebe „HTTP 500 “ mit Leerzeichen am Ende
MM (eng #5).
**Abgelehnt: falsch.** `_error` normalisiert den ganzen Text; nachgeprüft: `Exa: HTTP 500`.

### K. Kleinigkeiten in `_detail`: falsy Werte, verschachtelte `message`, Liste als Python-Darstellung
DS (eng #4; spec #4), BF (eng #5; spec #2), SB (spec #6), BP (spec #4).
**Abgelehnt.** Nachgeprüft: `{"error": ["a","b"]}` ergibt `HTTP 400 ['a', 'b']` – lesbar und folgenlos. Dass ein leeres Feld übersprungen wird, liefert einen aussagekräftigeren Grund als ein leerer String; das Wort „present“ in A4 so wörtlich zu nehmen, verschlechtert die Meldung. Keiner der dokumentierten Fehlerkörper der drei Anbieter ist betroffen.

### L. Interrupts
SB (prov #2), BF (prov #4): Fallback bei fehlendem `tools.interrupt` still. DS (prov #7), GLM (prov #7): `"Interrupted"` ohne Präfix.
**Abgelehnt: S6.** `tools.interrupt.is_interrupted` existiert in Hermes v0.21.6 (`web_search_tool` importiert es selbst). `"Interrupted"` ist genau der Text, den Hermes' `web_search_tool` und die eingebauten Provider liefern.

### M. `requires_env` im Manifest mache alle drei Keys zur Pflicht
DS (prov #1).
**Abgelehnt.** In Hermes v0.21.6 wird `requires_env` nur zum Abfragen bei der Installation, im Katalog und in `hermes doctor` verwendet; das Laden des Plugins hängt nicht daran. `is_available()` entscheidet, und die ist mit einem Key wahr (S2).

### N. Test-Umgebung: `conftest.py` ersetzt das Hermes-Modul, Proxy-Test verbindet auf Port 9, `request.extensions["timeout"]`, Helfer `capture`
SB (prov #8, #10), GLM (prov #3), BF (prov #8, #10; eng #7), DS (eng #7).
**Abgelehnt.** Der Stub ist gewollt (T1: Tests laufen ohne Hermes); T1 nennt den einen Test, der eine Verbindung zu einem geschlossenen lokalen Port öffnet. `extensions["timeout"]` ist eine dokumentierte Request-Extension von httpx. Alle Anfragen haben einen JSON-Körper.

### O. Negativer `highlight_chars` würde gesendet
LC (eng #2), BF (eng #1).
**Abgelehnt: nicht erreichbar.** Der Provider übernimmt nur Werte aus einer bis sechs Ziffern (A1).

### P. Key-Maskierung trifft auch Teilstrings anderer Wörter
LC (eng #6).
**Abgelehnt: S3** maskiert bewusst jede wörtliche Wiederholung ab 8 Zeichen; lieber ein verstümmeltes Wort als ein Key im Log.

### Q. Leistung: ganzer Antworttext wird gelesen und durchsucht
MM (eng #6), LC (eng #4), SB (spec #8: Einstellungen je Aufruf gelesen).
**Abgelehnt: D16** (httpx hält den Körper schon im Speicher, bevor gekürzt werden könnte) und **D15** (Einstellungen werden je Aufruf gelesen, damit mehrere Profile in einem Prozess funktionieren).

### R. Engine-Ergebnis ohne `code`/`status` → `KeyError`; `_error` mit `key=None`
DS (prov #3; eng #3), BF (prov #2).
**Abgelehnt: nicht erreichbar.** Jede Engine-Funktion liefert entweder `rows` oder ein Dict aus `_error` mit `code` und `status`; Keys sind immer Strings (siehe B).

### S. Pausengrund ist auf 200 Zeichen gekürzt
BF (spec #5).
**Abgelehnt:** K5 wiederholt den Fehlertext der Antwort, und dieser ist nach A4 auf 200 Zeichen gekürzt. So gewollt.

### T. Stil: viele Positionsargumente in `_post`, `STAGES` als Tupel
SB (spec #7).
**Abgelehnt:** Stilfrage ohne Fehlerbild; alle Aufrufe sind getestet.

### U. `recompute.py`: fest verdrahtete Nenner, `KeyError`/`ValueError` bei veränderten Daten, Duplikate, Sekunden-Median über beide Blöcke, `p 0.000`, `p 1.000` bei 0:0
SB (scr #2, #3, #6, #7), DS (scr #5), GLM (scr #1, #2, #3 – Sekunden), BF (scr #7, #8).
**Abgelehnt.** Die Daten sind veröffentlicht und fest; CI rechnet bei jedem Push nach, ein Bruch würde sofort rot. Der Sekunden-Median über beide Blöcke entspricht den veröffentlichten Zeiten (Exa 2,0 s, Firecrawl 1,3 s). `p 0.000` ist eine Rundung, `evaluation.md` schreibt richtig „below 0.001“; der Vorzeichentest mit 0:0 hat per Definition p = 1. (Der Zeichen-Median ist dagegen als S-01 bestätigt.)

### V. `live_check.py`: alle `*_API_KEY` werden entfernt, Einstellungen aus der Shell bleiben, `interrupted` zählt als Anfrage, `json.loads(None)`, Pause nach der letzten Query, „below 8 requests/min“, relativer Pfad unter Linux, Root-Log-Level
SB (scr #9, #10), DS (scr #2, #3, #4, #6, #7), GLM (scr #4, #5), BF (scr #2, #3, #4, #5).
**Abgelehnt.** Alle Keys werden entfernt, damit sie nur aus der `.env` des Profils kommen (Docstring). Der Docstring verspricht das für Keys, nicht für Einstellungen. Ein Skript ohne Bedienoberfläche kann nicht unterbrochen werden. `web_search_tool` gibt in Hermes v0.21.6 immer einen JSON-String zurück. Die Pause nach der letzten Query hält das Tempo auch über die drei direkt aufeinanderfolgenden Läufe von T2. Da jede Anfrage selbst Zeit braucht, bleibt die Rate unter 8 pro Minute. Das Skript ist für Hermes Desktop unter Windows geschrieben und nimmt `HERMES_ROOT` an. INFO muss eingeschaltet sein, um die Logzeile zu sehen.

### W. CI und Projektdatei: `> /dev/null`, doppelte CI-Läufe, gepinntes `httpx`
SB (scr #4), BF (scr #9, #10), DS (scr #8), GLM (scr #6).
**Abgelehnt.** T4 verlangt nur, dass `recompute.py` in CI läuft; ein Vergleich gegen eine gespeicherte Ausgabe wäre ein neues Verfahren (S-01 hätte er gefunden, daher als Idee in der Zusammenfassung). Doppelte Läufe kosten nur CI-Zeit. Der Pin auf `httpx==0.28.1` ist bewusst die Version von Hermes v0.21.6 (Kommentar in `pyproject.toml`).

### X. Big Pickle, Nachholrunde provider: Rundung der Restzeit, Grenzfall am Pausenende, `surrogatepass`, Log-Detail, Einstellungen mit Leerzeichen
BP (prov #1–#4, #8–#10).
**Abgelehnt: sachlich falsch oder so spezifiziert.** #1 rechnet die Restzeit falsch nach (nach 81.001 s bleiben 5.399 s, nicht 6.399 s; `_left` ergibt „1 h“, wie der Test erwartet). #8/#9 übersehen, dass `get_provider_env` trimmt (siehe B); die Tests mit `" 1200 "` und `" V1 "` laufen grün. #10 widerlegt sich in der Antwort selbst. Pausenende bei `left == 0` ist getestet (`test_pause_after_quota_and_rate_limit`). `surrogatepass` hält gerade einen solchen Key vom Abbruch der Kette ab (`test_key_that_cannot_be_encoded_fails_only_its_stage`). Das Log-Detail ohne Providernamen ist das Format von L2.

## Hinweis zur Unabhängigkeit der Antworten

Die Modelle laufen im `opencode`-Agentenmodus mit Shell- und Lesezugriff. Sie lesen nicht nur die Anhänge, sondern durchsuchen das Repository: Big Pickle zitiert in der Spec-Nachholrunde „Space-Bunnys Befund“ aus `docs/nachtlauf/antworten/`, GLM verglich die Anhänge mit dem Arbeitsstand („die angehängten Dateien sind älter als der Repo-Stand“) und versuchte, Dateien außerhalb des Repos zu lesen; Beams Antworten zu provider und scripts gleichen in Wortlaut und Beispielen denen von Space Bunny, DeepSeek und GLM, die vorher im selben Ordner lagen. Unabhängig voneinander und vor dem Fix gefunden wurde E-01 nur von Claude, Space Bunny (provider) und DeepSeek (spec). Mehrfachnennungen sind daher kein Maß für Gewicht.

## Nachtrag: isolierte Nachholrunde

Alle Modelle wurden für alle Bereiche erneut gefragt, diesmal abgeschottet (siehe `isoliert.md`). Neu bestätigt sind nur die Vorschläge V-04 und V-05; die neu abgelehnten Punkte stehen mit Grund in `isoliert.md`, Abschnitt *Neu abgelehnt*. E-01 und S-01 fand ohne Shell kein Modell.

## Unklar

Keine. Wo ein Befund nicht eindeutig war, wurde er am Hermes-Quellcode oder mit einem Skript entschieden.
