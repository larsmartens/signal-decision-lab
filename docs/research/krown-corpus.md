# Krown source corpus

The collector uses Eric Krown's own YouTube channel,
[`@ECKrown`](https://www.youtube.com/@ECKrown), pinned to channel ID
`UCnwxzpFzZNtLH8NgTeAROFA`. Both the channel listing and each selected watch page
must identify that channel. The scope is regular market-analysis uploads and
completed livestreams. Guest appearances and other channels' summaries are separate
sources and are not substituted for his own commentary.

## Latest source reading

The public [Videos](https://www.youtube.com/@ECKrown/videos) and
[Live](https://www.youtube.com/@ECKrown/streams) tabs were checked on 14 November 2026
at approximately 01:07 UTC. The selected sources were the two newest regular videos
and the two newest completed streams then listed. No November 14 publication was
listed at that observation time.

| Published UTC | Type | Duration | Source |
| --- | --- | ---: | --- |
| 2026-11-13 17:57:23 | Completed livestream | 1:21:57 | [09poJg_Fm1w](https://www.youtube.com/watch?v=09poJg_Fm1w) |
| 2026-11-12 21:54:54 | Regular video | 11:54 | [jI8dKkBSPuQ](https://www.youtube.com/watch?v=jI8dKkBSPuQ) |
| 2026-11-11 17:45:04 | Regular video | 12:18 | [7oTGS8m-94s](https://www.youtube.com/watch?v=7oTGS8m-94s) |
| 2026-11-09 18:31:16 | Completed livestream | 1:33:52 | [_vVNNnKqdDw](https://www.youtube.com/watch?v=_vVNNnKqdDw) |

All four caption acquisitions succeeded, yielding 6,187 automatically generated
English segments. Retrieval occurred on 14 November 2026 between 01:07:41 and
01:07:46 UTC. The [source manifest](../../datasets/krown-latest-20261114/sources.json)
records publication, acquisition and content hashes. Titles can change; source IDs
and the captured metadata identify the recording used.

The [latest report](krown-latest-20261114.md) interprets the commentary in context.
The [structured annotations](../../annotations/krown-20261114/claims.json) contain a
selected set of scenarios, not an exhaustive reference labeling of every statement
in the four recordings. The November 9 source was also inspected in earlier work,
so this reading is not a blind evaluation set.

## Retained historical acquisition

The earlier acquisition remains under
[`datasets/krown-20261113`](../../datasets/krown-20261113/sources.json):

- [Source selection and metadata](../../datasets/krown-20261113/sources.json).
- [Acquisition receipts](../../datasets/krown-20261113/acquisition.json).
- [Acquisition validation](../../datasets/krown-20261113/acquisition-validation.json).
- [Market data and provenance](market-data.md).

That capture contains 36 sources: 18 regular videos and 18 completed streams,
published between September 8 and November 10, 2026. All selected captions were
retrieved, totaling 66,992 segments. The original inventory covered 120 unique IDs;
118 watch pages yielded verified metadata, while two returned a YouTube sign-in
requirement. Those failures were recorded and were not bypassed.

The stored selection retains its original development and holdout names. These
labels describe the earlier acquisition. They do not create an unseen test set for
the revised semantic workflow. The previous word-based analysis and its result files
have been removed; the retained files describe source acquisition only.

## Timestamp and evidence rules

`published_at` comes from the watch page's exact publication timestamp, converted to
UTC. A date-only value does not become an invented time. Completed streams also retain
verified live start and end times; archive publication can occur after the live event.

Canonical transcript `available_at` is the actual caption retrieval time. It is never
replaced with the earlier publication time. Current captions may differ from those
available during the recording or at publication. A historical processing assumption
must therefore be recorded separately from the actual capture.

Caption segments retain the provider's times and text. Their times locate the caption
span; they are not verified word-level audio alignment. Generated captions can mishear
numbers and tickers. When the surrounding passage cannot resolve such an error, leave
the affected field uncertain or check the recording.

Public annotations store paraphrases, source hashes, segment references and character
offsets. Loading them requires the exact canonical local transcript and validates the
referenced substrings. Complete captions, raw watch pages and provider responses stay
under ignored `data/`. A fresh download with changed metadata or content cannot be
silently treated as the same capture.

## Acquisition commands

Install the optional dependency, then run from the repository root:

```bash
python -m pip install -e '.[youtube]'
python scripts/collect_krown.py --root data/krown-new discover --pages 2
python scripts/collect_krown.py --root data/krown-new metadata --workers 4
python scripts/collect_krown.py --root data/krown-new captions \
  --selection data/krown-new/selection.json --workers 3
```

Create the selection file after inspecting the dated inventory and before examining
outcomes. It contains an `entries` array with the selected `source_id` values. Record
the reason for selection and retain failed caption requests without replacing them
with more convenient sources.

The collector caches successful public requests with their URLs, retrieval times and
hashes. It uses standard-library HTTP for public pages and
[youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) for captions.
The channel-page interface can change. The collector does not authenticate, download
audio, run speech recognition or recover information absent from the captions.
