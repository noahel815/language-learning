#!/usr/bin/env python3
"""Release QA for the 2026-09-01 through 2026-09-15 extension."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / "generator" / name for name in (
    "weekly-content-2026-W36.json", "weekly-content-2026-W37.json", "weekly-content-2026-W38-partial.json")]
EXPECTED = [(date(2026, 9, 1), "JP-V1-2026-W36-D2"), *
            [(date(2026, 9, day), f"JP-V1-2026-W37-D{day - 6}") for day in range(7, 14)],
            (date(2026, 9, 14), "JP-V1-2026-W38-D1"), (date(2026, 9, 15), "JP-V1-2026-W38-D2")]
EXPECTED = [(date(2026, 9, day), f"JP-V1-2026-W36-D{day + 1}") for day in range(1, 7)] + EXPECTED[1:]
ALLOWED = {"threads", "google_trends", "nikkei", "travel", "review"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> int:
    failures: list[str] = []
    lessons = []
    for path in FILES:
        lessons.extend(json.loads(path.read_text(encoding="utf-8"))["lessons"])
    selected = [item for item in lessons if "2026-09-01" <= item["lesson"]["date"] <= "2026-09-15"]
    pairs = [(date.fromisoformat(item["lesson"]["date"]), item["lesson"]["id"]) for item in selected]
    if pairs != EXPECTED:
        failures.append("Lesson ID／日期／ISO 週次順序不符")
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    node = shutil.which("node") or str(Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe")
    for item in selected:
        meta = item["lesson"]
        if meta.get("trendSource") not in ALLOWED:
            failures.append(f'{meta["id"]} trendSource 不符')
        if len(item["usefulSentences"]) != 10:
            failures.append(f'{meta["id"]} Useful Sentences 不是 10 句')
        path = ROOT / "japanese" / f'{meta["id"]}.html'
        text = path.read_text(encoding="utf-8")
        ruby_count, rt_count = text.count("<ruby>"), text.count("<rt>")
        if not ruby_count or ruby_count != rt_count:
            failures.append(f'{meta["id"]} ruby/rt 不成對')
        if f'<meta name="trend-source" content="{meta["trendSource"]}">' not in text:
            failures.append(f'{meta["id"]} HTML metadata 不符')
        if f'href="japanese/{meta["id"]}.html"' not in index:
            failures.append(f'{meta["id"]} 首頁連結缺少')
        if re.search(r"@@[A-Z0-9_]+@@|PLACEHOLDER:", text):
            failures.append(f'{meta["id"]} 有 placeholder')
        scripts = re.findall(r"<script>(.*?)</script>", text, flags=re.S)
        if not scripts:
            failures.append(f'{meta["id"]} 缺少 JavaScript')
        else:
            result = subprocess.run([node, "--check", "-"], input="\n".join(scripts).encode("utf-8"),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode:
                failures.append(f'{meta["id"]} JavaScript 語法錯誤')
    if digest(ROOT / "japanese/JP-V1-001.html") != "8D1E1933CC73351A8291F9AC00357116828DCE54D7AAC79FF5C91F811690B7BB":
        failures.append("JP-V1-001 hash 改變")
    if digest(ROOT / "templates/japanese-lesson-v1.html") != "A1834EC71C27BE73FF95652A89B1BF065A28D3CEC16F3628B136DD77D008BF92":
        failures.append("frozen template hash 改變")
    if failures:
        print("MID-SEPTEMBER QA FAILED")
        print("\n".join(f"- {item}" for item in failures))
        return 1
    print("MID-SEPTEMBER QA PASSED: 15/15 dates, ISO IDs, source metadata, 10 sentences, ruby/rt, placeholders, JS syntax, index links, and frozen hashes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
