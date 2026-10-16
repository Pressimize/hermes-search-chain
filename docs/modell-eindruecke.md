# Eindrücke der Review-Modelle

Eine Zeile je Modell und Review. Spalten: Modell-ID (exakt, ohne `opencode/`), Datum, PR/Branch, Dauer, Punkte gesamt / übernommen / Fehlalarme, Kurzurteil.

| Modell | Datum | PR | Dauer | Punkte ges./übern./Fehlalarm | Kurzurteil |
|---|---|---|---|---|---|
| muse-spark-1.3-contributor-free | 2026-10-16 | chore/second-opinion | 30s | 5/0/2 | Knapp, mit Zeilen. Fehlalarme: `big-pickle` sei falsche ID (ist korrekt), `kill` lasse opencode verwaist (timeout leitet SIGTERM weiter). Rest berechtigt, aber bewusst so gewollt (npm-Install, exclude-Eintrag, Basename-Kollision). |
| space-bunny-free | 2026-10-16 | chore/second-opinion | 20s | 5/0/1 | Gründlichste Antwort. Treffer: kein `--` vor dem Prompt, alte `.opinion/*.md` bleiben liegen, Rotation schweigt bei leerem Pool. Fehlalarm: verwaister opencode-Prozess. |
| cat-jam-free | 2026-10-16 | chore/second-opinion | 10s | 5/0/1 | Schnell, ohne Zeilennummern, überschneidet sich mit den anderen (Basename, `-`-Prompt). Regex-Hinweis zu `count_rows` praktisch folgenlos. |
