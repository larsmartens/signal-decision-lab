# Review record

The semantic revision is reviewed against parent
`4582f5620efba053411879646bd6c727e82d2b41`. It removes the word-based Krown experiment
and adds contextual annotations with a bounded OpenRouter/Jev fidelity check.

## Source interpretation

A non-author assistant read the complete November 13 stream, both November 11 and 12
daily videos, and the November 9 RDW, CRSP, XMR, INJ, LINK and UI passages with context.
It found no material interpretation errors in the reading or the eight candidate records.
All 275 cited caption references matched the captured text.

That verdict applies to the captions. The reviewer did not inspect audio, chart frames,
subsequent prices or whether a conditional setup later activated. The
[receipt](validation/semantic-context-review.json) records those boundaries and the
reviewed artifact hashes.

Examples that distinguish faithful interpretation from a direction label:

- BTC's long-term spot accumulation is separate from a daily trading entry that still
  requires bullish divergence. Its macro-low failure case belongs to another horizon.
- TSLA's daily support at $380 is separate from the $413.15 bullish confirmation.
- HYPE's daily close below $69 is a pending condition, despite the speaker expecting it.
- RDW's invalidation uses a weekly close; the speaker explicitly corrects an earlier
  mention of a daily close.
- XMR's pullback forecast concerns Monero even though Bitcoin appears in the question.
- Conflicting BE levels and ambiguous instrument identities remain unresolved.

## Software review

Separate non-author reviews exercised the client and semantic runner through their public
interfaces. The client review used a local HTTP server and malformed-response probes.
The runner review used the actual eight-claim input and verified that missing credentials
return an error without creating a completed run.

Two concrete review findings were addressed:

| Finding | Change | Distinguishing check |
|---|---|---|
| A later oversized request could fail after an earlier request had already been charged | Preflight the complete serialized request for every declared claim before the first call | A valid first claim followed by an oversized second claim must send zero HTTP requests. |
| Fixture and production receipts did not identify their transport | Record endpoint and transport mode in the protocol and cached request identity | Loopback receipts identify `loopback_test`; they cannot be reused as OpenRouter results. |

Public annotation manifests contain paraphrases, segment references and hashes. A separate
loader restores exact quotes only from matching local transcripts. Tests reject changed
source content, invalid offsets and altered hashes. Full captions stay outside Git.

The final verification commands and observed results are recorded in
[offline-tests.json](validation/offline-tests.json). Hosted-model behavior remains
unverified until an authenticated provider request succeeds. No amount of local contract
testing establishes semantic accuracy or a profitable strategy.

The [independent software receipt](validation/semantic-software-review.json) pins the reviewed code and fixture blobs. It records the public CLI runs, parent comparison, 210-test suite, malformed-manifest rejection and the remaining limits.
