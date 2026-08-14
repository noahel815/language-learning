#!/usr/bin/env python3
"""Static QA for generated Japanese Lesson Template V1 files."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTECTED = ROOT / "japanese" / "JP-V1-001.html"
EXPECTED_PROTECTED_SHA256 = "8d1e1933cc73351a8291f9ac00357116828dce54d7aac79ff5c91f811690b7bb"


def sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(paths: list[str]) -> int:
    files = [Path(item).resolve() for item in paths] if paths else sorted((ROOT / "japanese").glob("JP-V1-????-W??-D?.html"))
    failures: list[str] = []
    if len(files) != 7:
        failures.append(f"應有 7 份 lesson，實際 {len(files)} 份")
    if not PROTECTED.exists() or sha256(PROTECTED) != EXPECTED_PROTECTED_SHA256:
        failures.append("JP-V1-001 不存在或 SHA-256 已改變")
    forbidden_value = re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][^'\"]{8,}")
    required = ['<!doctype html>', '<html lang="zh-Hant">', '<meta name="viewport"', ':lang(ja)', '<ruby>', '<rt>', 'id="quiz"', 'Quick Quiz', 'id="output"', 'Output Practice', 'id="feedback"', 'id="resultText"', 'function build()', 'navigator.clipboard', 'localStorage', '@media(max-width:620px)', 'overflow-x:hidden']
    ids: set[str] = set()
    for path in files:
        if not path.exists():
            failures.append(f"檔案不存在：{path}")
            continue
        text = path.read_text(encoding="utf-8")
        lesson_id = path.stem
        if lesson_id == "JP-V1-001":
            failures.append("產生清單不可包含 JP-V1-001")
        if lesson_id in ids:
            failures.append(f"Lesson ID 重複：{lesson_id}")
        ids.add(lesson_id)
        if re.search(r"@@[A-Z0-9_]+@@|PLACEHOLDER:", text):
            failures.append(f"{lesson_id} 有 placeholder 殘留")
        for marker in required:
            if marker not in text:
                failures.append(f"{lesson_id} 缺少：{marker}")
        if forbidden_value.search(text):
            failures.append(f"{lesson_id} 疑似含敏感值")
        if 'width:min(880px,calc(100% - 28px))' not in text or 'max-width:100%' not in text:
            failures.append(f"{lesson_id} 缺少靜態防 overflow 規則")
    if failures:
        print("QA FAILED")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("QA PASSED：7/7 lessons；placeholder、HTML、語系、ruby、互動、敏感值與靜態 mobile CSS 檢查通過；JP-V1-001 hash 未變。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
