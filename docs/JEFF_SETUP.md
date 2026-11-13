# Jeff v1.4 einrichten und prüfen

Die Anwendung verwendet Jeff als optionalen Entscheider für beschriebene Regeln. Jeffs Konfidenz beschreibt die Auswahl einer Regelaktion; sie ist keine Gewinnwahrscheinlichkeit.

## Festgehaltener Quellstand

- Repository: [firelex/jeff](https://github.com/firelex/jeff)
- Commit: [59898ae9e12621bd8e0199b86c951d366f5026b7](https://github.com/firelex/jeff/commit/59898ae9e12621bd8e0199b86c951d366f5026b7), 6. November 2026
- Runtime und SDK: 1.4.1; Python mindestens 3.13
- Base: `mstrasser/jeff-base@v1.4`
- Adapter: `mstrasser/jeff-adapter-trading-desk@v1.4`, Adapterversion 1.4.0
- Funktion: `jeff.finance.trading-desk.direction`
- HTTP-Vertrag: [Request](https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/contract/schemas/decide_request.schema.json), [Response](https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/contract/schemas/decide_response.schema.json), [Decision](https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/contract/schemas/decision.schema.json)

Die aktuelle [Base-Liste](https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/catalogue/bases.yaml) kennzeichnet v1.3 als zurückgezogen. Suchtreffer mit `jeff-serve`, v1.3 oder 98,1 % Trading-Accuracy sind daher keine Anleitung für diesen Stand. Die [v1.4-Model-Card](https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/release/hf/jeff-adapter-trading-desk/README.md) nennt 97,7 % Regelgenauigkeit auf 5.000 intern generierten Testfällen; das ist kein Profitnachweis.

## Separate CPU-Umgebung

Die Trading-Anwendung selbst benötigt diese Modellpakete nicht. Für Jeff eine getrennte Umgebung anlegen. Benötigt werden Git, [uv](https://docs.astral.sh/uv/) und Zugang zu GitHub, PyPI, Hugging Face sowie den PyTorch-Downloadhosts. Proxy- und Zertifikatseinstellungen des Systems beibehalten.

Aus einem eigenen Arbeitsverzeichnis:

```bash
git clone https://github.com/firelex/jeff
git -C jeff checkout 59898ae9e12621bd8e0199b86c951d366f5026b7
uv venv --python 3.13 .venv-jeff
uv pip install --python .venv-jeff/bin/python \
  --index-url https://download.pytorch.org/whl/cpu \
  torch==2.14.0 torchvision==0.29.0
uv pip install --python .venv-jeff/bin/python \
  ./jeff/packages/python ./jeff/runtime/python ./jeff/apps/server
```

Die CPU-Wheels werden zuerst installiert, damit keine NVIDIA-Pakete für diesen CPU-Test benötigt werden. Im dokumentierten Test ergaben sich `torch==2.14.0+cpu` und `torchvision==0.29.0+cpu`. Die lokale Installation aus Quellpfaden wurde erfolgreich ausgeführt. Die Runtime-Pins stehen in der [Paketdefinition](https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/runtime/python/pyproject.toml).

Falls die Umgebung wie der hier verwendete Testrechner einen SOCKS-Proxy vorgibt, benötigt Hugging Face zusätzlich `httpx[socks]`. Dafür wurde `uv pip install --python .venv-jeff/bin/python 'httpx[socks]==0.28.1'` ausgeführt. Proxy und TLS-Prüfung bleiben aktiviert.

Das erste Laden benötigt die Modellgewichte von Hugging Face. Das Repository nennt rund 1,7 GB für die Base; zusätzlich werden Adapter, Frameworks und Cache benötigt. Downloadgröße und Arbeitsspeicherbedarf sind unterschiedliche Größen.

## Modellprozess starten

**Grenze des hier verwendeten Executors:** Der offizielle Server konnte nach erfolgreichem Laden der Gewichte keinen Unix-Socket erzeugen: `socket.socket(AF_UNIX, SOCK_STREAM)` endet mit `PermissionError: [Errno 1] Operation not permitted`. Die unten beschriebene Server-Topologie benötigt eine Umgebung, die lokale Unix-Sockets erlaubt. Es wurde keine Netz- oder Sandbox-Einstellung umgangen. Der tatsächliche Modelltest wurde über die dokumentierte In-Process-Schnittstelle `jeff.Jeff.local(["trading-desk"], backend="torch")` durchgeführt.

Im selben Arbeitsverzeichnis:

```bash
OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
.venv-jeff/bin/jeff runtime serve \
  --socket /tmp/jeff-trading.sock \
  --adapter trading-desk \
  --backend torch \
  --batch-window-ms 1 \
  --max-batch-rows 1 \
  --queue-limit-rows 64 \
  --prepare-workers 1
```

Der explizite Backendwert `torch` und die vier Scheduler-Optionen entsprechen der [aktuellen CLI](https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/packages/python/src/jeff/cli.py). Andere Backendwerte sind `auto`, `mlx` und `fast`; der NVIDIA-Pfad benötigt weitere Parameter und ist hier nicht getestet.

In einem zweiten Terminal prüfen:

```bash
.venv-jeff/bin/jeff runtime health --socket /tmp/jeff-trading.sock --timeout-s 5
```

## HTTP-Dienst starten

Sobald der Modellprozess bereit ist, in einem weiteren Terminal:

```bash
JEFF_ENGINE_SOCKETS=/tmp/jeff-trading.sock \
JEFF_MODEL_NAME=jeff-v1.4 \
.venv-jeff/bin/jeff-server serve \
  --host 127.0.0.1 --port 8765 --workers 1
```

Der lokale Dienst wird bewusst an Loopback gebunden. Die aktuellen Betriebsoptionen stehen in [docs/operating.md](https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/docs/operating.md).

## Verwendung durch Signal Decision Lab

```python
from signal_lab.jeff import JeffClient

client = JeffClient(base_url="http://127.0.0.1:8765", timeout=10)
result = client.judge(signal, completed_bar)
```

`signal` und `completed_bar` sind validierte `Signal`- und `Bar`-Objekte. Bei einem geschützten Dienst kann ein Schlüssel über `api_key=` übergeben werden; Schlüssel gehören nicht ins Repository.

Die Anwendung sendet `POST /v1/decide` mit der festgehaltenen Direction-Funktion. Als Zustand überträgt sie ausschließlich das Signal samt Belegen und die zum Entscheidungszeitpunkt abgeschlossene Kerze. Portfoliozustand, Orderbuch und künftige Kurse werden nicht erfunden. Ein Signal aus der Zukunft, ein abgelaufenes Signal oder ein Instrumentkonflikt führen bereits vor dem HTTP-Aufruf zur Enthaltung.

Die Antwort wird streng geprüft: genau eine Entscheidung, korrekte Funktion und Adapterversion, die Labels `buy/sell/hold`, endliche Wahrscheinlichkeiten zwischen null und eins mit Summe eins, ausgewählte Aktion als Maximum und passende Konfidenz. Der [aktuelle Decision-Code](https://github.com/firelex/jeff/blob/59898ae9e12621bd8e0199b86c951d366f5026b7/packages/python/src/jeff/decision.py) definiert die Konfidenz für diese API als Wahrscheinlichkeit der gewählten Aktion.

Bei Ausfall, ungültiger Antwort, Enthaltung des Modells, fehlender Kalibrierung oder einer Richtung gegen das Signal liefert der Client `hold` mit `abstained=true`. Die feste Fallback-Verteilung ist durch `probability_source="fail_closed_policy"` als Anwendungsentscheidung markiert; ihre Konfidenz ist null. Eine gültige, aber verworfene Modellentscheidung bleibt separat für die Prüfung erhalten. Der Client wechselt nicht heimlich auf Heuristiken.

## Testnachweis

```bash
python -m unittest discover -s tests -p test_jeff.py -v
```

Am 13. November 2026 bestanden **12 Tests** mit echten HTTP-Aufrufen gegen einen lokalen Testserver. Sie prüfen Request-Format und Belegzuordnung, Zeitgrenzen, Gegenrichtung, Enthaltung, Kalibrierung, ungültige Wahrscheinlichkeiten, Versionen, Serverfehler, Weiterleitungen und Nicht-Erreichbarkeit. Diese Tests laden keine Modellgewichte.

### Tatsächliche Modellinferenz am 13. November 2026

Die offiziellen v1.4-Gewichte wurden heruntergeladen und mit `jeff.Jeff.local(["trading-desk"], backend="torch")` geladen. Verwendet wurden Python 3.13.5 und PyTorch 2.14.0+cpu; CUDA war nicht verfügbar. Das Skript forderte vor dem Laden vier Threads an, die Runtime meldete anschließend acht CPU-Threads in beiden unveränderten Messdateien. Das Laden aus dem lokalen Cache dauerte 15,49 Sekunden. Es wurden zwei Aufrufe mit demselben durch `JeffClient` gebauten Zustand ausgeführt. Beide verwendeten ein ausdrücklich synthetisches Long-Signal mit der Bedingung „Fünf-Minuten-Schlusskurs über 100“, verfügbar zehn Minuten vor dem Entscheidungszeitpunkt.

| Fall | Schlusskurs | Erwartete Regelaktion | Tatsächliche Jeff-Aktion | Konfidenz | Enthaltung | Dauer |
|---|---:|---|---|---:|---|---:|
| Auslöser erfüllt | 101 | buy | hold | 0,8884098 | ja | 3.152 ms |
| Auslöser nicht erfüllt | 99 | hold | hold | 0,9888063 | nein | 3.101 ms |

Beide Antworten meldeten `calibrated=true`, die korrekte Funktion und Adapterversion 1.4.0. Die aktuelle Direction-Schwelle beträgt 0,980730. Die erste Antwort bleibt darunter und wird enthaltend behandelt. Die CPU verwendete korrekte PyTorch-Referenzimplementierungen für die fehlenden beschleunigten CUDA-Kernels; die gemessene Dauer ist ein einzelner Funktionstest und kein belastbarer Performance-Benchmark.

**Ergebnis:** Echte lokale Modellinferenz ist nachgewiesen. Die korrekte Umsetzung beider Entry-Fälle ist es nicht: Jeff erkannte den erfüllten Einstieg nicht. Die Payload enthält bewusst keine erfundenen Positionen, Spreads oder Orderbücher und weicht damit von der Trainingsdomäne ab. Der deterministische Regelentscheider bleibt deshalb die Standardbasis. Die zwei Fälle sind kein Accuracy-, Profitabilitäts- oder Generalisierungsnachweis.

Die Ende-zu-Ende-Verbindung des offiziellen HTTP-Dienstes mit diesen Gewichten wurde wegen der Unix-Socket-Sperre nicht ausgeführt. Nachgewiesen sind getrennt die echte In-Process-Inferenz und die 12 HTTP-Vertragstests gegen einen lokalen Testserver.

### Einmaliger Vergleich mit kompakter Darstellung

Anschließend wurde genau eine alternative Darstellung untersucht: kurze, explizite Desk-Regeln plus die aktuellen Fakten als Text statt des gesamten Signalobjekts mit Zitaten. Sechs Fälle und ihre Erwartungen standen vor dem Lauf fest. Die Alternative ist im Reproduktionsskript als `concise` enthalten und wurde **nicht** in den produktiven HTTP-Client übernommen.

| Vorab festgelegter Fall | Erwartet | Jeffs erste Wahl | Konfidenz | Enthaltung | Dauer |
|---|---|---|---:|---|---:|
| Long, Auslöser erfüllt | buy | buy | 0,6046533 | ja | 2.411 ms |
| Long, Auslöser nicht erfüllt | hold | hold | 0,9704145 | ja | 2.594 ms |
| Long, Schlusskurs genau auf Schwelle | hold | hold | 0,8487236 | ja | 2.679 ms |
| Short, Auslöser erfüllt | sell | hold | 0,8461812 | ja | 2.545 ms |
| Short, Auslöser nicht erfüllt | hold | hold | 0,9052068 | ja | 2.510 ms |
| Schutz-Stop fehlt | hold | buy | 0,5789002 | ja | 2.658 ms |

Vier der sechs zuerst gewählten Labels stimmen mit der vorab definierten Regel überein; **alle sechs Entscheidungen enthalten sich** unter der unveränderten Adapter-Schwelle. Die falsche Buy-Auswahl ohne Stop zeigt zusätzlich, weshalb die Risiko-Prüfung in Code unabhängig vom Modell bestehen bleiben muss. Diese sechs Beispiele sind keine Schätzung der allgemeinen Accuracy. Es gab kein weiteres Prompt-Tuning und keine Absenkung von Konfidenz- oder Risikogrenzen.

**Praktische Entscheidung:** Für die hier formulierten, einfachen Zahlenregeln bietet der getestete Adapter keinen nachgewiesenen Vorteil gegenüber Code. Er bleibt optional für einen protokollierten Vergleich im Hintergrund; die deterministische Strategie ist die Grundlage. Ein späterer Einsatz für schwierigere Textentscheidungen benötigt einen eigenen, vorab definierten Datensatz und eine eigene Kalibrierung.

### Messdaten und Reproduktion

- [Ursprüngliche zwei Modellaufrufe](validation/jeff-cpu-smoke.json), unverändert übernommen.
- [Alle sechs Aufrufe mit kompakter Darstellung](validation/jeff-cpu-concise-smoke.json), einschließlich vollständiger Requests, Modellverteilungen, Enthaltung und Laufzeiten.
- [Portables Reproduktionsskript](../scripts/smoke_jeff_local.py). Es importiert die installierte offizielle Jeff-Runtime und das eigene Projekt; es enthält keinen kopierten Vendor-Code.

Aus dem Repository-Stamm mit dem Python der getrennten Jeff-Umgebung:

```bash
/pfad/zur/.venv-jeff/bin/python scripts/smoke_jeff_local.py \
  --experiment all \
  --output docs/validation/jeff-local-reproduction.json
```

`--experiment original` führt nur die ursprünglichen zwei Fälle aus, `--experiment concise` nur die sechs Vergleichsfälle. Ein Exit-Code null bedeutet, dass die Modellaufrufe abgeschlossen und protokolliert wurden; er behauptet keine Übereinstimmung aller Antworten mit den Erwartungen. Modell- und Paketversionen sowie der festgehaltene Source-Commit stehen in der erzeugten JSON-Datei.

## Grenzen

Die mitgelieferten Kalibrierungsschwellen stammen aus Jeffs Testdomäne. Der Einsatz für Transkriptsignale mit OHLCV-Daten weicht von den Orderbuch-Beispielen des Adapters ab. Korrekte technische Integration belegt daher weder ausreichende Genauigkeit auf eigenen Regeln noch Profitabilität.

Quellen, Forschungseinordnung und Lizenzangaben: [decision-models.md](research/decision-models.md).

