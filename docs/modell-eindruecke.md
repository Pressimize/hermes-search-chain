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
