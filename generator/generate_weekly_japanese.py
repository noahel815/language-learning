#!/usr/bin/env python3
"""Generate a seven-lesson Japanese week from the frozen V1 template."""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "generator"
TEMPLATE = ROOT / "templates" / "japanese-lesson-v1.html"
SCHEMA = GENERATOR / "template-schema.json"
ADJUSTMENTS = GENERATOR / "next-lesson-adjustments.json"
OUTPUT_DIR = ROOT / "japanese"
PROTECTED_SAMPLE = OUTPUT_DIR / "JP-V1-001.html"
TOKEN_RE = re.compile(r"@@[A-Z0-9_]+@@")


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_week(data: dict, schema: dict, adjustments: dict) -> list[dict]:
    require(data.get("templateVersion") == schema["properties"]["templateVersion"]["const"], "templateVersion 不符")
    lessons = data.get("lessons")
    require(isinstance(lessons, list) and len(lessons) == 7, "weekly content 必須剛好有 7 課")
    required = schema["required"]
    lesson_required = schema["properties"]["lesson"]["required"]
    id_pattern = re.compile(schema["properties"]["lesson"]["properties"]["id"]["pattern"])
    seen: set[str] = set()
    for number, lesson in enumerate(lessons, 1):
        missing = [key for key in required if key not in lesson]
        require(not missing, f"第 {number} 課缺少欄位：{', '.join(missing)}")
        missing_meta = [key for key in lesson_required if key not in lesson["lesson"]]
        require(not missing_meta, f"第 {number} 課 lesson 缺少欄位：{', '.join(missing_meta)}")
        lesson_id = lesson["lesson"]["id"]
        require(id_pattern.fullmatch(lesson_id) is not None, f"Lesson ID 不符 schema：{lesson_id}")
        require(lesson_id != "JP-V1-001", "禁止覆寫 JP-V1-001")
        require(lesson_id not in seen, f"Lesson ID 重複：{lesson_id}")
        seen.add(lesson_id)
        date.fromisoformat(lesson["lesson"]["date"])
        require(len(lesson["usefulSentences"]) == 10, f"{lesson_id} 必須有 10 句實用句")
        require(lesson["reading"].get("japaneseHtml") and "<ruby>" in lesson["reading"]["japaneseHtml"], f"{lesson_id} Reading 缺少 ruby")
        require(lesson["quiz"], f"{lesson_id} Quick Quiz 不可為空")
        require(lesson["outputPractice"].get("promptZh"), f"{lesson_id} Output Practice 不可為空")

    serialized = json.dumps(data, ensure_ascii=False)
    expected = {item["target"] for item in adjustments.get("nextLessonAdjustments", [])}
    require("〜を踏まえて" in serialized and ("造句" in serialized or "寫一句" in serialized), "未落實 〜を踏まえて Production")
    require(serialized.count("〜ように") >= 3, "〜ように 必須在不同練習情境出現至少 3 次")
    require("〜に伴って" in serialized, "未安排 〜に伴って review")
    require("自由" in serialized or "自己的" in serialized, "未安排短篇自由輸出")
    require({"〜を踏まえて", "〜ように", "〜に伴って", "free_production"}.issubset(expected), "調整檔缺少 V1 必要學習訊號")
    return lessons


def pitch(item: dict) -> str:
    return html.escape(item.get("pitch") or "") if item.get("pitchVerified") else ""


def dict_item(item: dict) -> str:
    if item.get("components"):
        units = []
        for component in item["components"]:
            tone = f'<span class="pitch">{pitch(component)}</span>' if pitch(component) else ""
            units.append(f'<span class="dict-unit">{tone}<span class="bracket">【{html.escape(component["surface"])}】</span><span class="kana">{html.escape(component["reading"])}</span></span>')
        entry = '<span class="compose">＋</span>'.join(units) + f'<span class="whole">→ {html.escape(item["surface"])}</span>'
    else:
        tone = f'<span class="pitch">{pitch(item)}</span>' if pitch(item) else ""
        entry = f'{tone}<span class="bracket">【{html.escape(item["surface"])}】</span><span class="kana">{html.escape(item["reading"])}</span>'
    return f'<div class="vocab"><span class="dict-entry" lang="ja">{entry}</span><span class="meaning" lang="zh-Hant">{html.escape(item["meaningZh"])}</span></div>'


def pronunciation_item(item: dict) -> str:
    parts = item.get("components") or [item]
    rendered = []
    for part in parts:
        tone = f'<span class="pitch">{pitch(part)}</span>' if pitch(part) else ""
        rendered.append(f'{tone}<span class="kanji">【{html.escape(part["surface"])}】</span><span class="kana">{html.escape(part["reading"])}</span>')
    return '<span class="pron">' + '<span class="compose">＋</span>'.join(rendered) + '</span>'


def replace_section(document: str, section_id: str, inner: str) -> str:
    pattern = re.compile(rf'(<section id="{re.escape(section_id)}">).*?(</section>)', re.DOTALL)
    updated, count = pattern.subn(rf'\1\n{inner}\n    \2', document, count=1)
    require(count == 1, f"模板找不到 section #{section_id}")
    return updated


def render_reading(data: dict) -> str:
    reading = data["reading"]
    pron = "".join(pronunciation_item(item) for item in reading["pronunciation"])
    vocab = "".join(dict_item(item) for item in reading["readingVocabulary"])
    return f'''      <span class="kicker">01 · Reading First</span><h2>先讀完，再查單字</h2>
      <p class="lead">{html.escape(reading["leadZh"])}</p>
      <div class="card reading"><p class="jp" lang="ja">{reading["japaneseHtml"]}</p><p class="translation" lang="zh-Hant">{html.escape(reading["translationZh"])}</p></div>
      <div class="pronunciation" lang="ja" aria-label="短文關鍵詞讀音">{pron}</div>
      <p class="pron-note">只在資料明確標示已確認時顯示音調；未確認者不標數字。</p>
      <div class="vocab-grid" aria-label="閱讀詞彙">{vocab}</div>'''


def render_sentences(data: dict) -> str:
    rows = []
    for index, item in enumerate(data["usefulSentences"], 1):
        rows.append(f'<div class="sentence"><span class="num">{index:02d}</span><p class="jp" lang="ja">{item["japaneseHtml"]}</p><p class="zh" lang="zh-Hant">{html.escape(item["translationZh"])}</p></div>')
    return '      <span class="kicker">02 · Useful Sentences</span><h2>10 句實用句</h2>\n      ' + "\n      ".join(rows)


def render_grammar(data: dict) -> str:
    cards = []
    for item in data["patterns"]:
        cards.append(f'<article class="card grammar"><h3>{html.escape(item["name"])}</h3><p class="pattern" lang="ja">{html.escape(item["formation"])}</p><p>{html.escape(item["explanationZh"])}</p><p class="example" lang="ja">{item["example"]["japaneseHtml"]}</p><p class="note">{html.escape(item["example"]["translationZh"])}</p></article>')
    return f'      <span class="kicker">03 · Key Patterns</span><h2>重點句型</h2><div class="grammar-grid">{"".join(cards)}</div>'


def render_quiz(data: dict) -> str:
    questions = []
    for item in data["quiz"]:
        qid = item["id"]
        if item["type"] == "singleChoice":
            controls = "".join(f'<label class="choice"><input type="radio" name="{qid}" value="{html.escape(choice["value"], quote=True)}">{choice["labelHtml"]}</label>' for choice in item.get("choices", []))
        elif item["type"] == "text":
            controls = f'<input type="text" id="{qid}" autocomplete="off" placeholder="請用日文填答">'
        else:
            controls = f'<textarea id="{qid}" placeholder="請輸入答案"></textarea>'
        questions.append(f'<div class="question"><p><strong>{qid.upper()}.</strong> {item["promptZh"]}</p>{controls}</div>')
    return f'      <span class="kicker">05 · Quick Quiz</span><h2>快速練習</h2><div class="card"><fieldset>{"".join(questions)}</fieldset></div>'


def render_feedback(data: dict) -> str:
    weakness = "".join(f'<label class="weak"><input type="checkbox" name="weak" value="{html.escape(item, quote=True)}">{html.escape(item)}</label>' for item in data["weaknessRecovery"])
    return f'''      <span class="kicker">08 · Feedback</span><h2>自評與回傳 ChatGPT</h2><div class="card">
      <h3>今天的難度</h3><div class="difficulty" role="radiogroup" aria-label="自評難度">{''.join(f'<label><input type="radio" name="difficulty" value="{i}"><span>{i}</span></label>' for i in range(1,6))}</div><p class="note">1＝太簡單；5＝很吃力</p>
      <h3>標記不熟內容</h3><div class="weak-list">{weakness}</div><label for="weakOther"><strong>其他不熟或想複習的內容</strong></label><input type="text" id="weakOther" placeholder="自由填寫">
      <div class="actions"><button class="btn primary" id="prepare" type="button">產生給 ChatGPT 的回饋文字</button><button class="btn secondary" id="clear" type="button">清除本課填答</button></div><p class="status" id="status" aria-live="polite"></p>
      <div class="result" id="result"><label for="resultText"><strong>給 ChatGPT 的純文字回饋</strong></label><textarea id="resultText" readonly spellcheck="false" aria-describedby="status"></textarea><div class="actions"><button class="btn secondary compact" id="copyAgain" type="button">嘗試一鍵複製</button></div></div></div>'''


def render_lesson(template: str, data: dict) -> str:
    meta = data["lesson"]
    tokens = {"LESSON_ID": meta["id"], "LESSON_DATE": meta["date"], "TOPIC_JA": meta["topicJa"], "TOPIC_ZH": meta["topicZh"], "LESSON_SUMMARY_ZH": meta["summaryZh"], "JLPT_LEVEL": meta["jlptLevel"], "DURATION": meta["duration"], "DOMAIN": meta["domain"], "REVIEW_PATTERN": data["previousReview"]["pattern"]}
    document = template
    for key, value in tokens.items():
        document = document.replace(f"@@{key}@@", html.escape(str(value), quote=True))
    document = replace_section(document, "reading", render_reading(data))
    document = replace_section(document, "sentences", render_sentences(data))
    document = replace_section(document, "grammar", render_grammar(data))
    document = replace_section(document, "vocabulary", f'      <span class="kicker">04 · Vocabulary</span><h2>本課單字</h2><div class="vocab-grid">{"".join(dict_item(item) for item in data["vocabulary"])}</div>')
    document = replace_section(document, "quiz", render_quiz(data))
    output = data["outputPractice"]
    document = replace_section(document, "output", f'      <span class="kicker">06 · Output Practice</span><h2>輸出練習</h2><div class="card output"><p>{html.escape(output["promptZh"])}</p><p class="note" lang="ja">例：{output["exampleJaHtml"]}</p><textarea id="outputText" maxlength="{output["maxLength"]}" placeholder="請用日文作答"></textarea><div class="counter"><span id="count">0</span> / {output["maxLength"]}</div></div>')
    review = data["previousReview"]
    document = replace_section(document, "review", f'      <span class="kicker">07 · Previous Review</span><h2>前課複習區</h2><div class="card review"><details><summary>展開 2 分鐘複習｜{html.escape(review["pattern"])}</summary><p>{html.escape(review["explanationZh"])}</p><p lang="ja">{review["exampleJaHtml"]}</p><label for="reviewAnswer"><strong>小題：</strong>{html.escape(review["promptZh"])}</label><textarea id="reviewAnswer" placeholder="請輸入日文句子"></textarea></details></div>')
    document = replace_section(document, "feedback", render_feedback(data))
    ids = [question["id"] for question in data["quiz"] if question["type"] != "singleChoice"]
    document = re.sub(r"const ids=\[[^;]*;", "const ids=" + json.dumps(ids + ["outputText", "reviewAnswer", "weakOther"], ensure_ascii=False) + ";", document)
    document = document.replace("Q1: ${value('q1')}\nQ2: ${text('q2')}\nQ3: ${text('q3')}\nQ4: ${text('q4')}", "Q1: ${value('q1')}\\nQ2: ${text('q2')}\\nQ3: ${text('q3')}\\nQ4: ${text('q4')}")
    require(TOKEN_RE.search(document) is None, f"{meta['id']} 尚有 placeholder")
    return document


def update_index(lessons: list[dict]) -> None:
    path = ROOT / "index.html"
    document = path.read_text(encoding="utf-8")
    links = "\n".join(f'      <a class="lesson" href="japanese/{item["lesson"]["id"]}.html"><span>{html.escape(item["lesson"]["date"])} · {html.escape(item["lesson"]["topicZh"])}</span><small>{html.escape(item["lesson"]["id"])} · {html.escape(item["lesson"]["jlptLevel"])}</small></a>' for item in lessons)
    block = f'    <section id="this-week"><h2>This Week｜本週日文</h2><div class="lessons">\n{links}\n    </div></section>'
    if '<section id="this-week">' in document:
        document = re.sub(r'    <section id="this-week">.*?</section>', block, document, flags=re.DOTALL)
    else:
        document = document.replace("  </main>", block + "\n  </main>")
    path.write_text(document, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Japanese Weekly Lesson V1")
    parser.add_argument("--content", type=Path, default=GENERATOR / "sample-weekly-content.json")
    parser.add_argument("--publish", action="store_true", help="QA 後 commit 並 push；預設不發布")
    args = parser.parse_args()
    protected_before = PROTECTED_SAMPLE.read_bytes()
    lessons = validate_week(load_json(args.content), load_json(SCHEMA), load_json(ADJUSTMENTS))
    template = TEMPLATE.read_text(encoding="utf-8")
    written = []
    for lesson in lessons:
        output = OUTPUT_DIR / f'{lesson["lesson"]["id"]}.html'
        output.write_text(render_lesson(template, lesson), encoding="utf-8", newline="\n")
        written.append(output)
    update_index(lessons)
    require(PROTECTED_SAMPLE.read_bytes() == protected_before, "JP-V1-001 內容遭到變更")
    print(f"已產生 {len(written)} 課：")
    for path in written:
        print(f"  - {path.relative_to(ROOT)}")
    validation = subprocess.run([sys.executable, str(GENERATOR / "validate_lessons.py"), *map(str, written)], cwd=ROOT)
    require(validation.returncode == 0, "QA 未通過，不會發布")
    if args.publish:
        subprocess.run(["git", "add", "generator", "japanese", "index.html", "README.md", "run_weekly_japanese.bat"], cwd=ROOT, check=True)
        subprocess.run(["git", "commit", "-m", "Add Japanese weekly generator V1"], cwd=ROOT, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
    else:
        print("QA 通過。預設未執行 git push；發布方式請見 generator/README.md。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        raise SystemExit(1)
