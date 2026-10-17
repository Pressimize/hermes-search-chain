# Nachtlauf, Nachtrag 2026-10-17: isolierte Nachholrunde

## Warum

In der Nacht liefen die Modelle mit Shell- und Lesezugriff im Repository. Sie konnten die Antworten anderer Modelle lesen (`.opinion/`, `docs/nachtlauf/antworten/`) und taten es nachweislich (Big Pickle zitierte Space Bunny, Beam kopierte fast wörtlich, GLM verglich mit dem Repo-Stand). Andre bat darum, alle betroffenen und alle ausgefallenen Fälle mit einer Abschottung nachzuholen.

## Was geändert wurde

`scripts/second-opinion.sh` (Commit `d133c7e`): Jedes Modell läuft in einem eigenen leeren Temp-Ordner außerhalb des Repos, der nur die Anhänge enthält. Über `OPENCODE_CONFIG_CONTENT` sind Shell, Bearbeiten, Web, Unteragenten und jeder Zugriff außerhalb dieses Ordners gesperrt (`external_directory: deny`). Ein Probelauf bestätigte die Sperre: Das Modell kam weder an `docs/nachtlauf/antworten/` noch an `../`, hatte keine Shell und beantwortete die Frage trotzdem. Das Skript bricht ab, wenn `TMPDIR` im Repo liegt. Die Änderung wurde wie in CLAUDE.md vorgesehen von drei Modellen geprüft (Space Bunny, DeepSeek, MiMo); übernommen wurde die TMPDIR-Prüfung, der Rest ist im Commit-Text begründet.

## Ablauf

- Alle 7 verfügbaren Modelle (Space Bunny, DeepSeek, GLM, MiMo, Longcat, Big Pickle, Beam) für alle 4 Bereiche, dieselben Prompts wie in der Nacht, dieselben Dateien wie in der Nacht (Stand `main` vor den Fixes), Zeitlimit 700 s, keine Rotation. Damit sind sowohl die möglicherweise beeinflussten als auch die ausgefallenen Fälle abgedeckt.
- Rate-limitierte Fälle wurden einzeln nachgeholt.
- Antworten: `docs/nachtlauf/antworten-isoliert/<bereich>/`. Die Antworten der Nacht bleiben unverändert in `docs/nachtlauf/antworten/`.

**Aufrufe:** 35, davon 21 mit Antwort, 6 Rate-Limits, 5 leere Antworten (Longcat 3×, GLM, Big Pickle), 1 Timeout (MiMo), 2 Fehler. Die 2 Fehler betrafen Space Bunny ab 09:24 UTC: „OpenCode's free tier can only be used from within OpenCode“. Das ist eine Sperre auf Anbieterseite; Space Bunny für `scripts` ließ sich deshalb nicht nachholen.

| Bereich | Antworten | Fehlt |
|---|---|---|
| engines | SB, DS, GLM, MM, BP, BF | LC (leer) |
| provider | SB, DS, GLM, MM, BP, BF | LC (leer) |
| scripts | DS, GLM, MM, LC, BP, BF | SB (Free-Tier-Sperre) |
| spec | SB, DS, BF | GLM, LC, BP (leer), MM (Rate-Limit, dann Timeout) |

## Ergebnis

### 1. Ohne Shell finden die Modelle die bestätigten Fehler nicht mehr

| Befund | In der Nacht gefunden von | Isoliert gefunden von |
|---|---|---|
| E-01 (Request, der nicht gebaut werden kann → „malformed reply“) | Claude; SB (provider, „verifiziert“ per Shell am echten `engines.py`); DS (spec, „in .venv geprüft“); später BP, BF | **niemand** |
| S-01 (`recompute.py` druckt `None chars`) | SB (Skript ausgeführt), daneben GLM und BF nur als „unterschiedliche Basis der Mediane“ | **niemand**; GLM, LC und BF nennen wieder nur die unterschiedliche Basis |
| T-01, T-02 (Testlücken) | SB | niemand |
| V-02 (Live-Check zeigt Fehler als Cache-Treffer) | DS, SB, BF | niemand (BP nennt einen ähnlichen Fall mit erfundenem Logformat) |

Beide echten Fehler wurden in der Nacht von Modellen gefunden, die den Code **ausgeführt** haben. Das ist nicht dasselbe wie das Abschreiben fremder Antworten. Die Abschottung verhindert beides: Die Antworten sind jetzt unabhängig, aber flacher.

### 2. Was isoliert mehrfach und unabhängig kam

- **V-01 (Firecrawl 2xx mit `success: false`)** nennen jetzt vier Antworten unabhängig: SB und MM (engines), SB und DS (spec). SB und MM ergänzen einen Gesichtspunkt: Meldet Firecrawl so ein aufgebrauchtes Kontingent, greift die 24-h-Pause nicht, weil der Status 2xx ist. Ob Firecrawl so antwortet, ist weiter nicht belegt. Der Vorschlag bleibt bei Andre; die Skizze in `befunde.md` ist um diesen Punkt ergänzt.
- **V-04 (neu): Die Einstellungen `SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS` und `SEARCH_CHAIN_PARALLEL_API` stehen nicht im Manifest** (SB und GLM, provider). GLMs Vermutung, sie seien deshalb im Profil-Scope wirkungslos, trifft nicht zu: `build_profile_secret_scope` in Hermes v0.21.6 übernimmt die ganze `.env` des Profils. Hermes kennt aber den Manifest-Schlüssel `optional_env`, der die beiden Werte auffindbar machen würde. Das ist eine Manifest-Änderung und damit Andres Entscheidung.
- **V-05 (neu): Fehlt in einer 2xx-Antwort von Exa oder Parallel das Feld `results`, gilt das als „no results“, nicht als „malformed reply“** (SB spec, MM engines). A4 lässt sich so lesen, dass das `malformed` sein müsste. Der Code macht es absichtlich (`if items is None: items = []`), und Firecrawl ohne `data.web` ist ausdrücklich so getestet. Die Kette läuft in beiden Fällen weiter, nur der Grund im Fehlertext unterscheidet sich. Vorschlag: A4 präzisieren (fehlende Liste = keine Treffer) statt den Code zu ändern.
- Die übrigen Punkte wiederholen die abgelehnten Gruppen der Nacht (Limit-Grenzen, breite `except`, Client je Aufruf, Pausentabelle, Ergebniszeilen, Test-Stub). Diesmal sind sie unabhängig voneinander entstanden; sie zeigen also eher, was Modelle an diesem Code typischerweise anmerken, als dass sie neue Belege wären.

### 3. Neu abgelehnt

| Punkt | Modelle | Grund |
|---|---|---|
| Pausentabelle nicht threadsicher | BF, BP (provider) | K5 beschreibt das ausdrücklich: einfacher Dict ohne Lock, gleichzeitige Aufrufe setzen dieselbe Pause erneut. |
| Logzeilen mit „paused for“ verschluckten Stufen | BP (scripts) | Falsch: „paused for“ steht nur in der WARNING-Zeile (L2); die INFO-Zeile lautet `exa=paused`. Das Beispiel-Logformat ist erfunden. |
| `Retry-After` ignoriert, keine Obergrenze für die Anzahl der Zeilen, Highlight bis 999.999 | GLM (engines), MM (provider) | D15 und D16. Hermes kürzt die Liste ohnehin auf das Limit des Modells. |
| Zeilen über 88 Zeichen, Leerzeile nach `except` | SB, DS (spec) | Das Repo setzt `line-length = 120`; `ruff format --check` ist in CI grün. |
| `super().__init__()` fehlt, Hermes könnte mit Argumenten instanziieren | SB (spec) | Das Plugin instanziiert die Klasse in `register()` selbst ohne Argumente. |
| `HERMES_ROOT` als Angriffsweg, `uv.lock` fehle | BF (scripts) | Wer die Umgebung setzt, kontrolliert den Prozess ohnehin; `uv.lock` liegt im Repo (nur nicht im Anhang). |
| Import von `hermes_bootstrap` vor `.env` und `--break` | GLM (scripts) | Keys werden bei jedem Aufruf gelesen; der Live-Check mit `--break` hat genau so funktioniert (validation.md, T2). |
| `IndexError` beim Zerlegen der Logzeile, `keyless_rescue` per `is not False` | LC (scripts) | Gesammelt werden nur Zeilen, die mit `search-chain: ` beginnen; die strenge Prüfung auf `false` ist gewollt (T2). |
| „Nearest hour“ könnte Banker's Rounding meinen | BF (spec) | K5 und die Tests legen Aufrunden ab x,5 fest. |
| `RecursionError` bei `"[" * 200000` sei nicht garantiert | DS (engines) | Der Test läuft in CI auf 3.11 und 3.14 grün; CPythons JSON-Parser prüft die Rekursionstiefe. |
| Testnähte (`transport`, `clock`) im Konstruktor, Default-Argumente zur Importzeit, geteilte `httpx.Response`-Objekte in Tests | MM (provider, engines) | Stil ohne Fehlerbild. |

## Eindrücke je Modell (isoliert)

| Modell | Antworten | Fehlalarme | Tempo | Eindruck |
|---|---|---|---|---|
| space-bunny-free | 3 von 6 | 1 (Zeilenlänge, vorsichtig formuliert) | 110–260 s | Weiter das gründlichste Modell, ohne Shell aber ohne bestätigten Fehler. Unabhängig V-01, V-04 und V-05. Ab 09:24 UTC durch OpenCodes Free-Tier gesperrt. |
| deepseek-v4.1-flash-free | 4 von 5 | 0 | 70–351 s | Knapp und sachlich; ohne Ausführen findet es E-01 nicht mehr. V-01 unabhängig. |
| glm-5.3-flash-free | 3 von 4 | 1 (Einstellungen wirkungslos) | 185–461 s | Diesmal ohne Timeout in drei Bereichen. Fand V-04 mit einer falschen Begründung. |
| mimo-v2.6-flash-free | 3 von 7 | 0 | 270–545 s | Isoliert deutlich besser als in der Nacht (dort fast nur Timeouts): drei vollständige Antworten, V-01 und V-05 unabhängig. |
| longcat-2.5-preview-free | 1 von 4 | 1 (`IndexError`) | 140 s | Dreimal leere Antwort; die eine Antwort (scripts) ist ordentlich, aber ohne Treffer. |
| big-pickle | 3 von 5 | 1 (erfundenes Logformat) | 435–581 s | Ohne fremde Antworten deutlich schwächer als in der Nacht; langsam. |
| beam-free | 4 von 4 | 2 (Rundung, `uv.lock`) | 35–85 s | Schnell, aber oberflächlich. Ohne Vorlage keine eigenen Treffer; das bestätigt den Verdacht, dass die Treffer der Nacht abgeschrieben waren. |

## Folgerung für das Skript

Die Abschottung bleibt drin: Mehrfachnennungen sind jetzt echte unabhängige Stimmen. Damit die Modelle Code wieder ausführen können, ohne das Repo oder andere Antworten zu sehen, müsste die Shell in einer echten Sandbox laufen. Auf diesem Rechner gäbe es dafür `unshare` (eigener Mount-Namespace mit einer Kopie nur der Anhänge); `bwrap` und `firejail` fehlen. Das wäre ein größerer Umbau. Vorschlag an Andre: als eigenen Schritt entscheiden. Bis dahin sollte, wer eine Zweitmeinung zu Code einholt, die Prüfung „durch Ausführen“ selbst übernehmen. So war es auch in dieser Nacht: Beide echten Fehler hat Claude reproduziert.
