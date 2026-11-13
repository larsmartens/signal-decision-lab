# Krown source corpus

## Identity and scope

The acquisition pins Eric Krown's own YouTube channel to
[`UCnwxzpFzZNtLH8NgTeAROFA`](https://www.youtube.com/channel/UCnwxzpFzZNtLH8NgTeAROFA).
The channel's current displayed name is **Krown** and its handle is
[`@ECKrown`](https://www.youtube.com/@ECKrown). The official channel page's
`channelMetadataRenderer` supplies the channel ID, owner URL and name together.
Each selected video's own watch-page `videoDetails` must independently match
that same channel ID. Searches for the older names Eric Krown Crypto and
Krown's Crypto Cave were used for discovery, not as sufficient proof of
ownership.

The intended research corpus consists of his normal market-analysis uploads
and completed analysis livestreams. Other channels' interviews, guest
appearances, Shorts, courses and general trading tutorials are outside the
evaluation scope. The discovery inventory deliberately retains ordinary
educational uploads as candidates; their presence in an inventory is not an
assertion that they are eligible for the evaluation. Exact video IDs, content
types and dates govern selection. Titles can change: the cache preserves both
the title found on the channel listing and the title returned by the watch
page.

The channel is accessible through its public
[Videos](https://www.youtube.com/@ECKrown/videos) and
[Live](https://www.youtube.com/@ECKrown/streams) tabs. Metadata and captions were
obtained without an account, supplied login cookies, a login or an
access-control workaround.

## Discovery inventory

The first two pages of each official tab yielded 120 unique IDs. Watch-page
metadata was verified for 118 IDs between **2026-11-13 23:10:30 UTC** and
**23:12:07 UTC**. Every verified record has the pinned channel ID, an exact
publication timestamp and `isShortsEligible: false`. All 60 records classified
as completed livestreams include YouTube's live start and end timestamps.

| Publication month | Normal videos | Completed livestreams |
| --- | ---: | ---: |
| June 2026 | 0 | 6 |
| July 2026 | 0 | 13 |
| August 2026 | 0 | 13 |
| September 2026 | 23 | 10 |
| October 2026 | 26 | 13 |
| November 2026 | 9 | 5 |
| **Total verified** | **58** | **60** |

The earlier June and July streams are incidental inventory coverage, not an
expansion of the requested evaluation period. The November inventory includes
a November 13 stream that cannot support a full subsequent 24-hour outcome at
the fixed November 13 market-data cutoff.

Two candidate watch pages returned YouTube's `LOGIN_REQUIRED` state and the
reason “Sign in to confirm you're not a bot”: `wvu0onib6WU` and `BrF-Qz1Hur0`.
Their HTML, discovery records and failure reasons remain in the ignored cache.
Neither was substituted with a video from another channel or retrieved through
an authentication workaround. A preliminary RSS-feed request returned HTTP
404; discovery therefore used the two public channel tabs. The web-search
fetcher also throttled several YouTube pages, while direct public-page requests
from the workspace succeeded.

Inventory files under the ignored `data/krown/` tree are:

- `inventory.json`: the 120 IDs and their listing provenance.
- `dated-inventory.json`: the 118 verified records and two explicit failures.
- `candidate-inventory.csv`: a compact view of ID, publication time, type,
  duration, live start/end, title and source URL.
- `channel.json`: official channel identity and the supporting page hash.
- `discovery/`, `watch/`, `metadata/`, and `metadata-failures/`: source pages,
  retrieval evidence, normalized metadata and failure records.

No market-price files or returns are read by the acquisition script. The dated
inventory was delivered to the evaluation owner before choosing a chronological
split or downloading the selected corpus's captions. A single caption probe
confirmed that the installed provider worked; it was an access check, not a
source-selection criterion.

## Frozen selection and acquired captions

The evaluation owner froze the selection at **2026-11-13 23:14:18 UTC**, after the dated inventory was available and before downloading the selected caption corpus. The immutable public source manifest is [`experiments/krown-20261114/sources.json`](../../experiments/krown-20261114/sources.json). The study identifier uses November 14; the actual acquisition occurred on November 13 UTC.

The rule requires a Bitcoin or BTC analysis title, at least five minutes of recorded duration, a verified own-channel source and exclusion of educational explainer patterns. Within each period and content type, eligible records are sorted chronologically and sampled at equally spaced indices, including the endpoints. Selection does not depend on extracted signals or subsequent returns. Failed caption downloads would remain failures rather than trigger replacement.

| Split | Actual publication span | Normal analyses | Completed streams | Acquired | Source duration | Caption segments |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Development | September 8–28, 2026 | 6 | 6 | 12 of 12 | 13 h 35 m 39 s | 22,425 |
| Holdout | October 1–November 10, 2026 | 12 | 12 | 24 of 24 | 25 h 2 m 39 s | 44,567 |
| **Total** | **September–November 2026** | **18** | **18** | **36 of 36** | **38 h 38 m 18 s** | **66,992** |

Caption acquisition ran from **2026-11-13 23:14:40.727434 UTC** through **23:15:41.771485 UTC**. All 36 tracks are English. The provider designates 27 tracks as generated and nine as non-generated; that designation is not an independent human accuracy review. There were **zero selected-source caption failures**. The earlier two metadata failures remain in the discovery audit.

All 36 canonical files passed the project's `Transcript.from_dict` validation, every recorded caption content hash matched its file, and all raw transcript files are ignored by Git. The last returned caption in every source reaches at least 97.9% of the recorded video duration. This checks for an obviously truncated tail; it does not establish complete word coverage or accurate transcription.

The following table reproduces the frozen source IDs and original publication timestamps. “Video” means a normal analysis upload; “stream” means a completed livestream with verified start and end metadata. All rows were acquired successfully.

| Split | Published UTC | Type | Duration | Source ID |
| --- | --- | --- | ---: | --- |
| Development | 2026-09-08 17:53:50 | Video | 18:58 | [DyB0RL8GnhA](https://www.youtube.com/watch?v=DyB0RL8GnhA) |
| Development | 2026-09-10 06:29:23 | Stream | 1:52:21 | [Wo7tnwTMYNQ](https://www.youtube.com/watch?v=Wo7tnwTMYNQ) |
| Development | 2026-09-11 18:24:41 | Stream | 1:51:13 | [nujnKp4lVbo](https://www.youtube.com/watch?v=nujnKp4lVbo) |
| Development | 2026-09-11 23:00:06 | Video | 14:32 | [8LBiM6deRks](https://www.youtube.com/watch?v=8LBiM6deRks) |
| Development | 2026-09-15 17:47:57 | Video | 20:04 | [jc2HQXgcY5s](https://www.youtube.com/watch?v=jc2HQXgcY5s) |
| Development | 2026-09-16 19:28:11 | Stream | 2:48:45 | [PXWP9f2bpPU](https://www.youtube.com/watch?v=PXWP9f2bpPU) |
| Development | 2026-09-18 18:09:04 | Stream | 1:54:03 | [pT7jeM9j490](https://www.youtube.com/watch?v=pT7jeM9j490) |
| Development | 2026-09-18 23:00:35 | Video | 14:29 | [UtCC3s_lo3o](https://www.youtube.com/watch?v=UtCC3s_lo3o) |
| Development | 2026-09-22 17:49:41 | Video | 15:55 | [sZPfKVEoK0I](https://www.youtube.com/watch?v=sZPfKVEoK0I) |
| Development | 2026-09-23 18:29:46 | Stream | 2:00:51 | [mEHFdbVMyrQ](https://www.youtube.com/watch?v=mEHFdbVMyrQ) |
| Development | 2026-09-25 18:02:50 | Stream | 1:32:25 | [tPYEYNwhKGc](https://www.youtube.com/watch?v=tPYEYNwhKGc) |
| Development | 2026-09-28 17:29:29 | Video | 12:03 | [uOWagLcNLKM](https://www.youtube.com/watch?v=uOWagLcNLKM) |
| Holdout | 2026-10-01 19:24:03 | Video | 16:21 | [rNtVHO9JZm8](https://www.youtube.com/watch?v=rNtVHO9JZm8) |
| Holdout | 2026-10-03 06:02:06 | Stream | 1:29:47 | [AwgwAItUyoQ](https://www.youtube.com/watch?v=AwgwAItUyoQ) |
| Holdout | 2026-10-05 18:24:37 | Video | 17:36 | [AUP1UMotI5w](https://www.youtube.com/watch?v=AUP1UMotI5w) |
| Holdout | 2026-10-06 18:02:22 | Video | 14:27 | [V0gjxlaW2Qk](https://www.youtube.com/watch?v=V0gjxlaW2Qk) |
| Holdout | 2026-10-08 06:28:24 | Stream | 1:36:44 | [4-LZ1_9n4vc](https://www.youtube.com/watch?v=4-LZ1_9n4vc) |
| Holdout | 2026-10-08 18:41:33 | Video | 15:25 | [IJN6hlhJ8ZY](https://www.youtube.com/watch?v=IJN6hlhJ8ZY) |
| Holdout | 2026-10-12 20:14:57 | Stream | 1:55:25 | [3BIzcbfWzuU](https://www.youtube.com/watch?v=3BIzcbfWzuU) |
| Holdout | 2026-10-13 00:23:11 | Video | 23:22 | [uFjS2qFEZmE](https://www.youtube.com/watch?v=uFjS2qFEZmE) |
| Holdout | 2026-10-14 20:12:26 | Stream | 1:54:56 | [Vn391v0U1lI](https://www.youtube.com/watch?v=Vn391v0U1lI) |
| Holdout | 2026-10-15 18:17:28 | Video | 22:06 | [TDQwVve6G3Y](https://www.youtube.com/watch?v=TDQwVve6G3Y) |
| Holdout | 2026-10-19 19:43:12 | Stream | 1:54:32 | [4xbNMfb_QUs](https://www.youtube.com/watch?v=4xbNMfb_QUs) |
| Holdout | 2026-10-20 00:00:38 | Video | 19:37 | [ro6tMlqbbBI](https://www.youtube.com/watch?v=ro6tMlqbbBI) |
| Holdout | 2026-10-22 01:00:17 | Video | 15:30 | [LMRNBdMiQ2g](https://www.youtube.com/watch?v=LMRNBdMiQ2g) |
| Holdout | 2026-10-22 07:49:51 | Stream | 1:32:57 | [R0MW3Lhjmis](https://www.youtube.com/watch?v=R0MW3Lhjmis) |
| Holdout | 2026-10-26 18:08:20 | Stream | 1:32:01 | [CicUYUaeF5E](https://www.youtube.com/watch?v=CicUYUaeF5E) |
| Holdout | 2026-10-27 00:30:30 | Video | 23:52 | [zay_owGmjo0](https://www.youtube.com/watch?v=zay_owGmjo0) |
| Holdout | 2026-10-28 19:13:36 | Stream | 2:07:37 | [mTIm-ykXBGY](https://www.youtube.com/watch?v=mTIm-ykXBGY) |
| Holdout | 2026-10-30 20:21:03 | Stream | 1:45:04 | [_mBMq8jYOY8](https://www.youtube.com/watch?v=_mBMq8jYOY8) |
| Holdout | 2026-11-02 18:31:32 | Stream | 1:54:25 | [37k61H-vRT4](https://www.youtube.com/watch?v=37k61H-vRT4) |
| Holdout | 2026-11-03 18:15:40 | Video | 18:54 | [H9KOaDvzP4Y](https://www.youtube.com/watch?v=H9KOaDvzP4Y) |
| Holdout | 2026-11-05 00:00:12 | Video | 21:35 | [FVakIyoNcqc](https://www.youtube.com/watch?v=FVakIyoNcqc) |
| Holdout | 2026-11-06 20:39:59 | Stream | 2:00:42 | [8wF7kb6nRug](https://www.youtube.com/watch?v=8wF7kb6nRug) |
| Holdout | 2026-11-09 18:31:16 | Stream | 1:33:52 | [_vVNNnKqdDw](https://www.youtube.com/watch?v=_vVNNnKqdDw) |
| Holdout | 2026-11-10 17:56:42 | Video | 15:52 | [78k4GmOT2KE](https://www.youtube.com/watch?v=78k4GmOT2KE) |

The cached `acquisition-summary.json` records each source's paths, language flags, counts and full content hashes. `acquisition-validation.json` records the aggregate validation results. The frozen selection SHA-256 is `bcf100cae62d27c5b1958453968113f540b9ff9190b2e9c91627ad80613003b3`; the completed acquisition-summary SHA-256 is `9564de3c01051482c7b29bce10b75d2dfb860ac7f653f8f18a33de8216608245`. These hashes identify this captured run and do not imply that a later fresh download will have identical content.

## Timestamp semantics and provenance

For a normal video, `published_at` is the exact `publishDate` exposed by the
watch page's `playerMicroformatRenderer`, converted from its explicit timezone
to UTC. The raw publication and upload strings are retained. A date without a
time is not silently promoted to an exact timestamp. Such a record would be
marked `date_only`, and canonical-transcript construction would stop rather
than invent an hour.

The recorded duration comes from `videoDetails.lengthSeconds`; the separate
microformat duration is retained because the two can differ slightly. Stream
classification uses `isLiveContent` and requires a completed
`liveBroadcastDetails.endTimestamp`. Live start and end are retained separately
from the archive's publication timestamp. All 60 observed archives were
published after the stream ended, sometimes by hours.

This matters for historical replay. An assumed processing delay applied to the
stream's end may still precede the archive's documented publication. A replay
that models caption availability from the archive should therefore use at
least the later of archive publication and verified stream end, plus the stated
processing delay. If a study instead assumes live capture while broadcasting,
that assumption needs a separate, explicit record; it is not demonstrated by
downloading an archive months later.

The frozen experiment assumes a 15-minute processing delay. It sets research
availability to publication plus the complete duration plus 15 minutes for a
normal video, and to `max(archive publication, live end) + 15 minutes` for a
stream. These assumptions are deliberately separate from the acquisition
record.

Canonical transcript `available_at` records **actual retrieval time**. The
collector never replaces it with historical publication time. Any research
copy that models an earlier availability must preserve the original record and
label that counterfactual timing assumption. Current downloadable captions do
not establish that identical captions existed at publication: automatic
captions, titles and archived video edits can change over time.

Each successful caption acquisition records the exact source URL and channel
ID, metadata reference, publication timestamp, duration, content type,
retrieval timestamp, language, language code, generated/manual status, provider
version, segment count, last caption end and SHA-256 hashes. The raw envelope
preserves every provider row; the canonical transcript retains nonempty,
positive-duration segments in timestamp order. Raw provider rows and complete
third-party transcripts remain under ignored `data/`, not in the repository.

## Reproduction

Install the project's optional YouTube dependency in the existing project
environment, then run from the repository root:

```bash
.venv/bin/python scripts/collect_krown.py discover --pages 2
.venv/bin/python scripts/collect_krown.py metadata --workers 4
.venv/bin/python scripts/collect_krown.py captions --selection data/krown/selection.json --workers 3
```

The selection file must contain an `entries` array of objects with `source_id`
values from the dated inventory. Additional fields such as split assignment and
selection rationale are accepted without changing caption acquisition. Freeze
this file before examining outcomes. The acquisition summary stores its hash.

Successful HTTP responses are cached with their source URL, retrieval time,
request method and content hash. Reusing a cached HTTP response or caption
checks the corresponding content hash. Caption failures are explicit records;
they are not automatically replaced with another source. `--retry-failed` can
make a new ordinary public-caption request, while retaining the previous
attempt in `attempt-history/`; it does not add a login, proxy rotation or a
restriction bypass. Discovery follows the read-only pagination command
advertised by the public page. This public-page interface can change and is not
a claim of a stable, documented YouTube Data API contract.

The script uses standard-library HTTP for public pages and the project's
optional `youtube-transcript-api` package for caption retrieval. It does not
download audio, run speech recognition, infer prices from video thumbnails or
manufacture missing captions. Cached files make the inspected run reproducible;
a fresh run against a changing channel can return newer titles, captions or
availability states.
