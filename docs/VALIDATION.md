# Validierung des Drafts

Stand: 13. November 2026. Die nachfolgenden Prüfungen unterscheiden Softwareverhalten,
echte Quellen und echte Modellinferenz. **Keine Prüfung belegt eine profitable Strategie.**

## Ausgeführt

| Prüfung | Beobachtetes Ergebnis | Aussagegrenze |
|---|---|---|
| Verhaltenstests | **146 bestanden, 0 Fehler, 0 übersprungen** auf Python 3.12.14 | Konstruierte Fälle und lokale HTTP-Testserver; keine Genauigkeitsmessung auf einem repräsentativen Krown-Korpus. |
| Ruff | Bestanden | Statische Konsistenz, kein fachlicher Nachweis. |
| Mypy | Bestanden, 12 Quelldateien | Typprüfung, kein Gewinn- oder Sicherheitsbeweis. |
| Offline-Demo | 6 synthetische Aussagen, 1 freigegebenes Setup, 1 abgeschlossener Paper-Trade | Künstliche Preisfolge; Ergebnis ausschließlich als Mechaniktest ausgewiesen. |
| Paket-Build | Wheel gebaut, in separater Umgebung installiert, Demo außerhalb des Source-Verzeichnisses gestartet | Belegt die Auslieferung der notwendigen Beispieldaten. |
| Echter YouTube-Abruf | 646 automatisch erzeugte englische Segmente für `EdXslFg3u38` | Audio nicht unabhängig geprüft; kein manuell gelabelter Extraktionsbenchmark. |
| Quelle auf Baseline angewendet | 46 Asset-Erwähnungen als Kommentare; 0 vollständige unterstützte Setups | Segmentweise Verarbeitung verliert Kontext über Cue-Grenzen; diese Zahl misst keine Recall-Qualität. |
| Jeff mit echten Gewichten | Acht echte CPU-Aufrufe über die offizielle In-Process-Schnittstelle | Zwei Darstellungen und sehr wenige konstruierte Fälle; keine Accuracy-Schätzung. |
| Jeff-HTTP-Vertrag | 12 Tests gegen einen echten lokalen HTTP-Testserver | Der Testserver liefert kontrollierte Antworten, keine Modellinferenz. |
| Unabhängige Code-Reviews | Drei Standards-Befunde und drei Spec-Befunde bearbeitet | Gezielte Nachprüfung; siehe [REVIEW.md](REVIEW.md). |

Die rohe lokale Testzusammenfassung steht in [offline-tests.json](validation/offline-tests.json).
Die GitHub-Workflow-Datei prüft zusätzlich Python 3.11 und 3.13; deren tatsächlicher Laufstatus
ist im jeweiligen PR unter Checks einsehbar. Ein vorhandener Workflow ist allein noch kein
bestandener CI-Lauf.

## Besonders relevante Regressionen

- Negierte, historische und als Beispiel oder fremde Aussage markierte Setups führen nicht
  zu einer Freigabe. Nicht abgebildete Bedingungen bleiben gesperrt.
- Stop, Ziel und Auslöser müssen ihrer jeweiligen Rolle in der Quelle entsprechen. Eine
  vorhandene Zahl an anderer Stelle reicht nicht. Spannen und Korrekturen werden nicht
  still auf einen Wert reduziert.
- Die begrenzte Ausführungsgrammatik wird auch beim Review erneut geprüft. Ein Modell
  kann eine Sperre nicht allein durch Löschen seines `issues`-Feldes umgehen.
- Publikation, Quellenverfügbarkeit, Extraktion, Review und früheste Entscheidungsverfügbarkeit
  bleiben getrennt. Ein später Import oder Review verlängert die ursprüngliche Gültigkeit nicht.
- Untertitel-Kommentare sind keine Sprache; malformed Zeitstempel lösen einen Fehler aus,
  statt eventuell wichtige Negationen aus der Quelle zu entfernen.
- Das Modell erhält nur das aktuelle abgeschlossene Candle und das bereits verfügbare Signal.
  Der Einstieg erfolgt zur nächsten zusammenhängenden Eröffnung. Gebühren und adverse
  Slippage betreffen beide Seiten.
- Drawdown-Schließungen erfolgen erst zur nächsten beobachteten Eröffnung. Der konkrete
  Regressionstest umfasst Einstieg 100, Alarm bei Schlusskurs 90 und nächste Eröffnung 70:
  Die Simulation realisiert −3.000 bei 100 Einheiten statt optimistisch −1.000. Endet der
  Datensatz am Alarm, bleibt die Position offen und markiert.
- Jeff-Ausfälle und Enthaltungen bleiben von fehlerhaften Antworten unterscheidbar. Eine
  von der Anwendung erzeugte Hold-Verteilung ist ausdrücklich keine Modellwahrscheinlichkeit.
- Manipulierte HTML-Statistikwerte werden verworfen; Quellentexte werden escaped.

## Echte Quelle

[youtube-smoke.json](validation/youtube-smoke.json) protokolliert Abrufzeit, Sprache, Hash
des lokal gespeicherten Caption-Payloads und Resultate. Originalvideo:
[Cointelegraph-Interview mit Eric Crown](https://www.youtube.com/watch?v=EdXslFg3u38).
Das YouTube-Microformat nennt sowohl als `publishDate` als auch `uploadDate`
`2026-09-02T08:01:27-07:00`, entsprechend **2. September 2026, 15:01:27 UTC**.
Die Podcastseiten nennen teils abweichende Kalendertage; die Videoangabe wurde direkt geprüft.

Der Abruf erfolgte am 13. November. Das System behauptet deshalb keine damalige Beobachtung
im September. Die vollständigen fremden Untertitel liegen nur im ignorierten lokalen
Datenverzeichnis und werden nicht mit dem Repository verteilt. Ein kurzer, attribuierter
Originalsatz dient in den Tests lediglich als Negativbeispiel für eine uneindeutige Prognose.

## Echte Jeff-Inferenz

Getestet wurden die offiziellen v1.4-Gewichte mit Python 3.13.5 und PyTorch 2.14.0+cpu.
Details einschließlich aller Wahrscheinlichkeiten und Requests:

- [Ursprüngliche zwei Fälle](validation/jeff-cpu-smoke.json)
- [Einmalige kompakte Darstellung mit sechs vorab festgelegten Fällen](validation/jeff-cpu-concise-smoke.json)
- [Setup und Reproduktion](JEFF_SETUP.md)

In der ursprünglichen Darstellung enthielt sich Jeff beim erfüllten Long-Trigger und wählte
beim nicht erfüllten Trigger korrekt Hold. In der kompakten Darstellung enthielt es sich in
allen sechs Fällen. Zwei zuerst gewählte Labels waren falsch: ein erfüllter Short-Trigger
und ein Fall mit fehlendem Stop. Kein Einstiegsfall erhielt eine akzeptierte Freigabe.
Die kompakte Darstellung wurde nicht übernommen und es wurden keine Schwellen gesenkt.
Die beobachtete Laufzeit lag bei etwa 2,4–3,2 Sekunden pro CPU-Aufruf. Das ist kein belastbarer
Latenzbenchmark. Vier Threads wurden angefordert; nach dem Laden meldete die Runtime acht.

**Getrennte Integrationsgrenze:** Der offizielle HTTP-Dienst konnte hier nach dem Laden
der Gewichte keinen Unix-Socket erstellen (`AF_UNIX`, `PermissionError: Operation not permitted`).
Echte In-Process-Inferenz und HTTP-Vertrag sind separat belegt. Ein kompletter Lauf über
den offiziellen HTTP-Server bis zu echten Gewichten ist hier nicht nachgewiesen.

## Offen oder nur vorbereitet

- **Generative LLM-Extraktion:** transport- und schema-getestet, aber kein echter externer
  generativer Modellaufruf. Es war kein solcher Dienst für diesen Test konfiguriert.
- **ASR/Video:** optionaler CPU-Adapter implementiert; kein echter Whisper-Lauf und keine
  Chart-/OCR-Extraktion geprüft.
- **Berichtsansicht:** HTML-Erzeugung, Escaping und Berichtsdaten geprüft. Ein visueller
  Desktop-/Mobile-Render konnte hier nicht abgeschlossen werden: Der lokale Chromium-Start
  scheiterte an einer Socket-Beschränkung; der getrennte Cloud-Browser erreichte den lokalen
  HTTP-Server nicht. Responsive CSS ist vorhanden, aber nicht als gerendert geprüft ausgewiesen.
- **Marktevaluation:** kein historischer Krown-Backtest mit belastbarem Goldstandard, keine
  prospektive Performancebeobachtung, keine Schätzung eines Handelsvorteils.
- **Ausführung:** keine Brokerverbindung, keine Funding-/Leihkosten, kein Orderbuch-,
  Liquiditäts- oder Margin-Liquidationsmodell. Shorts sind ausschließlich optionale Simulation.

Nächste Prüfschritte und Abnahmekriterien stehen in [PLAN.md](PLAN.md) und
[EVALUATION.md](EVALUATION.md).
