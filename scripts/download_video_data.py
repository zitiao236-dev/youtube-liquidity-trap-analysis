#!/usr/bin/env python3
"""Download public YouTube metadata and subtitle tracks without media files."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


DEFAULT_LANGUAGES = ["en", "en-US", "en-GB"]
DEFAULT_ZH_LANGUAGES = ["zh-CN", "zh-Hans", "zh", "zh-TW"]
TIMING_RE = re.compile(
    r"^(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="获取 YouTube 元数据与字幕（不下载音视频）。"
    )
    parser.add_argument("url", help="YouTube 视频 URL")
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument(
        "--languages",
        default=",".join(DEFAULT_LANGUAGES),
        help="原文字幕语言优先级，逗号分隔（默认 en,en-US,en-GB）",
    )
    parser.add_argument(
        "--zh-languages",
        default=",".join(DEFAULT_ZH_LANGUAGES),
        help="中文字幕语言优先级，逗号分隔",
    )
    parser.add_argument(
        "--prefer-auto",
        action="store_true",
        help="优先自动字幕；默认优先人工字幕",
    )
    return parser.parse_args()


def choose_track(
    info: dict[str, Any], priorities: list[str], prefer_auto: bool
) -> tuple[str, str, dict[str, Any]] | None:
    pools = [
        ("automatic", info.get("automatic_captions") or {}),
        ("manual", info.get("subtitles") or {}),
    ]
    if not prefer_auto:
        pools.reverse()
    for source_type, pool in pools:
        for language in priorities:
            entries = pool.get(language)
            if not entries:
                continue
            preferred = next((entry for entry in entries if entry.get("ext") == "srt"), None)
            preferred = preferred or next(
                (entry for entry in entries if entry.get("ext") == "vtt"), None
            )
            if preferred:
                return source_type, language, preferred
    return None


def fetch_text(entry: dict[str, Any]) -> str:
    response = requests.get(
        entry["url"],
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=45,
    )
    response.raise_for_status()
    if not response.content:
        raise RuntimeError("字幕服务器返回空内容")
    response.encoding = "utf-8"
    return response.text.lstrip("\ufeff")


def parse_timestamp(value: str) -> float:
    hours, minutes, seconds = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def fmt_timestamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def normalize_srt(raw: str) -> tuple[str, list[dict[str, Any]]]:
    """Normalize either SRT or VTT into SRT and return parsed cues."""
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cues: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        match = TIMING_RE.match(lines[index].strip())
        if not match:
            index += 1
            continue
        start = parse_timestamp(match.group("start"))
        end = parse_timestamp(match.group("end"))
        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            cleaned = html.unescape(TAG_RE.sub("", lines[index])).strip()
            if cleaned and not cleaned.startswith(("NOTE", "Kind:", "Language:")):
                text_lines.append(cleaned)
            index += 1
        text = " ".join(text_lines).strip()
        if text and end > start:
            cues.append({"start": start, "end": end, "text": text})
        index += 1
    if not cues:
        raise ValueError("未能从字幕响应中解析出有效时间轴")
    blocks = []
    for number, cue in enumerate(cues, 1):
        blocks.append(
            f"{number}\n{fmt_timestamp(cue['start'])} --> {fmt_timestamp(cue['end'])}\n"
            f"{cue['text']}"
        )
    return "\n\n".join(blocks) + "\n", cues


def write_plain_text(cues: list[dict[str, Any]], path: Path, timestamped: bool) -> None:
    rows = []
    for cue in cues:
        text = cue["text"]
        if rows and rows[-1].endswith(text):
            continue
        if timestamped:
            stamp = fmt_timestamp(cue["start"]).split(",", 1)[0]
            rows.append(f"[{stamp}] {text}")
        else:
            rows.append(text)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def public_metadata(info: dict[str, Any], tracks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "video_id": info.get("id"),
        "title": info.get("title"),
        "author": info.get("channel") or info.get("uploader"),
        "channel_url": info.get("channel_url") or info.get("uploader_url"),
        "upload_date": info.get("upload_date"),
        "duration_seconds": info.get("duration"),
        "duration_string": info.get("duration_string"),
        "original_url": info.get("webpage_url") or info.get("original_url"),
        "description": info.get("description"),
        "available_manual_subtitle_languages": sorted((info.get("subtitles") or {}).keys()),
        "available_auto_subtitle_languages": sorted(
            (info.get("automatic_captions") or {}).keys()
        ),
        "downloaded_tracks": tracks,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "notes": [
            "manual/automatic 分类直接来自 yt-dlp 对 YouTube 字幕清单的解析。",
            "manual 分类不能单独证明字幕由作者本人制作或经过人工校对。",
            "未下载视频或音频。完整字幕文件仅供本地研究，并由 .gitignore 排除。",
        ],
    }


def download_track(
    info: dict[str, Any], priorities: list[str], prefer_auto: bool, stem: str, out: Path
) -> dict[str, Any] | None:
    selected = choose_track(info, priorities, prefer_auto)
    if not selected:
        return None
    source_type, language, entry = selected
    raw = fetch_text(entry)
    srt, cues = normalize_srt(raw)
    (out / f"{stem}.srt").write_text(srt, encoding="utf-8")
    write_plain_text(cues, out / f"{stem}.txt", timestamped=(stem == "zh"))
    return {
        "file_stem": stem,
        "language": language,
        "source_type": source_type,
        "format_received": entry.get("ext"),
        "cue_count": len(cues),
        "first_timestamp_seconds": cues[0]["start"],
        "last_timestamp_seconds": cues[-1]["end"],
    }


def main() -> int:
    args = parse_args()
    output = args.output_dir.resolve()
    transcripts = output / "transcripts"
    transcripts.mkdir(parents=True, exist_ok=True)
    options = {"quiet": True, "skip_download": True, "noplaylist": True}
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(args.url, download=False)
        tracks: list[dict[str, Any]] = []
        original = download_track(
            info,
            [x.strip() for x in args.languages.split(",") if x.strip()],
            args.prefer_auto,
            "original",
            transcripts,
        )
        if not original:
            raise RuntimeError("未找到符合原文语言优先级的人工或自动字幕")
        tracks.append(original)
        chinese = download_track(
            info,
            [x.strip() for x in args.zh_languages.split(",") if x.strip()],
            args.prefer_auto,
            "zh",
            transcripts,
        )
        if chinese:
            tracks.append(chinese)
        else:
            print("警告：没有可下载的中文字幕轨道；未生成 zh 文件。", file=sys.stderr)
        metadata = public_metadata(info, tracks)
        output.mkdir(parents=True, exist_ok=True)
        (output / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except (DownloadError, requests.RequestException, RuntimeError, ValueError) as exc:
        print(f"错误：无法获取视频数据：{exc}", file=sys.stderr)
        return 1
    print(f"已写入元数据：{output / 'metadata.json'}")
    for track in tracks:
        print(
            f"已写入 {track['file_stem']}：{track['language']} / "
            f"{track['source_type']} / {track['cue_count']} cues"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

