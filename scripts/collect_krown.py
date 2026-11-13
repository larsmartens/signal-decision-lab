#!/usr/bin/env python3
"""Cache public Krown channel listings, dated metadata and English captions.

This is acquisition only: no prices, returns, recommendation scoring or selection
by performance. Raw third-party content belongs under the ignored data/ tree.
YouTube HTML is public and unauthenticated. Listing pagination follows the
read-only continuation endpoint advertised in that page; captions use the
optional youtube-transcript-api dependency. No account cookies or credentials
are supplied.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
from typing import Any
from urllib.request import Request, urlopen


CHANNEL_ID = "UCnwxzpFzZNtLH8NgTeAROFA"
HANDLE = "@ECKrown"
BASE = "https://www.youtube.com"
USER_AGENT = "Mozilla/5.0"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def encoded(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded(value))
    temporary.replace(path)


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def embedded(html: str, name: str) -> dict:
    match = re.search(r"(?:var\s+)?" + re.escape(name) + r"\s*=\s*", html)
    if not match:
        raise ValueError(f"Public page omitted {name}")
    return json.JSONDecoder().raw_decode(html[match.end():])[0]


def request(url: str, *, data: dict | None = None) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    payload = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(data).encode()
    with urlopen(Request(url, headers=headers, data=payload), timeout=40) as response:
        return response.read()


def cached_request(path: Path, url: str, *, data: dict | None = None) -> tuple[bytes, dict]:
    evidence_path = path.with_suffix(path.suffix + ".evidence.json")
    if path.exists() and evidence_path.exists():
        raw, evidence = path.read_bytes(), load(evidence_path)
        if digest(raw) != evidence["sha256"]:
            raise ValueError(f"Cached source hash mismatch: {path}")
        return raw, evidence
    raw = request(url, data=data)
    evidence = {"url": url, "retrieved_at": now(), "sha256": digest(raw),
                "request_method": "POST" if data is not None else "GET"}
    if data is not None:
        evidence["request_body_sha256"] = digest(json.dumps(data, sort_keys=True).encode())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    save(evidence_path, evidence)
    return raw, evidence


def listing_entries(data: dict, tab: str, page: int, evidence: dict) -> list[dict]:
    result = {}
    for node in walk(data):
        if "lockupViewModel" in node:
            item = node["lockupViewModel"]
            if item.get("contentType") != "LOCKUP_CONTENT_TYPE_VIDEO":
                continue
            meta = item.get("metadata", {}).get("lockupMetadataViewModel", {})
            video_id = item.get("contentId", "")
            title = meta.get("title", {}).get("content", "")
            labels = [x["accessibilityLabel"] for x in walk(meta.get("metadata", {}))
                      if "accessibilityLabel" in x]
            duration = [x["thumbnailBadgeViewModel"].get("text", "")
                        for x in walk(item.get("contentImage", {}))
                        if "thumbnailBadgeViewModel" in x]
        elif "videoRenderer" in node:
            item = node["videoRenderer"]
            video_id = item.get("videoId", "")
            title = "".join(r.get("text", "") for r in item.get("title", {}).get("runs", []))
            labels = [item.get("publishedTimeText", {}).get("simpleText", "")]
            duration = [item.get("lengthText", {}).get("simpleText", "")]
        else:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            continue
        result[video_id] = {"source_id": video_id, "url": f"{BASE}/watch?v={video_id}",
                            "listing_title": title, "listing_tab": tab, "listing_page": page,
                            "listing_labels": labels, "listing_duration": duration,
                            "listing_evidence": evidence}
    return list(result.values())


def continuation(data: dict) -> str | None:
    # Only the selected content tab, not unrelated page widgets.
    tree = data
    for node in walk(data.get("contents", {})):
        tab = node.get("tabRenderer", {})
        if tab.get("selected") and "content" in tab:
            tree = tab["content"]
            break
    for node in walk(tree):
        endpoint = node.get("continuationItemRenderer", {}).get("continuationEndpoint", {})
        if endpoint.get("commandMetadata", {}).get("webCommandMetadata", {}).get("apiUrl") == "/youtubei/v1/browse":
            return endpoint.get("continuationCommand", {}).get("token")
    return None


def discover(root: Path, tabs: list[str], pages: int) -> None:
    inventory: dict[str, dict] = {}
    failures = []
    for tab in tabs:
        try:
            url = f"{BASE}/{HANDLE}/{tab}"
            raw, evidence = cached_request(root / "discovery" / f"{tab}-1.html", url)
            html = raw.decode()
            data = embedded(html, "ytInitialData")
            channel = data.get("metadata", {}).get("channelMetadataRenderer", {})
            if channel.get("externalId") != CHANNEL_ID:
                raise ValueError("Official channel identity does not match the pinned channel ID")
            save(root / "channel.json", {"channel_id": CHANNEL_ID, "handle": HANDLE,
                 "title": channel.get("title"), "channel_url": channel.get("channelUrl"),
                 "owner_urls": channel.get("ownerUrls"), "description": channel.get("description"),
                 "evidence": evidence})
            version = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', html)
            if not version:
                raise ValueError("Public page omitted its listing client version")
            for page in range(1, pages + 1):
                rows = listing_entries(data, tab, page, evidence)
                for row in rows:
                    inventory.setdefault(row["source_id"], row)
                print(f"{tab} page {page}: {len(rows)} entries", flush=True)
                token = continuation(data)
                if not token or page == pages:
                    break
                # This endpoint is supplied by the public page. The request only
                # reads the next listing page and does not mutate an account.
                payload = {"context": {"client": {"clientName": "WEB", "clientVersion": version[1],
                                                  "hl": "en", "gl": "US"}}, "continuation": token}
                raw, evidence = cached_request(root / "discovery" / f"{tab}-{page+1}.json",
                    BASE + "/youtubei/v1/browse", data=payload)
                data = json.loads(raw)
        except Exception as exc:
            failures.append({"tab": tab, "retrieved_at": now(), "error_type": type(exc).__name__, "reason": str(exc)})
    save(root / "inventory.json", {"channel_id": CHANNEL_ID, "created_at": now(),
         "entries": list(inventory.values()), "discovery_failures": failures})
    print(f"Inventory: {len(inventory)} unique entries; {len(failures)} discovery failures")


def iso_timestamp(value: str | None) -> str | None:
    if value is None or "T" not in value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def metadata(root: Path, entry: dict) -> dict:
    video_id = entry["source_id"]
    path = root / "metadata" / f"{video_id}.json"
    if path.exists():
        return load(path)
    raw, evidence = cached_request(root / "watch" / f"{video_id}.html", entry["url"])
    player = embedded(raw.decode(), "ytInitialPlayerResponse")
    details = player.get("videoDetails", {})
    micro = player.get("microformat", {}).get("playerMicroformatRenderer", {})
    if details.get("videoId") != video_id or details.get("channelId") != CHANNEL_ID:
        status = player.get("playabilityStatus", {})
        raise ValueError("Watch page did not confirm the selected video and pinned channel; "
                         f"{status.get('status')}: {status.get('reason', 'no reason supplied')}")
    live = micro.get("liveBroadcastDetails", {})
    is_live = bool(details.get("isLiveContent"))
    published = iso_timestamp(micro.get("publishDate"))
    end = iso_timestamp(live.get("endTimestamp"))
    if is_live and not end:
        raise ValueError("Livestream is unfinished or lacks an authoritative end timestamp")
    result = dict(entry, channel_id=CHANNEL_ID, channel=details.get("author"),
        title=details.get("title"), duration_seconds=int(details["lengthSeconds"]),
        microformat_duration_seconds=micro.get("lengthSeconds"),
        published_at=published, publication_precision="timestamp" if published else "date_only",
        publish_date_raw=micro.get("publishDate"), upload_date_raw=micro.get("uploadDate"),
        content_type="completed_livestream" if is_live else "normal_video",
        live_start_at=iso_timestamp(live.get("startTimestamp")), live_end_at=end,
        is_shorts_eligible=micro.get("isShortsEligible"), metadata_evidence=evidence,
        playability_status=player.get("playabilityStatus", {}).get("status"))
    save(path, result)
    return result


def acquire_metadata(root: Path, workers: int) -> None:
    inventory = load(root / "inventory.json")
    results, failures = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(metadata, root, entry): entry for entry in inventory["entries"]}
        for future in as_completed(pending):
            entry = pending[future]
            try:
                item = future.result()
                results.append(item)
                print(f"{item['source_id']} {item['published_at']} {item['content_type']}", flush=True)
            except Exception as exc:
                failure = dict(entry, failed_at=now(), error_type=type(exc).__name__, reason=str(exc))
                failures.append(failure)
                save(root / "metadata-failures" / f"{entry['source_id']}.json", failure)
                print(f"{entry['source_id']} FAILED: {type(exc).__name__}: {exc}", flush=True)
    results.sort(key=lambda row: (row.get("published_at") or "", row["source_id"]))
    save(root / "dated-inventory.json", {"channel_id": CHANNEL_ID, "created_at": now(),
         "entries": results, "metadata_failures": failures,
         "discovery_failures": inventory.get("discovery_failures", [])})
    print(f"Dated inventory: {len(results)} successful; {len(failures)} failed")


def fetch_captions(root: Path, selected: dict, retry_failed: bool) -> dict:
    video_id = selected["source_id"]
    result_path = root / "acquisition" / f"{video_id}.json"
    if result_path.exists():
        existing = load(result_path)
        if existing["status"] == "success" or not retry_failed:
            if existing["status"] == "success":
                for field in ("transcript", "raw_caption"):
                    if digest(Path(existing[field + "_path"]).read_bytes()) != existing[field + "_sha256"]:
                        raise ValueError(f"Cached {field} hash mismatch for {video_id}")
            return existing
    meta = load(root / "metadata" / f"{video_id}.json")
    result = {"source_id": video_id, "url": meta["url"], "channel_id": CHANNEL_ID,
              "title": meta["title"], "published_at": meta["published_at"],
              "duration_seconds": meta["duration_seconds"], "content_type": meta["content_type"],
              "attempted_at": now(), "status": "failed", "metadata_path": str(root / "metadata" / f"{video_id}.json")}
    try:
        if not meta["published_at"]:
            raise ValueError("Exact publication time unavailable; refusing to invent it")
        import requests
        from youtube_transcript_api import YouTubeTranscriptApi

        class TimedSession(requests.Session):
            def request(self, *args, **kwargs):
                kwargs.setdefault("timeout", 40)
                return super().request(*args, **kwargs)

        with TimedSession() as session:
            transcript = YouTubeTranscriptApi(http_client=session).fetch(video_id, languages=["en", "en-US", "en-GB"])
        retrieved = now()
        rows = transcript.to_raw_data()
        segments = [{"id": f"s{i+1}", "start": row["start"], "end": row["start"] + row["duration"], "text": row["text"]}
                    for i, row in enumerate(rows) if row["duration"] > 0 and row["text"].strip()]
        segments.sort(key=lambda row: (row["start"], row["end"]))
        if not segments:
            raise ValueError("Caption provider returned no nonempty timestamped segments")
        raw_path = root / "captions" / f"{video_id}.json"
        canonical_path = root / "transcripts" / f"{video_id}.json"
        envelope = {"source_id": video_id, "url": meta["url"], "channel_id": CHANNEL_ID,
                    "metadata": meta, "retrieved_at": retrieved, "language": transcript.language,
                    "language_code": transcript.language_code, "is_generated": transcript.is_generated,
                    "provider": "youtube-transcript-api", "provider_version": importlib.metadata.version("youtube-transcript-api"),
                    "rows": rows}
        canonical = {"source_id": video_id, "channel": meta["channel"], "url": meta["url"],
                     "published_at": meta["published_at"], "available_at": retrieved,
                     "segments": segments, "kind": "youtube"}
        save(raw_path, envelope)
        save(canonical_path, canonical)
        result.update(status="success", retrieved_at=retrieved, language=transcript.language,
            language_code=transcript.language_code, is_generated=transcript.is_generated,
            caption_segments=len(segments), last_caption_end=segments[-1]["end"],
            raw_caption_path=str(raw_path), transcript_path=str(canonical_path),
            raw_caption_sha256=digest(raw_path.read_bytes()), transcript_sha256=digest(canonical_path.read_bytes()))
    except Exception as exc:
        result.update(error_type=type(exc).__name__, reason=str(exc), failed_at=now())
    if result_path.exists():
        prior = load(result_path)
        save(root / "attempt-history" / f"{video_id}-{digest(encoded(prior))[:12]}.json", prior)
    save(result_path, result)
    return result


def acquire_captions(root: Path, selection_path: Path, workers: int, retry_failed: bool) -> None:
    selection = load(selection_path)
    entries = selection["entries"] if isinstance(selection, dict) else selection
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(fetch_captions, root, item, retry_failed): item for item in entries}
        for future in as_completed(pending):
            result = future.result()
            results.append(result)
            print(f"{result['source_id']} {result['status']} {result.get('caption_segments', result.get('error_type'))}", flush=True)
    results.sort(key=lambda row: (row.get("published_at") or "", row["source_id"]))
    save(root / "acquisition-summary.json", {"channel_id": CHANNEL_ID, "created_at": now(),
         "selection_path": str(selection_path), "selection_sha256": digest(selection_path.read_bytes()),
         "entries": results, "successful": sum(r["status"] == "success" for r in results),
         "failed": sum(r["status"] != "success" for r in results)})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/krown"))
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("discover")
    listing.add_argument("--tabs", nargs="+", choices=["videos", "streams"], default=["videos", "streams"])
    listing.add_argument("--pages", type=int, default=2)
    meta = sub.add_parser("metadata")
    meta.add_argument("--workers", type=int, default=4)
    captions = sub.add_parser("captions")
    captions.add_argument("--selection", type=Path, required=True)
    captions.add_argument("--workers", type=int, default=3)
    captions.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()
    if args.root.resolve() == Path.cwd().resolve() or "data" not in args.root.parts:
        parser.error("Use an ignored data/ directory for third-party material")
    if hasattr(args, "workers") and not 1 <= args.workers <= 6:
        parser.error("workers must be between 1 and 6")
    if args.command == "discover":
        if not 1 <= args.pages <= 10:
            parser.error("pages must be between 1 and 10")
        discover(args.root, args.tabs, args.pages)
    elif args.command == "metadata":
        acquire_metadata(args.root, args.workers)
    else:
        acquire_captions(args.root, args.selection, args.workers, args.retry_failed)


if __name__ == "__main__":
    main()
