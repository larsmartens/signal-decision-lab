# Decision Models für transcriptbasiertes Trading

Recherche- und Quellenstand: **13. November 2026**. Primärquellen: Projektcode, versionierte Model Cards und Originalarbeiten. Dieser Bericht prüft verfügbare Ansätze und Schnittstellen. Die anschließend ausgeführten Tests mit echten Jeff-v1.4-Gewichten sind in [JEFF_SETUP.md](../JEFF_SETUP.md) dokumentiert: lokale CPU-Inferenz gelang; beim ursprünglichen Zweifall-Test enthielt sich das Modell einmal, bei einem einmaligen Vergleich mit kompakter Darstellung in allen sechs Fällen. Zwei der sechs zuerst gewählten Labels waren falsch. Die veröffentlichte Modellgüte wurde nicht unabhängig repliziert.

## Empfehlung für diesen Prototyp

**Jeff v1.4 als optionalen, austauschbaren Vergleichsentscheider für ausdrücklich formulierte Handelsregeln anbinden.** Die aus Transkripten gewonnenen Aussagen sollten zunächst in belegte, zeitlich verfügbare Signale überführt werden. Ein deterministisches Regelwerk bleibt die Vergleichsbasis. Jeff kann prüfen, welche der vorgegebenen Aktionen zu Regeln und Zustand passt; die aktuelle Trading Model Card grenzt Preisprognose und Strategieentwicklung ausdrücklich aus. Deshalb darf die Oberfläche eine Jeff-Konfidenz nicht als Gewinnwahrscheinlichkeit darstellen. [J1] Die unten recherchierte technische Eignung wurde anschließend durch die genannten kleinen Funktionstests eingegrenzt: Für diese einfachen Regeln bleibt deterministischer Code die empfohlene Grundlage.

Decision Transformer und klassisches Offline-RL sind mögliche spätere Experimente. Dafür werden zeitlich geordnete Markt-, Positions-, Aktions- und Ergebnisverläufe benötigt. Eine Sammlung von Transkripten allein liefert diese Trainingsdaten nicht. Dies ist eine Architekturfolgerung aus dem Trainingsproblem des ursprünglichen Decision Transformer. [D1]

## 1. „Jeff“ ist identifiziert

Gemeint sein kann tatsächlich das Projekt **firelex/jeff**, nicht eine fehlerhaft transkribierte JEPA-Bezeichnung. Jeff verwendet ein auf Qwen3.5-0.8B basierendes Modell mit taskbezogenen LoRA-Adaptern. Es bewertet eine begrenzte Auswahl von Antworten in einem Forward-Pass. Die v1.4-Base ist für die Verwendung mit Adaptern vorgesehen, unterstützt laut eigener Model Card englischen Text und ist kein Modell für mehrstufiges Schlussfolgern. [J2]

### Verifizierter aktueller Stand

| Komponente | Verifizierter Stand | Quelle |
|---|---|---|
| Öffentliches Repository | `firelex/jeff` | [J3] |
| Für diese Recherche festgehaltener Commit | `59898ae9e12621bd8e0199b86c951d366f5026b7`, 6. November 2026 | [J3] |
| Python-SDK und Runtime | Version 1.4.1; Python mindestens 3.13 | [J4], [J5] |
| Modellbasis | `mstrasser/jeff-base`, Revision `v1.4`, veröffentlicht am 5. November 2026 | [J2], [J6] |
| Trading-Adapter | `mstrasser/jeff-adapter-trading-desk`, Revision `v1.4`; Adapterversion 1.4.0 | [J1], [J7] |
| Base-Identität | SHA-256 `22fd9a1ee317894fe8a987e362a313f36e4246129602a19ce54f617fa90e2f9b` | [J6] |
| Code-Lizenz | MIT | [J3] |
| Base- und Trading-Adapter-Gewichte | Apache-2.0 laut Model Cards | [J1], [J2] |

**Versionsfalle:** Suchmaschinen liefern noch v1.3-Seiten, die `jeff-serve`, andere Installationsbefehle und 98,1 % Trading-Genauigkeit nennen. Die aktuelle versionierte Quelldatei erklärt v1.3 für zurückgezogen; nur v1.4 und zugehörige Adapter werden veröffentlicht. Für Neuinstallationen deshalb weder v1.3-Anweisungen noch deren Kennzahlen verwenden. [J6]

### Was die aktuelle Trading-Evidenz belegt

Der v1.4-Adapter wurde laut Model Card am **25. Oktober 2026** trainiert. Der Anbieter meldet **97,7 % Accuracy auf 5.000 intern generierten Testfällen mit simulierten Orderbüchern**. Die Messung bewertet, ob die richtige diskrete Regelentscheidung gewählt wurde. Sie ist weder eine Renditemessung noch ein Live-Handelsnachweis. Die Model Card unterscheidet dieses Generator-Testset ausdrücklich von unabhängigen öffentlichen Benchmarks und echten gehaltenen Dokumenten. Die Ergebnisse wurden in dieser Recherche nicht repliziert. [J1]

Die aktuellen kalibrierten Funktionsschwellen stehen separat im Manifest:

| Funktion | Ergebniswerte | Konfidenzschwelle | Präzision oberhalb der Schwelle | Abdeckung | Kalibrierungsfälle |
|---|---|---:|---:|---:|---:|
| `direction` | `buy`, `sell`, `hold` | 0,980730 | 100,0 % | 100,0 % | 200 |
| `risk_off` | `yes`, `no` | 0,999642 | 100,0 % | 100,0 % | 200 |
| `size` | `increase`, `decrease`, `keep` | 0,968660 | 99,2 % | 63,0 % | 200 |
| `order` | `cancel`, `amend`, `leave` | 0,999338 | 100,0 % | 100,0 % | 200 |
| `route` | drei vom Aufrufer beschriebene Venues | 0,808822 | 99,4 % | 90,5 % | 200 |

Quelle: aktuelles Manifest, Zielpräzision jeweils 0,99. [J7]

Diese Zahlen beschreiben das Kalibrierungsset. **Eigene Schlussfolgerung:** Bei anderen Instrumenten, deutschen Transkripten, anderen Regeln und Nachrichtentypen muss die Anwendung Konfidenz und Enthaltung erneut messen. Eine kalibrierte Auswahlwahrscheinlichkeit ist keine ökonomische Wahrscheinlichkeit für Profit.

### Lizenz- und Reproduzierbarkeitsgrenze

Die Base Model Card beschreibt eine Mischung aus öffentlichen, synthetischen und adapterspezifischen Trainingsdaten, einschließlich Daten mit Beschränkung auf nichtkommerzielle, akademische oder Forschungsnutzung. Die vollständigen Trainingsdaten werden nicht veröffentlicht. Die Gewichte selbst werden als Apache-2.0 ausgewiesen. Das erlaubt keine pauschale Aussage, sämtliche vorgelagerten Daten seien uneingeschränkt kommerziell lizenziert; vor einer Produktverwertung sollte die Datenherkunft gesondert geklärt werden. Für die Reproduktion nennt die Trading-Model-Card veröffentlichte `test.jsonl` und `calibration.jsonl`. [J2], [J1]

## 2. Konkrete Integrationsschnittstelle

### Aktuelle API: POST /v1/decide

Das versionierte Schema akzeptiert eine Liste von Funktionsaufrufen. Für den Trading-Adapter sind `desk` und `market_context` Pflichtkontext; das wechselnde Live-Feld heißt `market_state`. Der Aufruf übergibt den Inhalt dieses Felds als `input`. [J7], [J8]

Ein bewusst vereinfachtes, selbst formuliertes Beispiel:

```json
{
  "calls": [
    {
      "function": "jeff.finance.trading-desk.direction",
      "context": {
        "desk": "Buy one unit if the verified signal is positive and exposure is below one unit. Otherwise hold. Never short.",
        "market_context": "Research simulation. One instrument. Current signal is derived only from sources already available."
      },
      "input": "Verified signal: positive. Current position: zero units. Request: choose the next action."
    }
  ],
  "on_low_confidence": "return"
}
```

Dieses Beispiel demonstriert das Request-Schema, **nicht eine bereits validierte Strategie oder gemessene Jeff-Antwort**. Ein echtes Experiment sollte Markt- und Positionsfelder vollständig und in reproduzierbarer Form übergeben.

Die Antwort enthält `decisions` in Aufrufreihenfolge. Zu jeder Entscheidung gehören unter anderem `value`, `confidence`, `abstained`, `calibrated`, `probabilities`, `function`, `version`, `timing` und `evidence_refs`. Diese Felder gehören ins Auditprotokoll. Bei `abstained=true` wird keine neue risikosteigernde Position eröffnet. Das ist eine empfohlene Anwendungsregel, kein aus der Konfidenz abgeleitetes Profitversprechen. [J9], [J10]

### Noch unterstützte ältere API

Das aktuelle Repository führt zusätzlich `POST /v1/systemone`. Dort ist die Form `{model, state, questions}`; eine Choice-Frage enthält `type: "choice"`, `criteria` und optional `instructions`. Antworten liegen unter `answers.<question>` mit `choice`, `probabilities` und `confidence`. Das ist eine dokumentierte Kompatibilitätsschnittstelle, kein Beleg dafür, dass alte v1.3-Gewichte noch verfügbar sind. [J11], [J12]

Für den neuen Prototyp ist `/v1/decide` sinnvoll, weil Adapterversion und Enthaltung Teil des standardisierten Ergebnisses sind. Ein kleiner HTTP-Adapter entkoppelt die Trading-Anwendung vom Python- und GPU-Stack des Modells.

### Installation und Betriebskosten

Die Runtime unterstützt PyTorch auf CPU, MLX auf Apple Silicon und einen NVIDIA-Pfad. Das Repository nennt ungefähr 1,7 GB für den ersten Download der Base; die Downloadgröße ist nicht gleich dem gesamten RAM-/VRAM-Bedarf. Modell, Frameworks und Cache benötigen zusätzlichen Platz. Hier wurden keine Laufzeit- oder Speicherwerte auf eigener Hardware gemessen. [J3], [J13]

Der aktuelle Runtime-Paketstand pinnt unter anderem PyTorch 2.14.0, Transformers 5.17.0 und PEFT 0.21.1. Das macht eine isolierte Runtime-Umgebung zweckmäßig. Die Model Card weist auf Installation aus GitHub hin, solange die Pakete nicht auf PyPI stehen; die README enthält dazu noch widersprüchliche Installationsformulierungen. Ein reproduzierbares Setup sollte den oben genannten Commit festhalten. [J5], [J1]

Die folgenden Startbefehle entsprechen den ausgelesenen CLI-Optionen und sind **hier noch nicht ausgeführt**:

```bash
jeff runtime serve \
  --socket /tmp/jeff-trading.sock \
  --adapter trading-desk \
  --backend torch \
  --batch-window-ms 1 \
  --max-batch-rows 1 \
  --queue-limit-rows 64 \
  --prepare-workers 1
```

In einem zweiten Prozess:

```bash
JEFF_ENGINE_SOCKETS=/tmp/jeff-trading.sock \
JEFF_MODEL_NAME=jeff-v1.4 \
jeff-server serve --host 127.0.0.1 --port 8765 --workers 1
```

Die vier Scheduler-Optionen und die drei HTTP-Startoptionen sind im aktuellen Stand erforderlich. Der explizite Backendwert `torch` ist gültig; GPU-spezifische Flags gehören nicht in dieses CPU-Beispiel. [J14], [J15]

Lokale Software und offene Gewichte erfordern keinen hier festgestellten Kauf. Reale Kosten entstehen durch Hardware, Strom, Datenversorgung und gegebenenfalls Cloud-Inferenz. Aus Hersteller-Benchmarks auf H100 oder RTX-Hardware lässt sich keine CPU-Latenz für diesen Prototyp ableiten.

## 3. Weitere Decision-Model-Ansätze

| Ansatz | Primärquelle und Implementierung | Was tatsächlich gelernt wird | Einordnung für den Prototyp |
|---|---|---|---|
| Jeff + Trading-Adapter | [firelex/jeff](https://github.com/firelex/jeff), aktuelle Model Card [J1] | Auswahl zwischen benannten Optionen anhand beschriebener Regeln und Zustand | Unmittelbar als austauschbarer Regelentscheider integrierbar |
| Decision Transformer | NeurIPS 2021; [kzl/decision-transformer](https://github.com/kzl/decision-transformer) [D1], [D2] | Aktionen aus Return-to-go, Zuständen und vergangenen Aktionen | Erst nach Aufbau eines zeitlich korrekten Trajektoriendatensatzes |
| GPT-2 + LoRA als Trading-DT | Yun, 26. November 2024; [syyunn/finrl-dt](https://github.com/syyunn/finrl-dt) [D3], [D4] | Handelsverhalten aus Trajektorien bereits trainierter Experten | Forschungsreferenz, kein fertiges transcriptbasiertes Handelssystem |
| Conservative Q-Learning | NeurIPS 2020; [aviralkumar2907/CQL](https://github.com/aviralkumar2907/CQL) [D5], [D6] | Konservative Wertschätzung bei Offline-RL | Späterer Vergleich gegen Behavior Cloning und DT |
| CORL | [corl-team/CORL](https://github.com/corl-team/CORL) [D7] | Referenzimplementierungen mehrerer Offline-RL-Verfahren | Für kontrollierte Algorithmenexperimente; bewusst keine importierbare modulare Trading-Bibliothek |
| Decision Foundation Models | Liu et al., Version vom 5. Januar 2024 [D8] | Vortraining und nachgelagerte Anpassung als allgemeines Forschungsprogramm | Kein Nachweis einer universellen profitablen Trading-Policy |

### Was die Trading-DT-Arbeit belegt

Die Arbeit von Yun initialisiert einen Decision Transformer mit GPT-2 und trainiert LoRA sowie Embeddings auf Expertenverläufen. Die Experimente verwenden 29 DJIA-Aktien; Training läuft von 2009 bis Juli 2020, der Test bis Oktober 2021. Verglichen werden unter anderem CQL, IQL, Behavior Cloning und zufällig initialisierte DT-Varianten. Die Arbeit wurde als Poster eines ICAIF-2024-Workshops angenommen. Diese begrenzte Studie stützt weitere Experimente, keine Zusage über neue Märkte, Transkript-Alpha oder heutige Handelskosten. Das Repository ist Replikationscode, nicht ein bereitgestellter Produktionsdienst. [D3], [D4]

### Wesentliche methodische Grenze

Die Originalarbeit „You Can't Count on Luck“ zeigt, warum bloße Konditionierung auf hohe historische Returns in stochastischen Umgebungen scheitern kann: Gute realisierte Ergebnisse können Zufall statt reproduzierbare Handlungsqualität widerspiegeln. Die Autoren untersuchen auch einen alternativen, auf durchschnittlichen Cluster-Returns beruhenden Ansatz. **Eigene Übertragung auf Trading:** Ein hoher gewünschter Return ist kein Stellrad, das verlässlich hohe künftige Rendite erzeugt. [D9]

JEPA ist davon getrennt zu betrachten. Zwei gefundene finanzielle Eigenstudien berichten zwar lernbare Repräsentationen, aber keinen robusten Trading-Vorteil: Fin-JEPA beschreibt schwache bis vernachlässigbare Downstream-Signale; JEPA-Trader berichtet in seiner eigenen Machbarkeitsstudie keinen robusten Vorteil nach Kosten. Diese Autorenberichte sind hilfreiche Gegenbeispiele zu überzogenen Architekturversprechen, keine allgemeine Widerlegung von JEPA. Für die jetzt geklärte Jeff-Anforderung ist JEPA nicht erforderlich. [D10], [D11]

## 4. Empfohlene Verbindung von Transkripten und Entscheidungsmodell

Die folgende Architektur ist eine eigene Implementierungsempfehlung, keine behauptete Eigenschaft einer der zitierten Implementierungen.

1. **Belegbare Aussagen extrahieren.** Pro Aussage Originaltext, Quelle, Sprecher, Instrumentbezug, Veröffentlichungszeit und früheste Verfügbarkeit speichern. Meinung, beobachtete Tatsache und konditionale Aussage unterscheiden.
2. **Signale definieren.** Aus Aussagen messbare Regeln ableiten: Richtung, Horizont, Gültigkeitsdauer, Auslöser, Gegenevidenz und Unsicherheit. Fehlende Angaben nicht durch LLM-Vermutungen ergänzen.
3. **Regeln und Marktzustand trennen.** Stabile Handelsregeln werden zu `desk`; Instrument und Sitzung zu `market_context`; nur zum Entscheidungszeitpunkt verfügbare Signale, Preise und Positionen kommen in `input`. Englischen Jeff-Eingaben Originalbelege in der ursprünglichen Sprache zuordnen.
4. **Entscheider austauschbar halten.** Gleicher Zustand für deterministische Regeln und Jeff; später auch für trainierte Policies. Ein Lauf darf einen nicht erreichbaren Jeff-Dienst nicht stillschweigend durch Heuristiken ersetzen.
5. **Grenzen in Code erzwingen.** Positionsobergrenzen, verfügbare Liquidität, Marktzeit, Kosten, Short-Erlaubnis und Stoppregeln werden nach jeder Modellantwort deterministisch geprüft. Im ersten Prototyp genügen `flat` und begrenzte Long-Positionen, falls keine andere Mandatsdefinition vorliegt.
6. **Simulation getrennt messen.** Regelgenauigkeit, Konfidenzkalibrierung, Enthaltungsquote und Latenz gehören in einen technischen Bericht; Nettorendite, Drawdown, Exposure und Umsatz in einen getrennten Handelsbericht.
7. **Erst den Zusatznutzen prüfen.** Vergleiche mindestens: keine Position, einfache feste Regel, Regel mit Transkriptsignal, Jeff mit denselben Inputs. So wird sichtbar, ob ein Gewinn aus Signal, Marktexposure oder Entscheider stammt.

### Für einen glaubwürdigen Funktionstest

Ein erfolgreicher Prototyp sollte nachweisen, dass ein tatsächliches Transkript in nachvollziehbare Signale übergeht, der Marktzeitpunkt korrekt zugeordnet wird, Positionen erst nach Signalverfügbarkeit entstehen und Gebühren bei Positionsänderungen anfallen. Für Jeff gehören reale Erreichbarkeit und eine echte Modellantwort zum Integrationstest; ein gemockter HTTP-Test prüft nur den Vertrag.

### Für einen späteren Alpha-Test

Vor dem ersten Test Handelsuniversum, Zeitraum, Gebühren, Slippage, Haltedauer und Benchmark festlegen. Training, Kalibrierung und Test chronologisch trennen; bei überlappenden Zielhorizonten eine angemessene Lücke verwenden. Auch Fälle ohne klare Signale im Datensatz behalten. Tests über mehrere Marktphasen wiederholen und Hyperparameter nicht nach dem letzten Testfenster wählen. Diese Empfehlungen sollen verhindern, dass eine technisch korrekte Pipeline mit einer ökonomisch nachgewiesenen Strategie verwechselt wird.

## Quellenverzeichnis

Alle URLs am 13. November 2026 geprüft. Die Jeff-Dateien sind nach Möglichkeit auf den beobachteten Commit festgehalten; volatile Webseiten können ältere Inhalte zeigen.

- **[J1]** Jeff Trading-Adapter, v1.4-Model-Card: https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/release/hf/jeff-adapter-trading-desk/README.md
- **[J2]** Jeff Base, v1.4-Model-Card: https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/release/hf/jeff-base/README.md
- **[J3]** Repository und festgehaltener Commit: https://github.com/firelex/jeff ; https://github.com/firelex/jeff/commit/59898ae9e12621bd8e0199b86c951d366f5026b7
- **[J4]** Python SDK Paketdefinition: https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/packages/python/pyproject.toml
- **[J5]** Runtime Paketdefinition: https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/runtime/python/pyproject.toml
- **[J6]** Aktuell veröffentlichte Basen und Gewichts-Hash: https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/catalogue/bases.yaml
- **[J7]** Trading-Manifest, Funktionsnamen und Kalibrierung: https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/catalogue/jeff.finance.trading-desk/manifest.yaml
- **[J8]** Decide-Request-Schema: https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/contract/schemas/decide_request.schema.json
- **[J9]** Decide-Response-Schema: https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/contract/schemas/decide_response.schema.json
- **[J10]** Decision-Schema: https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/contract/schemas/decision.schema.json
- **[J11]** Legacy-Request-Schema: https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/contract/schemas/systemone_request.schema.json
- **[J12]** Legacy-Response-Schema: https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/contract/schemas/systemone_response.schema.json
- **[J13]** Runtime-Dokumentation: https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/runtime/python/README.md
- **[J14]** CLI und gültige Backendwerte: https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/packages/python/src/jeff/cli.py
- **[J15]** Betriebsdokumentation: https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/docs/operating.md
- **[D1]** Chen et al., Decision Transformer, NeurIPS 2021: https://proceedings.neurips.cc/paper/2021/file/7f489f642a0ddb10272b5c31057f0663-Paper.pdf
- **[D2]** Offizielle DT-Implementierung, MIT: https://github.com/kzl/decision-transformer
- **[D3]** Yun, Pretrained LLM Adapted with LoRA as a Decision Transformer for Offline RL in Quantitative Trading, eingereicht 26. November 2024: https://arxiv.org/abs/2411.17900 ; Volltext https://arxiv.org/html/2411.17900v1
- **[D4]** Zugehöriger Replikationscode: https://github.com/syyunn/finrl-dt
- **[D5]** Kumar et al., Conservative Q-Learning, NeurIPS 2020: https://arxiv.org/abs/2006.04779
- **[D6]** Offizieller CQL-Code: https://github.com/aviralkumar2907/CQL
- **[D7]** CORL, vom Projekt gepflegter Fork mit DT, CQL, IQL und weiteren Verfahren: https://github.com/corl-team/CORL
- **[D8]** Liu et al., Self-supervised Pretraining for Decision Foundation Model, zuletzt geändert 5. Januar 2024: https://arxiv.org/abs/2401.00031
- **[D9]** Paster et al., You Can't Count on Luck, Version vom 28. November 2022: https://arxiv.org/abs/2205.15967
- **[D10]** Wang, Fin-JEPA, Manuskript vom 30. Mai 2026, auf SSRN eingestellt am 18. Juni 2026: https://ssrn.com/abstract=6855118 ; Implementierung https://github.com/cedricwyh/fin-jepa
- **[D11]** Vine, JEPA-Trader, eigene Machbarkeitsstudie, Juni 2026: https://bryanvine.github.io/jepa-trader/ ; Implementierung https://github.com/bryanvine/jepa-trader

