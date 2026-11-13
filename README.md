# Signal Decision Lab

Privater Research-Draft für Trading-Aussagen aus Videos und Transkripten und Decision Models wie Jeff. Stand: 13. November 2026.

## Zum vollständigen Entwurf

Der lauffähige Prototyp liegt auf dem Branch [draft/prototype](https://github.com/larsmartens/signal-decision-lab/tree/draft/prototype). Er wird als Draft-PR zur Prüfung bereitgestellt.

- [Startanleitung und Umfang](https://github.com/larsmartens/signal-decision-lab/blob/draft/prototype/README.md)
- [Konkreter Umsetzungsplan](https://github.com/larsmartens/signal-decision-lab/blob/draft/prototype/docs/PLAN.md)
- [Evaluationsdesign](https://github.com/larsmartens/signal-decision-lab/blob/draft/prototype/docs/EVALUATION.md)
- [Recherche zu Jeff und anderen Decision Models](https://github.com/larsmartens/signal-decision-lab/blob/draft/prototype/docs/research/decision-models.md)
- [Recherche zu Video- und Transkript-Trading-Systemen](https://github.com/larsmartens/signal-decision-lab/blob/draft/prototype/docs/research/video-signals.md)
- [Ausgeführte Validierung und Grenzen](https://github.com/larsmartens/signal-decision-lab/blob/draft/prototype/docs/VALIDATION.md)

## Ergebnis

Die Offline-Pipeline importiert zeitgestempelte Transkripte, extrahiert belegte Aussagen, verlangt vollständige überprüfte Setups und führt konservative Paper-Replays aus. Sie enthält 146 bestandene lokale Verhaltenstests, einen HTML-Bericht, optionale YouTube-/ASR-/LLM-Adapter und einen Jeff-v1.4-Client.

Ein echter YouTube-Abruf lieferte 646 Untertitelsegmente eines Krown-Interviews. Echte Jeff-Inferenz wurde mit offiziellen Gewichten auf CPU geprüft. Die kleinen Modellproben begründen derzeit keine Einstiegsfreigabe durch den Trading-Adapter. Die deterministische Regelbasis bleibt Standard.

Keine profitable Krown-Strategie ist nachgewiesen. Die erste Entwicklungsstufe ist ein echter, zeitlich sauber erfasster Korpus mit manuell geprüften Aussagen; danach folgen getrennte Extraktions-, Modell- und Strategieevaluierung.

## Lokal ausführen

```bash
git clone https://github.com/larsmartens/signal-decision-lab.git
cd signal-decision-lab
git checkout draft/prototype
python -m signal_lab demo
python -m unittest discover -s tests -v
```

Python 3.11+; für Demo und Tests sind keine API-Schlüssel oder Zusatzpakete nötig. Der Draft enthält keine Broker-Orderausführung.
