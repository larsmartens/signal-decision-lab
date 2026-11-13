# Entwicklungsplan

Stand: 13. November 2026 · [Repository](https://github.com/larsmartens/signal-decision-lab) · Maßgebliche Grenzen: [SPEC.md](SPEC.md)

## Ausgangspunkt und Architektur

Das Repository ist ein Forschungsprototyp für BTCUSDT. Die vorhandene Verarbeitung lautet: zeitgestempelte Quelle → belegte Aussage → geprüfte, ausführbare Bedingung → deterministische Regelentscheidung → numerische Risikoprüfung → chronologischer Paper-Replay. Ein optionaler LLM-Extraktor schlägt Aussagen vor; Jeff v1.4 kann Regelentscheidungen als experimentelle Vergleichsinstanz beurteilen. Beide dürfen weder eine fehlende Quellenangabe ergänzen noch die Risikoprüfung ersetzen. Belege und Umsetzung: [Extraktion](../signal_lab/extract.py), [LLM](../signal_lab/llm.py), [Jeff](../signal_lab/jeff.py), [Engine](../signal_lab/engine.py), [Replay](../signal_lab/replay.py).

Ausführbare Setups benötigen derzeit eine begrenzte englische Grammatik. `unsupported_language` bleibt auch bei LLM-Ausgaben eine Sperre. Nicht unterstützte Korrekturen, Preisbereiche und zusätzliche Bedingungen bleiben blockiert. Der Import übernimmt die mitgelieferte Veröffentlichungszeit; deren externe Prüfung gehört zur Datenerfassung. Es gibt weder ein eigens trainiertes Modell noch einen validierten Krown-Handelsvorteil.

Die folgenden sechs Meilensteine sind Arbeitsaufträge, keine laufenden Jobs. Vor jeder Stufe werden Umfang, Budget und Annahmekriterien im Experimentprotokoll festgehalten. Ergebnisse und Fehlversuche bleiben versioniert. Messdefinitionen stehen ausschließlich in [EVALUATION.md](EVALUATION.md).

## 1. Echten Krown-Korpus und Referenzlabels aufbauen

**Lieferung:** Zunächst eine überschaubare, vorab ausgewählte Stichprobe, beispielsweise 30 Videos mit unterschiedlichen Marktphasen und Aussagearten. Diese Größe ist eine Arbeitsplanung. Sie belegt keine statistische Aussagekraft. [Krowns offizieller Kanal](https://www.youtube.com/channel/UCnwxzpFzZNtLH8NgTeAROFA) und Gastauftritte werden getrennt erfasst; Videos erhalten stabile IDs statt einer Zuordnung allein über Titel.

Je Quelle speichern: URL, Herausgeber, Veröffentlichungszeit samt Beleg und Genauigkeit, tatsächliche Abrufzeit, Sprache, manuelle oder automatische Captions, Segmentzeiten, Inhaltshash, Abrufwerkzeug und Version. Veröffentlichungen mit ungeklärtem Zeitpunkt bleiben für historische Handelsbehauptungen gesperrt. Die [Transcript-Bibliothek](https://github.com/jdepoix/youtube-transcript-api) liefert segmentierte Texte und unterscheidet erzeugte Untertitel; ihr Abruf kann an Zugriffsproblemen scheitern. Ausfälle gehören ins Protokoll.

**Abnahme:** Zwei Personen annotieren unabhängig eine vorab festgelegte Teilmenge; Uneinigkeiten werden begründet aufgelöst. Labels enthalten Kommentar, Bedingung, Anweisung, Negation, Rückblick, Unklarheit und jeweils die Quellenstellen. Annotierende sehen keine späteren Kurse. Volltexte werden nur bei entsprechender Berechtigung verteilt.

**Aufwand:** Manuelle Annotation zuerst; ein kleiner geprüfter Bestand ist günstiger zu korrigieren als ein großer ungeprüfter Datenbestand. Das bereits importierte Interview ist ein technischer Ausgangspunkt, kein fertiger Referenzdatensatz; siehe [Abrufnachweis](validation/youtube-smoke.json).

## 2. Aussagen zuverlässig und vollständig abbilden

**Lieferung:** Ein eigenes Aussagenformat erhält Sprecher, Instrument, Zeitbezug, Bedingung, Richtung, Negation, Unsicherheit, Quellenspannen und unbekannte Werte. Ein separates Format beschreibt ausführbare Setups. Eine korrekte Langfristprognose darf deshalb als Aussage erhalten bleiben, obwohl Stop, Einstieg oder Frist fehlen. Neue Sprachmuster benötigen überprüfbare Regeln und Regressionstests, bevor sie die Ausführungssperre verlassen.

**Abnahme:** Auf zurückgehaltenen Videos Feldtreue, Quellenzuordnung und falsche Handelsfreigaben messen. Kontext über Caption-Grenzen berücksichtigen; Zahlenrollen, Selbstkorrekturen, Alternativszenarien und zurückgenommene Aussagen gesondert auswerten. Jeder bekannte Fall, der unbegründet einen Einstieg erzeugt, blockiert die nächste Stufe. [VideoConviction](https://arxiv.org/html/2507.08104v1) zeigt gerade bei der Unterscheidung von Kommentaren und Empfehlungen Schwierigkeiten; der Aktienbenchmark ersetzt keinen Krypto-Test.

**Aufwand:** Text zuerst messen. Erst dokumentierte Fehler durch fehlende Chartinformationen rechtfertigen gezielte Einzelbilder an relevanten Zeitpunkten und OCR. Bildzeit, Instrument, Achsenskalierung und Unsicherheit bleiben belegt; widersprüchliche Angaben gehen zur Prüfung. Den zusätzlichen Nutzen gegen Frame-, Modell- und Prüfkosten messen. Vision ist derzeit ein Ausbauvorschlag.

## 3. Regelbasis, LLM und Jeff kontrolliert vergleichen

**Lieferung:** Identische geprüfte Eingaben durch die deterministische Basis und den optionalen Jeff-v1.4-Entscheider schicken. Den LLM ausschließlich auf belegte Aussagevorschläge prüfen. Versionen, Prompt, Schema, Eingabehash, Laufzeit, Ablehnungsgrund und Rohentscheidung protokollieren. Eigene Referenzlabels beantworten die Frage, welche Regelaktion aus den verfügbaren Fakten folgt.

**Abnahme:** Modellfehler, ungültige Wahrscheinlichkeiten, Enthaltung oder fehlende Kalibrierung erlauben keinen Einstieg. Jeff erhält erst nach einer Auswertung auf eigenen getrennten Daten eine produktive Rolle im Paper-System. Die [Model-Card](https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/release/hf/jeff-adapter-trading-desk/README.md) evaluiert eine andere Aufgabenverteilung; ihr Genauigkeitswert ist keine Gewinnwahrscheinlichkeit. Die lokalen Modellproben begründen aktuell keine Aktivierung; [Nachweis und Einrichtung](JEFF_SETUP.md).

**Aufwand:** Zuerst kleine, eingefrorene Vergleichssätze mit Kosten und Latenz auswerten. Schwellen nachträglich abzusenken, um mehr Einstiege zu erhalten, wäre eine neue Strategievariante und benötigt neue Testdaten.

## 4. Zusätzlichen Marktwert im chronologischen Replay prüfen

**Lieferung:** Drei vorab definierte Varianten: ausschließlich Quellenaussagen, ausschließlich Preisregeln, Kombination. Gleiche Instrumente, Zeitfenster, Ausführungsannahmen und Risikolimits verwenden. Jeff separat als zusätzlichen Faktor untersuchen. Gebühren, Slippage, nicht ausgeführte Signale und offene Positionen vollständig bilanzieren.

**Abnahme:** Chronologische Trainings-, Validierungs- und Testfenster verwenden. Überlappende Zielintervalle entfernen und einen zum längsten Zielhorizont passenden Zeitabstand an den Grenzen festlegen. Alle Parameter, Modellversionen und Auswahlregeln vor Öffnung des nächsten Testfensters sperren und mit Hash dokumentieren. Variantenregister einschließlich verworfener Versuche liefern. Wiederholte Strategiewahl auf denselben Testdaten erhöht das Risiko zufälliger Gewinner; siehe [Bailey et al.](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).

**Aufwand:** Erst die wenigen definierten Vergleiche durchführen. Weitere Indikatoren oder Modelle benötigen eine begründete neue Hypothese. Historische LLM-Ergebnisse bleiben wegen möglicher Kenntnis späterer Ereignisse eingeschränkt interpretierbar.

## 5. Prospektiven Schattenbetrieb durchführen

**Lieferung:** Nach bewusster Einrichtung neue Quellen tatsächlich zum Abrufzeitpunkt verarbeiten und Entscheidungen ohne Geldbewegung fortlaufend protokollieren. Vier bis acht Wochen sind eine Planungsheuristik für Betriebsbeobachtung, kein Beweiszeitraum für Profitabilität. Die erforderliche Dauer richtet sich zusätzlich nach unabhängigen Ereignissen, Marktphasen und Unsicherheit.

**Abnahme:** Veröffentlichung, Abruf, Extraktion, Prüfung und Entscheidung bleiben getrennte Zeitpunkte. Protokolländerungen erzeugen neue Versionen. Ausfälle, verworfene Aussagen, manuelle Eingriffe, Modellkosten und Laufzeitquantile ausweisen. Geänderte Strategien starten einen neuen Auswertungsabschnitt; bereits beobachtete Ergebnisse werden nicht als unberührter Test wiederverwendet.

**Aufwand:** Begrenzte Quellenliste und tägliche manuelle Sichtung statt sofortiger Betriebsplattform. Niedrige Signalzahl wird als Ergebnis dokumentiert. Sie rechtfertigt keine nachträgliche Lockerung der Quellenanforderungen.

## 6. Optional ein Ausführungsframework anschließen

**Lieferung:** Erst nach den vorherigen Nachweisen einen austauschbaren Adapter zu einem ausgewählten Framework entwerfen. Zunächst dessen simulierten Betrieb verwenden; Ordergrößen, Verlustgrenzen und Freigaben bleiben im deterministischen Kern. Frameworkwahl erfolgt anhand der dann benötigten Börse, Instrumente und Betriebsfunktionen.

**Abnahme:** Wiederholte Requests dürfen keine doppelten Orders erzeugen. Teilfüllungen, Verbindungsabbrüche, Neustarts und Abweichungen zwischen lokalem und externem Bestand müssen reproduzierbar behandelt werden. Eine vollständige Entscheidungskette muss zu Quelle, Regelversion und Risikoprüfung zurückführen. Die optionale Integration allein autorisiert keinen Echtgeldbetrieb.

**Aufwand:** Keine Ausführungsplattform vorziehen, solange Quellenqualität oder zusätzlicher Marktwert ungeklärt sind. Scheitert eine Stufe, bleibt das Ergebnis ein nützliches Recherche- und Prüfsystem; die nächste Komponente wird dadurch nicht automatisch notwendig.
