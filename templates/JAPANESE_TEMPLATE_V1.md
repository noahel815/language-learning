# Japanese Lesson Template V1

狀態：**Frozen / Approved Template**

驗收母版：`japanese/JP-V1-001.html`

可重複使用模板：`templates/japanese-lesson-v1.html`

## 不可變更的硬性規格

1. 保持單一、自包含 HTML；不得破壞既有 GitHub Pages sample URL。
2. 手機優先且閱讀舒適：維持 viewport、單欄窄螢幕配置、可橫向捲動的 sticky 導覽、觸控友善表單與無橫向溢位。
3. 中文與日文字型分流：繁中使用 `PingFang TC`／`Noto Sans TC`／`Microsoft JhengHei`；日文、ruby、讀音與句型使用 `Hiragino Sans`／`Yu Gothic`／`YuGothic`／`Noto Sans JP`。
4. 正文的 ruby 必須依每個可理解構詞單位分開，不把可拆解的複合詞包成一個 ruby。例如「共用空間」應分成 `<ruby>共用…</ruby><ruby>空間…</ruby>`。
5. 單字與讀音採大辭林式呈現，例如 `①③【会議】かいぎ`。複合詞分列構成詞並以 `＋` 顯示；整詞音調未由可信資料確認時，只顯示讀音，不得由構成詞推測或杜撰。
6. 難度核心為 JLPT N3 → N2，可視學習狀態回收 N4–N3 基礎。
7. 可納入時事題材，但教材文字、例句、題目與解說必須原創；外部事實需查證，不複製新聞原文。
8. 每課至少包含 Reading、單字、句型、Quick Quiz、Output Practice、前課複習、弱點回收，以及可回傳 ChatGPT 的純文字 learning feedback。
9. 保留現有 localStorage、清除確認、textarea 顯示、Clipboard API 嘗試與 iPhone 手動全選／拷貝 fallback 流程。
10. 新 lesson 必須使用新的 Lesson ID，避免 localStorage 互相覆蓋；不得把未驗收輸出標為 Final／Approved。

## 模板 placeholder 契約

純量 token 使用 `@@UPPER_SNAKE_CASE@@`，在 HTML 文字與 JavaScript 字串中都保持語法有效：

- `@@LESSON_ID@@`
- `@@LESSON_DATE@@`（`YYYY-MM-DD`）
- `@@TOPIC_JA@@`
- `@@TOPIC_ZH@@`
- `@@LESSON_SUMMARY_ZH@@`
- `@@JLPT_LEVEL@@`
- `@@DURATION@@`
- `@@DOMAIN@@`
- `@@REVIEW_PATTERN@@`

重複或結構化內容使用固定 selector：`#reading`、`#sentences`、`#grammar`、`#vocabulary`、`#quiz`、`#output`、`#review`、`#feedback .weak-list`。產生器應更新 selector 內的教材內容，但保留 section ID、CSS class、表單 ID/name 與 feedback 流程。完整資料契約見 `generator/template-schema.json`。

## 產生與驗證

1. 讀取符合 `generator/template-schema.json` 的 lesson config。
2. 複製模板到 `japanese/<lessonId>.html`，替換所有純量 token，再依固定 selector 填入結構化內容。
3. 合併 `generator/next-lesson-adjustments.json` 的弱點回收指示；不得把回饋中的亂填內容當成有效學習答案。
4. 驗證沒有殘留 `@@...@@` token、Lesson ID 唯一、JSON/schema 有效、必備 selector 與表單 ID 存在。
5. 在手機 Safari 或等效窄螢幕環境測試閱讀、ruby、表單、回饋產生、textarea 與 clipboard fallback。

`JP-V1-001.html` 是已驗收 sample，不是每次生成時覆寫的檔案。
