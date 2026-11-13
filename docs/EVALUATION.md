# Evaluationsprotokoll

Stand: 13. November 2026. Dieses Dokument definiert Messgrößen und Nachweise für die Meilensteine in [PLAN.md](PLAN.md). Grenzwerte werden vor einem Experiment festgelegt; rückblickend passende Grenzwerte gelten als neue Hypothese.

## 1. Was der aktuelle Stand belegt

Der [echte Abruf](validation/youtube-smoke.json) des [Cointelegraph-Interviews mit Krown](https://www.youtube.com/watch?v=EdXslFg3u38) lieferte 646 automatisch erzeugte englische Caption-Segmente. Die YouTube-Seite nennt Veröffentlichung und Upload am 2. September 2026 um 15:01:27 UTC. Der tatsächliche Abruf erfolgte am 13. November. Diese spätere Verfügbarkeit darf nicht auf September zurückdatiert werden. Die Baseline erzeugte 46 ungeprüfte, als Kommentar klassifizierte Aussagen und kein vollständiges unterstütztes Setup. Das belegt einen Import und konservative Ausgabe, keine gemessene Extraktionsgenauigkeit. Eine unabhängige Audioprüfung fehlt.

Jeffs echte lokale Gewichte wurden über das offizielle In-Process-SDK ausgeführt. Die [ersten zwei Fälle](validation/jeff-cpu-smoke.json) und [sechs weiteren vorab definierten Fälle](validation/jeff-cpu-concise-smoke.json) belegen Modellinferenz, aber keinen akzeptierten Einstieg. Die sechs zusätzlichen Fälle führten sämtlich zur Enthaltung; zwei höchste Klassenwahrscheinlichkeiten gehörten zum falschen Label. Die vollständige HTTP-Verbindung zu diesen Gewichten wurde nicht ausgeführt. Jeff bleibt experimentell und standardmäßig deaktiviert; Details in [JEFF_SETUP.md](JEFF_SETUP.md).

Synthetische Tests, HTTP-Vertragstests, echte Modellinferenz, echter Quellenimport und wirtschaftliche Validierung sind getrennte Nachweisarten. Es wurde kein eigener Decision Transformer trainiert und kein Krown-Handelsvorteil nachgewiesen.

## 2. Quellenverständnis messen

Referenzlabels entstehen vor Einsicht in spätere Kurse. Videos desselben Ereignisses und überlappende Ausschnitte gehören in dieselbe Datenpartition. Testvideos bleiben bei Prompt-, Grammatik- und Schemaänderungen geschlossen. Ein eingefrorener Datensatz enthält positive Aussagen, nicht ausführbare Prognosen und schwierige negative Beispiele.

Für jede Variante berichten:

- Präzision und Trefferquote der erkannten Aussagen, getrennt nach Aussageart und Instrument.
- Feldgenauigkeit für Zahlenwert **und Rolle**: Einstieg, Ziel, Stop, Horizont und Kerzenintervall. Fehlende Angaben dürfen fehlen.
- Belegtreue einschließlich Kontext: Negation, hypothetische Bedingung, Rückblick, Korrektur und Sprecherzuordnung.
- Anteil falscher ausführbarer Freigaben sowie Abdeckung: Wie viele tatsächlich ausführbare Referenzfälle werden erkannt? Zusätzlich Zahl und Gründe der Enthaltungen.

Ergebnisse pro Video aggregieren und Unsicherheitsintervalle ausweisen; viele Segmente desselben Videos sind keine unabhängigen Beobachtungen. Bekannte falsche Einstiege erhalten konkrete Regressionstests. Eine hohe Gesamtgenauigkeit durch häufige Kommentare ist kein ausreichendes Annahmekriterium.

## 3. Regelgenauigkeit und Kalibrierung messen

Das Ziel hier lautet `buy/sell/hold` gemäß einer ausdrücklich formulierten Regel. Es lautet nicht „Trade endet im Gewinn“. Den Zeitpunkt der Vorhersage und der Labelerfassung speichern. Das [vorhandene Auswertungsmodul](../signal_lab/evaluate.py) berechnet Genauigkeit, Abdeckung, ECE und den mehrklassigen Brier-Score.

Der Brier-Wert ist der Mittelwert der **Summe über alle drei Klassen** von `(p − y)²`, wobei das richtige Label den Wert eins erhält. Die Implementierung teilt nicht zusätzlich durch drei; der Wertebereich ist null bis zwei. Er bewertet die gesamte Wahrscheinlichkeitsverteilung und ist kein reines Kalibrierungsmaß.

ECE gruppiert die höchste Klassenwahrscheinlichkeit in gleich breite Intervalle und mittelt gewichtet den absoluten Abstand zwischen Konfidenz und beobachteter Trefferquote. Das entspricht dem üblichen Ansatz bei [Guo et al.](https://proceedings.mlr.press/v70/guo17a/guo17a.pdf). ECE hängt von Gruppierung und Stichprobe ab; zehn Intervalle sind kein Qualitätsstandard. Daher zusätzlich Zuverlässigkeitsdiagramm, Intervallbelegung, Klassenzahlen, Konfusionsmatrix und Ergebnisse verschiedener vorab gewählter Gruppierungen liefern.

Die aktuelle Genauigkeit umfasst auch enthaltende Zeilen. Ergänzend die Genauigkeit akzeptierter Entscheidungen gegen deren Abdeckung auswerten. Schwellen oder nachträgliche Kalibrierung ausschließlich auf Trainings-/Validierungsdaten bestimmen. Künstliche Fallback-Verteilungen separat halten. Weder niedriger ECE noch niedriger Brier-Wert belegen positive Handelserträge.

## 4. Zeittrennung und faire Vergleiche

Ein handelbares Signal darf frühestens nach Quellenverfügbarkeit, abgeschlossener Extraktion und Prüfung berücksichtigt werden. Seine Gültigkeit wird durch spätes Einlesen nicht verlängert. Bei historischen Nachberechnungen ohne damalige Erfassungsnachweise ausdrücklich eine rekonstruierte Studie ausweisen. Ein rückwirkend gesetztes Datum ist kein Nachweis damaliger Verfügbarkeit.

Walk-forward bedeutet: ausschließlich frühere Daten zur Auswahl verwenden, danach das nächste Zeitfenster mit unveränderter Variante auswerten. Trainingsbeispiele entfernen, deren Zielintervalle in die Validierungs- oder Testphase reichen. Einen vorab festgelegten Abstand entsprechend Zielhorizont und Veröffentlichungsverzögerungen einhalten. Datenaufbereitung und Schwellenwahl ebenfalls innerhalb der jeweiligen Trainingsphase halten. Moderne LLMs könnten spätere Ereignisse aus ihrem Training kennen; zeitlich gefilterte Prompts beseitigen dieses Risiko nicht. Prospektive Beobachtung bleibt deshalb eine eigene Evidenzstufe.

| Variante | Information für die Signalentscheidung | Prüfzweck |
|---|---|---|
| Quelle | Geprüfte Aussagen und ihre ausdrücklichen Auslöser | Eigenständiger Quellenbeitrag |
| Preis | Vorab festgelegte Regeln auf vergangenen Kursen | Vergleich ohne Finfluencer |
| Kombination | Quellen- und Preisregeln | Zusätzlicher Nutzen der Quelle |
| Jeweils mit Jeff | Dieselben Fakten, zusätzlicher Regelentscheid | Nutzen und Kosten des Modells |

Alle Varianten benötigen Kurse für Auslöser, Risikoprüfung und Fills. Die Quellenvariante erhält dabei keine zusätzlichen technischen Indikatoren. Handelsfreiheit, Gebühren, Risikobudget und Zeitfenster bleiben vergleichbar. Jede getestete Variante wird erfasst; die Auswahl des besten Backtests aus vielen Versuchen ist selbst eine Überanpassungsquelle ([Bailey et al.](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)).

## 5. Wirtschaftliche und betriebliche Ergebnisse

Nettorendite, maximalen Drawdown, marktbewertetes Eigenkapital, Exposition, Umschlag, Zahl unabhängiger Trades und Kosten ausweisen. Cash und Buy-and-hold im selben Zeitraum als Referenzen zeigen. Gebühren und Slippage variieren; Funding, Leihe und Liquidität müssen vor entsprechenden Derivatebehauptungen modelliert werden. Der aktuelle Simulator bildet diese zusätzlichen Markteffekte nicht vollständig ab.

Entscheidungen verwenden abgeschlossene Kerzen; frühester Einstieg ist die nächste zulässige Eröffnung. Mehrdeutige Reihenfolgen innerhalb einer Kerze bleiben konservativ behandelt. Zeitlich zusammenhängende Blöcke für Unsicherheitsschätzungen verwenden; dünne Daten und Regimeabhängigkeit offenlegen. Nach Öffnung des Tests bleiben Strategiewahl und Bewertungsregel gesperrt.

Der abschließende Bericht enthält außerdem Abrufausfälle, Prüfaufwand, Modellkosten und Laufzeitquantile. Jeder Befund nennt Datensatzversion, Code-Commit, Konfiguration, Ausschlüsse und Grenzen. Fehlende Evidenz ergibt ein offenes Ergebnis und keine Handelsfreigabe.
