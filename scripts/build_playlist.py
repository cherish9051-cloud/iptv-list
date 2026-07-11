#!/usr/bin/env python3
"""Build a deduplicated IPTV playlist from an upstream M3U/M3U8 file.

Selection policy:
1. Normalize equivalent channel names (for example CCTV-1 and CCTV1).
2. Prefer the candidate with the highest advertised resolution.
3. At the same resolution, prefer the lowest response-time value.
4. Keep the earlier upstream entry as the final tie-breaker.

Only Python's standard library is required.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ATTRIBUTE_RE = re.compile(r'([A-Za-z0-9_-]+)="([^"]*)"')
BRACKET_RESOLUTION_RE = re.compile(r"\[(\d{3,4})\]", re.IGNORECASE)
PAREN_RESOLUTION_RE = re.compile(r"\((\d{3,4})\s*[pi]?\)", re.IGNORECASE)
CCTV_4K_RE = re.compile(r"CCTV\s*[-_ ]?\s*4K", re.IGNORECASE)
CCTV_RE = re.compile(r"CCTV\s*[-_ ]?\s*(\d{1,2})\s*(\+)?", re.IGNORECASE)
RESPONSE_TIME_RE = re.compile(r"(\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)


@dataclass(frozen=True)
class Entry:
    index: int
    raw_extinf: str
    display_name: str
    attrs: dict[str, str]
    url: str
    canonical_name: str
    resolution: int
    response_time_ms: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="config/settings.json",
        help="Path to the JSON configuration file.",
    )
    parser.add_argument(
        "--source-file",
        help="Read an already downloaded M3U/M3U8 file instead of source_url.",
    )
    return parser.parse_args()


def load_config(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON configuration: {path}: {exc}") from exc


def download_text(url: str, timeout: int, retries: int) -> str:
    headers = {
        "User-Agent": "iptv-list-builder/1.0 (+https://github.com/cherish9051-cloud/iptv-list)",
        "Accept": "text/plain, application/vnd.apple.mpegurl, */*",
    }
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(attempt * 2)

    raise RuntimeError(f"Failed to download source after {retries} attempts: {url}: {last_error}")


def parse_attributes(extinf: str) -> dict[str, str]:
    return {key: value for key, value in ATTRIBUTE_RE.findall(extinf)}


def parse_display_name(extinf: str) -> str:
    return extinf.rsplit(",", 1)[1].strip() if "," in extinf else ""


def normalize_channel_name(display_name: str, attrs: dict[str, str]) -> str:
    source_name = display_name.strip() or attrs.get("tvg-name", "").strip()
    source_name = source_name.replace("（", "(").replace("）", ")")

    if CCTV_4K_RE.search(source_name):
        return "CCTV4K"

    cctv_match = CCTV_RE.search(source_name)
    if cctv_match:
        number = str(int(cctv_match.group(1)))
        plus = "+" if cctv_match.group(2) else ""
        return f"CCTV{number}{plus}"

    cleaned = re.sub(r"\[[^\]]*\]", "", source_name)
    cleaned = re.sub(r"\(\s*\d{3,4}\s*[pi]?\s*\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_")
    return cleaned or source_name


def normalize_resolution(value: int) -> int:
    # Some sources label 1920x1080 streams as [1920]. Treat that as 1080p.
    if 1800 <= value < 2200:
        return 1080
    if value >= 3000:
        return 2160
    return value


def extract_resolution(display_name: str, attrs: dict[str, str]) -> int:
    candidates: list[int] = []
    tvg_name = attrs.get("tvg-name", "")

    candidates.extend(int(value) for value in BRACKET_RESOLUTION_RE.findall(tvg_name))
    candidates.extend(int(value) for value in PAREN_RESOLUTION_RE.findall(display_name))

    if not candidates:
        explicit = re.search(
            r"(?<!\d)(2160|1080|720|600|576|540|480)\s*[pi]?(?!\d)",
            display_name,
            re.IGNORECASE,
        )
        if explicit:
            candidates.append(int(explicit.group(1)))

    return max((normalize_resolution(value) for value in candidates), default=0)


def extract_response_time(attrs: dict[str, str]) -> float | None:
    raw = attrs.get("response-time", "")
    match = RESPONSE_TIME_RE.search(raw)
    return float(match.group(1)) if match else None


def parse_playlist(text: str) -> list[Entry]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    entries: list[Entry] = []
    index = 0
    line_index = 0

    while line_index < len(lines):
        line = lines[line_index].strip()
        if not line.startswith("#EXTINF:"):
            line_index += 1
            continue

        extinf = line
        url = ""
        cursor = line_index + 1
        while cursor < len(lines):
            candidate = lines[cursor].strip()
            if not candidate:
                cursor += 1
                continue
            if candidate.startswith("#"):
                cursor += 1
                continue
            url = candidate
            break

        if not url:
            line_index += 1
            continue

        attrs = parse_attributes(extinf)
        display_name = parse_display_name(extinf)
        canonical_name = normalize_channel_name(display_name, attrs)
        entries.append(
            Entry(
                index=index,
                raw_extinf=extinf,
                display_name=display_name,
                attrs=attrs,
                url=url,
                canonical_name=canonical_name,
                resolution=extract_resolution(display_name, attrs),
                response_time_ms=extract_response_time(attrs),
            )
        )
        index += 1
        line_index = cursor + 1

    if not entries:
        raise RuntimeError("No #EXTINF entries were found in the upstream playlist")
    return entries


def rank_entry(
    entry: Entry,
    prefer_resolution: bool,
    prefer_response_time: bool,
) -> tuple[float, float, int]:
    resolution_score = -float(entry.resolution) if prefer_resolution else 0.0
    latency = entry.response_time_ms if entry.response_time_ms is not None else float("inf")
    latency_score = latency if prefer_response_time else 0.0
    return (resolution_score, latency_score, entry.index)


def group_entries(entries: Iterable[Entry]) -> OrderedDict[str, list[Entry]]:
    grouped: OrderedDict[str, list[Entry]] = OrderedDict()
    for entry in entries:
        grouped.setdefault(entry.canonical_name, []).append(entry)
    return grouped


def infer_group(channel_name: str) -> str:
    if channel_name.startswith("CCTV"):
        return "体育频道" if channel_name in {"CCTV5", "CCTV5+", "CCTV16"} else "央视频道"
    if channel_name.endswith("卫视"):
        return "卫视频道"
    return "其他频道"


def build_extinf(selected: Entry, candidates: list[Entry]) -> str:
    attrs = dict(selected.attrs)

    # Fill missing metadata from another candidate of the same normalized channel.
    for key in ("tvg-id", "tvg-logo", "group-title"):
        if attrs.get(key):
            continue
        for candidate in candidates:
            if candidate.attrs.get(key):
                attrs[key] = candidate.attrs[key]
                break

    attrs["tvg-name"] = selected.canonical_name
    attrs.setdefault("group-title", infer_group(selected.canonical_name))

    preferred_order = ["tvg-id", "tvg-name", "tvg-logo", "group-title", "response-time"]
    ordered_keys = [key for key in preferred_order if key in attrs]
    ordered_keys.extend(sorted(key for key in attrs if key not in ordered_keys))
    attr_text = " ".join(
        f'{key}="{attrs[key]}"' for key in ordered_keys if attrs[key] != ""
    )
    return f"#EXTINF:-1 {attr_text},{selected.canonical_name}"


def select_entries(
    entries: list[Entry],
    prefer_resolution: bool,
    prefer_response_time: bool,
) -> tuple[list[tuple[Entry, list[Entry]]], list[dict[str, object]]]:
    grouped = group_entries(entries)
    selected_items: list[tuple[Entry, list[Entry]]] = []
    report: list[dict[str, object]] = []

    for canonical_name, candidates in grouped.items():
        selected = min(
            candidates,
            key=lambda item: rank_entry(item, prefer_resolution, prefer_response_time),
        )
        selected_items.append((selected, candidates))
        report.append(
            {
                "channel": canonical_name,
                "candidate_count": len(candidates),
                "selected_original_name": selected.display_name,
                "selected_resolution": selected.resolution or None,
                "selected_response_time_ms": selected.response_time_ms,
                "selected_url": selected.url,
            }
        )

    return selected_items, report


def write_outputs(
    output_path: Path,
    report_path: Path,
    source_url: str,
    selected_items: list[tuple[Entry, list[Entry]]],
    report: list[dict[str, object]],
    source_count: int,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    playlist_lines = [
        "#EXTM3U",
        f"#SOURCE:{source_url}",
        "#GENERATED-BY:cherish9051-cloud/iptv-list",
    ]
    for selected, candidates in selected_items:
        playlist_lines.append(build_extinf(selected, candidates))
        playlist_lines.append(selected.url)

    output_path.write_text("\n".join(playlist_lines) + "\n", encoding="utf-8")

    report_document = {
        "source_url": source_url,
        "source_entry_count": source_count,
        "selected_channel_count": len(selected_items),
        "removed_duplicate_count": source_count - len(selected_items),
        "channels": report,
    }
    report_path.write_text(
        json.dumps(report_document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    config = load_config(config_path)

    source_url = str(config["source_url"])
    output_path = Path(str(config.get("output_file", "output/cn_best.m3u8")))
    report_path = Path(str(config.get("report_file", "output/selection-report.json")))
    timeout = int(config.get("request_timeout_seconds", 30))
    retries = int(config.get("request_retries", 3))
    prefer_resolution = bool(config.get("prefer_higher_resolution", True))
    prefer_response_time = bool(config.get("prefer_lower_response_time", True))

    if args.source_file:
        source_text = Path(args.source_file).read_text(encoding="utf-8")
    else:
        source_text = download_text(source_url, timeout=timeout, retries=retries)

    entries = parse_playlist(source_text)
    selected_items, report = select_entries(
        entries,
        prefer_resolution,
        prefer_response_time,
    )
    write_outputs(
        output_path=output_path,
        report_path=report_path,
        source_url=source_url,
        selected_items=selected_items,
        report=report,
        source_count=len(entries),
    )

    print(
        f"Built {output_path}: {len(entries)} source entries -> "
        f"{len(selected_items)} normalized channels"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
