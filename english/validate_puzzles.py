"""Validate english/puzzles.js. Usage: python3 english/validate_puzzles.py"""
import json, re, sys
from pathlib import Path

MAX_STOCK = 10
LEVELS = {"一般", "偏難"}
raw = (Path(__file__).parent / "puzzles.js").read_text(encoding="utf-8")
m = re.search(r"window\.PUZZLES_DATA\s*=\s*(\[.*\])\s*;?\s*$", raw, re.S)
if not m:
    sys.exit("puzzles.js 格式錯誤：必須是 window.PUZZLES_DATA = [...] 的純 JSON 陣列")
data = json.loads(m.group(1))
errs = []
if not 1 <= len(data) <= MAX_STOCK:
    errs.append(f"庫存必須 1–{MAX_STOCK} 題，目前 {len(data)} 題")
seen = set()
for q in data:
    i = q.get("id", "?")
    if i in seen: errs.append(f"{i} id 重複")
    seen.add(i)
    for k in ("name", "level", "theme", "quote", "quoteZh", "note", "clues", "added"):
        if not q.get(k): errs.append(f"{i} 缺少 {k}")
    if q.get("level") not in LEVELS: errs.append(f"{i} level 必須是 {sorted(LEVELS)}")
    quote = q.get("quote", "")
    if not re.fullmatch(r"[A-Z]+( [A-Z]+)*", quote): errs.append(f"{i} quote 只能有大寫英文字母與單一空格")
    cl = q.get("clues", [])
    if not 5 <= len(cl) <= 6: errs.append(f"{i} 提示字必須 5–6 個")
    letters = set(quote.replace(" ", ""))
    outside = set()
    for c in cl:
        if len(c) != 3 or not all(isinstance(x, str) and x.strip() for x in c): errs.append(f"{i} 提示格式必須是 [答案, 英文提示, 中文意思]"); continue
        if not re.fullmatch(r"[A-Z]{3,}", c[0]): errs.append(f"{i} 答案 {c[0]} 必須是 3 個以上大寫字母")
        outside |= set(c[0]) - letters
    if q.get("level") == "一般" and outside: errs.append(f"{i} 一般難度的提示字不可用句子以外的字母：{sorted(outside)}")
    if q.get("level") == "偏難" and len(outside) < 3: errs.append(f"{i} 偏難至少要有 3 個只出現在提示字的字母，目前 {len(outside)}")
    if len(letters | outside) > 26: errs.append(f"{i} 字母超過 26")
    blob = json.dumps(q, ensure_ascii=False)
    if re.search(r"@|https?:|gmail", blob, re.I): errs.append(f"{i} 內容不可含信箱或網址")
if errs:
    print("FAILED"); [print(" -", e) for e in errs]; sys.exit(1)
print(f"OK：{len(data)} 題（上限 {MAX_STOCK}）")
