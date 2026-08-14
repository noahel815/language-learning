# Japanese Weekly Generator V1

## 這是什麼

這個工具把一份含 7 課內容的 JSON，一次套進已 freeze 的 Japanese Lesson Template V1，輸出 7 個可直接放上 GitHub Pages 的 HTML，並更新首頁的「This Week｜本週日文」。它不會修改 `japanese/JP-V1-001.html`。

V1 不會連接模型 API、Notion API 或新聞網站。`sample-weekly-content.json` 內的 7 課均為原創示範；未來可把同一格式的 `weekly-content.json` 改由 ChatGPT、Codex 或 API 準備。

## 平常要做什麼

1. 複製 `sample-weekly-content.json`，改名為 `weekly-content.json`。
2. 更新 7 課日期、主題、短文、單字、句型、題目與輸出練習。
3. 保持每課資料符合 `template-schema.json`，並把 `next-lesson-adjustments.json` 的弱點實際放進題目。
4. 執行 generator；看到 `QA PASSED` 才進行發布。

音調沒有可靠資料時，請使用 `"pitch": null` 與 `"pitchVerified": false`，不要猜音調數字。日文漢字請使用分構詞的 `<ruby>漢字<rt>かな</rt></ruby>`。

## Windows 最簡單執行方式

在 repo 根目錄雙擊：

`run_weekly_japanese.bat`

這會讀取 sample、產生 7 課、更新首頁並執行 QA；預設不 commit、不 push。

PowerShell 一行指令（已安裝 Python 3）：

```powershell
py -3 generator\generate_weekly_japanese.py --content generator\sample-weekly-content.json
```

若電腦的指令名稱是 `python`，把 `py -3` 改成 `python`。

正式使用自己的內容：

```powershell
py -3 generator\generate_weekly_japanese.py --content generator\weekly-content.json
```

## 成功後會產生什麼

- `japanese/JP-V1-YYYY-Www-D1.html` 到 `D7.html`
- `index.html` 的本週 7 課連結
- 終端機顯示 7 個輸出路徑與 QA 結果

重新執行同一週會更新同一週的 7 課；不會覆寫 `JP-V1-001.html`。若要保留已發布週次，請在換週前完成 Git commit。

## QA 檢查範圍

`validate_lessons.py` 會確認：

- 剛好產生 7 份 lesson，且 ID 不重複
- `JP-V1-001.html` SHA-256 維持正式 baseline
- 沒有 placeholder 殘留
- HTML、viewport、`lang="zh-Hant"`、日文字型規則、ruby/rt 存在
- Quick Quiz、Output Practice、localStorage、feedback textarea 與 clipboard fallback 存在
- 沒有疑似 API key、token、secret 的值
- 保留 template 的窄螢幕與防橫向 overflow CSS

這是靜態 QA，不等同於 iPhone Safari 的實機視覺與點擊驗收。發布前若有修改模板或互動程式，仍應另做手機實測；正常每週內容生成不應修改 freeze template。

也可單獨執行 QA：

```powershell
py -3 generator\validate_lessons.py japanese\JP-V1-2026-W34-D1.html japanese\JP-V1-2026-W34-D2.html japanese\JP-V1-2026-W34-D3.html japanese\JP-V1-2026-W34-D4.html japanese\JP-V1-2026-W34-D5.html japanese\JP-V1-2026-W34-D6.html japanese\JP-V1-2026-W34-D7.html
```

## QA 通過後發布 GitHub Pages

先檢查 `git status` 與首頁／7 課內容，再依序執行：

```powershell
git add generator japanese index.html README.md run_weekly_japanese.bat
git commit -m "Add Japanese weekly generator V1"
git push origin main
```

GitHub Pages 會沿用 repo 設定。首頁預期為 `https://noahel815.github.io/language-learning/`，lesson 預期為 `https://noahel815.github.io/language-learning/japanese/<Lesson-ID>.html`。

Generator 另提供 `--publish`，會在 QA 通過後執行相同的 add／commit／push；為避免錯誤內容直接上線，日常預設請不要使用。

## 下一階段：Learning Feedback 與 Notion

V1 只產生教材並保留每課的純文字 Learning Feedback。接 Notion Dashboard 前還需要：定義 Learning Result 結構、把有效答案與測試亂填分開、將批改結果更新到 `next-lesson-adjustments.json`、設計 Notion database 欄位與去重規則，以及建立失敗重試與人工覆核流程。這些都不在 V1 自動執行。
