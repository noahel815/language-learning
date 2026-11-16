"""Validate english/puzzles.js. Usage: python3 english/validate_puzzles.py"""
import json, re, sys
from pathlib import Path

MAX_STOCK = 30
WINDOW = 20  # 同一個字，在最近 20 題內不可重複出現
LEVELS = {"一般", "偏難"}
# 虛詞不算「考過的字」（不然句子寫不出來）
STOPWORDS = set("A AN THE IT ITS SO IS ARE WAS AND OR BUT TO OF IN ON AT BY FOR WITH FROM AS IF THAT THIS YOU YOUR WE OUR MY ME BE CAN DO NOT NO".split())
HISTORY = Path(__file__).parent / "history.json"


def words_of(q):
    ws = [w for w in q["quote"].split()] + [c[0] for c in q["clues"]]
    return [w for w in ws if len(w) >= 3 and w not in STOPWORDS]
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
# ---- 字詞不重複檢查（history.json 記錄每題用過的字，含已從庫存刪掉的題）----
hist = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else {"puzzles": []}
entries = hist["puzzles"]
if "--sync" in sys.argv:
    have = {e["id"] for e in entries}
    for q in data:
        if q["id"] not in have:
            entries.append({"id": q["id"], "words": sorted(set(words_of(q)))})
    HISTORY.write_text(json.dumps(hist, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
by_id = {e["id"]: e for e in entries}
for q in data:
    e = by_id.get(q["id"])
    if not e:
        errs.append(f"{q['id']} 不在 history.json，請執行 python3 english/validate_puzzles.py --sync")
    elif set(e["words"]) != set(words_of(q)):
        errs.append(f"{q['id']} 與 history.json 的字不一致")
for i, e in enumerate(entries):
    if e.get("exempt"): continue
    seen_words = {}
    for prev in entries[max(0, i - WINDOW):i]:
        for w in prev["words"]: seen_words[w] = prev["id"]
    dup = sorted(w for w in e["words"] if w in seen_words)
    if dup: errs.append(f"{e['id']} 的字在最近 {WINDOW} 題內重複：" + ", ".join(f"{w}（{seen_words[w]}）" for w in dup))
for q in data:
    ws = words_of(q)
    dup_in = sorted({w for w in ws if ws.count(w) > 1})
    if dup_in and not by_id.get(q["id"], {}).get("exempt"): errs.append(f"{q['id']} 同一題內字重複：{dup_in}")
if errs:
    print("FAILED"); [print(" -", e) for e in errs]; sys.exit(1)
print(f"OK：{len(data)} 題（上限 {MAX_STOCK}）")
