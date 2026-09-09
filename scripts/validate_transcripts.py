#!/usr/bin/env python3
"""Basic SRT integrity checks used by this project."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

TIMING = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> "
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})$"
)


def seconds(parts: tuple[str, ...]) -> float:
    h, m, s, ms = map(int, parts)
    return h * 3600 + m * 60 + s + ms / 1000


def validate(path: Path) -> tuple[int, float]:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"文件缺失或为空：{path}")
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    cues = 0
    previous_start = -1.0
    last_end = 0.0
    for line_no, line in enumerate(lines, 1):
        if "-->" not in line:
            continue
        match = TIMING.fullmatch(line.strip())
        if not match:
            raise ValueError(f"第 {line_no} 行时间戳格式无效：{line}")
        start = seconds(match.groups()[:4])
        end = seconds(match.groups()[4:])
        if end <= start:
            raise ValueError(f"第 {line_no} 行结束时间不晚于开始时间")
        if start < previous_start:
            raise ValueError(f"第 {line_no} 行开始时间逆序")
        previous_start = start
        last_end = end
        cues += 1
    if not cues:
        raise ValueError(f"没有字幕 cue：{path}")
    return cues, last_end


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.paths:
        cues, last_end = validate(path)
        print(f"PASS {path}: {cues} cues, last_end={last_end:.3f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

