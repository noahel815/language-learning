# Japanese lessons through mid-September｜Release report

狀態：Published / 尚未標示為使用者 Approved

發布日期：2026-09-01

## 範圍

- 新增 2026-09-01～2026-09-15 共 15 課：W36-D2～D7、W37-D1～D7、W38-D1～D2。
- 延續 W36-D1，首頁本週區顯示 W36，另提供 W37～W38-D2 的九月中前入口。
- 每課包含 `trend-source` metadata；研究方法、Google Trends 前 10 筆顯示項目與 Threads 公開觀察樣本見 `TREND_TOPIC_PLAN_2026-09-01_to_09-15.md`。
- `JP-V1-001.html` 與 `templates/japanese-lesson-v1.html` 未修改。

## QA 與部署讀回

- Release validator：15/15 日期、ISO Lesson ID、source metadata、10 句、ruby/rt、placeholder、JavaScript 語法、首頁連結通過。
- Chrome 390×844：15/15 套用 mobile media query，`scrollWidth=375`、`innerWidth=390`，無頁面橫向溢位；ruby/rt 成對且實際渲染。
- 互動代表頁 9/1、9/7、9/15：Quick Quiz、Output Practice、前課複習展開、自評、弱點勾選、純文字 Learning Feedback 均通過。
- Frozen hashes：`JP-V1-001.html` 維持 `8D1E1933CC73351A8291F9AC00357116828DCE54D7AAC79FF5C91F811690B7BB`；template 維持 `A1834EC71C27BE73FF95652A89B1BF065A28D3CEC16F3628B136DD77D008BF92`。
- GitHub Pages：9/1、9/7、9/15 三頁直接讀回 HTTP 200，標題與 Lesson ID 正確。
- 內容發布 commit：`bb3103c33ea29d8a4eb85cba758a008e4f55c950`。

## Notion 只讀查重

已查詢 `Japanese｜日文複習` data source；W36-D1 既有 row 正常，但本次 15 個 Lesson IDs 均未找到。此次未寫入 Notion。

待新增範圍：`JP-V1-2026-W36-D2`～`D7`、`JP-V1-2026-W37-D1`～`D7`、`JP-V1-2026-W38-D1`～`D2`。若日後獲授權同步，應以 Lesson ID 再查重後新增，初始狀態「未讀」、完成 `false`，教材網址使用 GitHub Pages 正式 URL。
