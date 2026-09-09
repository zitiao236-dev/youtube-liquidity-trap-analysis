#!/usr/bin/env python3
"""Create a compact, local evidence index from an SRT transcript."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TIMING = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> "
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})"
)


def to_seconds(groups: tuple[str, ...]) -> tuple[float, float]:
    values = list(map(int, groups))
    start = values[0] * 3600 + values[1] * 60 + values[2] + values[3] / 1000
    end = values[4] * 3600 + values[5] * 60 + values[6] + values[7] / 1000
    return start, end


def read_srt(path: Path) -> list[dict[str, object]]:
    blocks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig").strip())
    cues = []
    for block in blocks:
        lines = block.splitlines()
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        match = TIMING.fullmatch(lines[timing_index].strip())
        if not match:
            continue
        start, end = to_seconds(match.groups())
        text = " ".join(lines[timing_index + 1 :]).strip()
        if text:
            cues.append({"start": start, "end": end, "text": text})
    return cues


def stamp(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def main() -> int:
    parser = argparse.ArgumentParser(description="从 SRT 生成关键词证据索引。")
    parser.add_argument("srt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--keywords",
        default="liquidity,trap,stop loss,target,risk-to-reward,strict rule,partial,news",
        help="逗号分隔，不区分大小写",
    )
    args = parser.parse_args()
    cues = read_srt(args.srt)
    if not cues:
        raise SystemExit("错误：没有解析到字幕 cue")
    keywords = [word.strip() for word in args.keywords.split(",") if word.strip()]
    hits: dict[str, list[dict[str, object]]] = {}
    for keyword in keywords:
        matches = [cue for cue in cues if keyword.casefold() in str(cue["text"]).casefold()]
        hits[keyword] = [
            {"timestamp": stamp(float(cue["start"])), "text": cue["text"]}
            for cue in matches
        ]
    payload = {
        "source": str(args.srt),
        "cue_count": len(cues),
        "first_timestamp": stamp(float(cues[0]["start"])),
        "last_timestamp": stamp(float(cues[-1]["end"])),
        "keyword_hits": hits,
        "notice": "This local index may contain transcript excerpts; keep it under data/transcripts/.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: {len(cues)} cues; index written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

