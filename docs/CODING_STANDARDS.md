# Coding standards

- Python 3.11+ standard library for the default offline flow. Optional services stay at module boundaries.
- Domain timestamps are timezone-aware UTC. Preserve source publication, acquisition,
  extraction and approval times. Never improve availability dates to improve a backtest.
- Keep source claims, executable rules, model judgments, numeric risk and execution separate.
- Preserve unknowns. Unsupported free text remains a claim, with an explicit blocker.
- No signal may approve itself. Quote grounding and source grammar checks run again on review.
- External service output is untrusted. Validate labels, probabilities, types, size and provenance.
- No secret values in logs, fixtures, HTTP error messages or committed files. No redirects with credentials.
- Every new failure mode that could produce a false entry needs a behavioral regression test.
  Pure presentation changes need manual verification, not redundant implementation-mirroring tests.
- Paper decisions use completed bars; fills occur at the next eligible open. Document uncertain
  intrabar ordering, gap assumptions, liquidity omissions and fee/slippage choices.
- Results must distinguish synthetic scenarios, HTTP stubs, true model inference and genuine
  market experiments. Never describe passing tests or calibrated labels as a trading edge.
- Use short explicit modules and functions; avoid generic frameworks until there is a second use.
- `python -m unittest discover -s tests`, `ruff check signal_lab tests`, and `mypy signal_lab`
  are the checks. CI runs all three; changing expected financial behavior requires an explanation.
