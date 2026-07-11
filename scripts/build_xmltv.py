#!/usr/bin/env python3
"""Generate a lightweight XMLTV guide that exactly matches the generated M3U.

The script also ensures every M3U entry has a stable tvg-id and embeds the
XMLTV URL in the #EXTM3U header. Only Python's standard library is required.
"""

from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ATTRIBUTE_RE = re.compile(r'([A-Za-z0-9_-]+)="([^"]*)"')


@dataclass(frozen=True)
class Channel:
    channel_id: str
    name: str
    logo: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--playlist",
        default="output/cn_best.m3u8",
        help="Generated M3U/M3U8 playlist to update.",
    )
    parser.add_argument(
        "--output",
        default="output/cn_dummy.xml",
        help="XMLTV output path.",
    )
    parser.add_argument(
        "--xmltv-url",
        default=(
            "https://raw.githubusercontent.com/cherish9051-cloud/iptv-list/"
            "main/output/cn_dummy.xml"
        ),
        help="Public XMLTV URL embedded into the M3U header.",
    )
    return parser.parse_args()


def parse_attributes(extinf: str) -> dict[str, str]:
    return {key: value for key, value in ATTRIBUTE_RE.findall(extinf)}


def parse_display_name(extinf: str) -> str:
    return extinf.rsplit(",", 1)[1].strip() if "," in extinf else ""


def set_attribute(extinf: str, key: str, value: str) -> str:
    escaped = value.replace('"', "'")
    pattern = re.compile(rf'(?<![A-Za-z0-9_-]){re.escape(key)}="[^"]*"')
    replacement = f'{key}="{escaped}"'
    if pattern.search(extinf):
        return pattern.sub(replacement, extinf, count=1)

    comma = extinf.rfind(",")
    if comma == -1:
        return f"{extinf} {replacement}"
    return f"{extinf[:comma]} {replacement}{extinf[comma:]}"


def update_header(line: str, xmltv_url: str) -> str:
    header = line.strip() if line.strip().startswith("#EXTM3U") else "#EXTM3U"
    header = re.sub(r'\s+(?:url-tvg|x-tvg-url)="[^"]*"', "", header)
    return f'{header} url-tvg="{xmltv_url}" x-tvg-url="{xmltv_url}"'


def normalize_playlist(playlist_path: Path, xmltv_url: str) -> list[Channel]:
    lines = playlist_path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    if not lines or not lines[0].strip().startswith("#EXTM3U"):
        raise RuntimeError(f"Invalid M3U header: {playlist_path}")

    lines[0] = update_header(lines[0], xmltv_url)
    channels: list[Channel] = []
    used_ids: set[str] = set()

    for index, line in enumerate(lines):
        if not line.strip().startswith("#EXTINF:"):
            continue

        attrs = parse_attributes(line)
        name = attrs.get("tvg-name", "").strip() or parse_display_name(line)
        if not name:
            name = f"Channel {len(channels) + 1}"

        base_id = attrs.get("tvg-id", "").strip() or name
        channel_id = base_id
        suffix = 2
        while channel_id in used_ids:
            channel_id = f"{base_id}.{suffix}"
            suffix += 1
        used_ids.add(channel_id)

        lines[index] = set_attribute(line, "tvg-id", channel_id)
        channels.append(
            Channel(
                channel_id=channel_id,
                name=name,
                logo=attrs.get("tvg-logo", "").strip(),
            )
        )

    if not channels:
        raise RuntimeError(f"No #EXTINF entries found in {playlist_path}")

    playlist_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return channels


def build_xmltv(channels: list[Channel], output_path: Path) -> None:
    root = ET.Element(
        "tv",
        {
            "generator-info-name": "cherish9051-cloud/iptv-list",
            "generator-info-url": "https://github.com/cherish9051-cloud/iptv-list",
        },
    )

    for channel in channels:
        channel_element = ET.SubElement(root, "channel", {"id": channel.channel_id})
        display_name = ET.SubElement(channel_element, "display-name", {"lang": "zh"})
        display_name.text = channel.name
        if channel.logo:
            ET.SubElement(channel_element, "icon", {"src": channel.logo})

    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    stop = start + timedelta(days=10)
    start_text = start.strftime("%Y%m%d%H%M%S +0000")
    stop_text = stop.strftime("%Y%m%d%H%M%S +0000")

    for channel in channels:
        programme = ET.SubElement(
            root,
            "programme",
            {
                "start": start_text,
                "stop": stop_text,
                "channel": channel.channel_id,
            },
        )
        title = ET.SubElement(programme, "title", {"lang": "zh"})
        title.text = "暂无节目单"
        description = ET.SubElement(programme, "desc", {"lang": "zh"})
        description.text = "该频道暂未配置真实 EPG，本条目用于 Threadfin 频道映射。"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def main() -> int:
    args = parse_args()
    playlist_path = Path(args.playlist)
    output_path = Path(args.output)

    channels = normalize_playlist(playlist_path, args.xmltv_url)
    build_xmltv(channels, output_path)
    print(f"Built {output_path}: {len(channels)} XMLTV channels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
