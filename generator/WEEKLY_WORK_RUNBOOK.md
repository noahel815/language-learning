# 每週日文產製 — Candidate，尚未啟用永久排程

正式根目錄：`C:\Users\tdliang\Documents\Codex\Projects\language-learning`。
本文件是可執行 Work 任務的作業契約。Work 必須有本機執行、已連線 Notion、GitHub 讀取與網頁工具。
CLI ChatGPT 登入已確認；CLI 沒有 Notion connector。不可宣稱單獨 Python/CLI 能完成 Notion。
工具 unavailable、quota、auth、查詢不完整，都必須停止並回報；不可假設沒有回饋。

## 同一週、同一條鏈

週日主流程採台北日期的下一個週一。週一補跑採當週週一，**永遠明確指定同一個 `--target-week YYYY-Www`**。
先讀 `.weekly/<week>/state.json`。complete 就結束；已 pushed/committed 則接續後段，禁止另產下一週。
沒有 state 才 prepare。若遠端已完整七課而沒有本機 state，先讀回 GitHub/Notion 重建證據，不要重新編寫。
若本週有部分正式教材，只產缺少的 ID；不得改既有教材，不補過去週次。
`.weekly/pipeline.lock` 防同時執行；Notion 跨工具步驟另有 `notion-sync.lock`。殘留鎖需確認原工作已停止後再明確恢復，不能自動刪除。

## 1. 讀取回饋與研究（Work connector）

fetch `collection://399114a6-0358-4421-964e-f300470ea2fa` 最新 schema，使用 query_data_sources：
日期近 30 天 OR 狀態=需複習 OR 弱點非空；讀 Recognition、Recall、Production、Naturalness、弱點、下週調整、批改摘要、完成、回饋已處理。
處理分頁，has_more=false；SQL LIMIT 截斷要用 keyset 分頁或縮小分批查詢，不能當完整。
有效分數不假設量尺；null 不是 0；亂填、測試、未批改的空答案不作能力依據。
有明確回饋的頁面 fetch 原文，歸納 `feedback:[{lessonId,targets:[句型],recognition,recall,production,naturalness,evidenceUrl}]`。
不要把「未讀」自動判定為弱點。無有效回饋時使用官方外部來源研究新題材，留下 url/title/checkedAt/summary；原創情境，不逐字翻譯新聞。
把精簡、必要的 context 寫入 `.weekly/context-<date>.json`，格式：

```json
{"status":"checked","checkedAt":"實際 ISO 時間與時區","dataSource":"collection://399114a6-0358-4421-964e-f300470ea2fa","complete":true,"feedback":[],"sources":[{"url":"https://官方來源","title":"標題","checkedAt":"日期","summary":"已查證摘要"}]}
```

不得寫入憑證。私人回饋只留被 Git 忽略的 .weekly，不進 public repo。

## 2. 編寫與 dry run

```powershell
.\run_weekly_pipeline.ps1 -Action dry-run -Context .weekly\context-<date>.json -TargetWeek YYYY-Www
```

預設呼叫已用 ChatGPT 登入的 `codex exec`，read-only 模型工作，stdout JSON 交回 orchestrator；不用私人 API Key，沒有假 API。
若 CLI 不可用：同指令加 `-Backend work`。exit 20 表示 AUTHOR_REQUIRED，Work 讀 `.weekly/<week>/author-prompt.txt`，自己編寫真正新內容為 content.json，再跑 stage。
不要把 exit 20 報成完成。exit 21=model author 失敗；orchestrator exit 1=停止且 events.jsonl 記錄失敗步驟；0=該步成功，不代表整條已發布。
既有 `build_mid_september_content.py` 僅 historical reference / JSON 組裝範例 / regression fixture，不呼叫。

```powershell
.\run_weekly_pipeline.ps1 -Action stage -Run .weekly\YYYY-Www
```

讀 manifest.json 的 stage 路徑；所有產生都在 stage 複本。執行 `python -B -m unittest discover -s generator -p 'test*.py' -v`。
逐課檢查自然度、讀音拆分、題目可回答、例句確實示範句型；自行解答 q1-q4/輸出，保存 answer review。
以本機 HTTP 預覽 staging，每課 390px 檢查無橫向溢位、ruby、輸入表單／回饋 Lesson ID；至少一課實測輸入與 fallback。
`editorial-review.json` 要綁定 content.json SHA-256，包含 reviewer、approved、mobilePreview="passed"、answersChecked=true，以及各課答案與限制。這是 Work 實際校閱紀錄，不能先填通過。

## 3. 明確發布關卡（本次 dry run 不執行）

工具實作必須先完成版本審查／提交，工具提交並發布後，先執行 `-Action refresh-base -Run .weekly\YYYY-Www`，再 stage 綁定新的 baseCommit；不要把工具與未審核教材混在同個提交。
publish 前不准有 tracked/staged 變更，origin 必須正確。

```powershell
.\run_weekly_pipeline.ps1 -Action publish -Run .weekly\YYYY-Www
.\run_weekly_pipeline.ps1 -Action verify-pages -Run .weekly\YYYY-Www
```

publish 用獨立 Git index 建立單一 commit，只含新 JSON、新 HTML 與首頁，普通非 force push。
HEAD/遠端前進會停止，不自動覆寫或 rebase。push 失敗保留同一 commit 可重試。
Pages 必須同一 commit 的 deployment success，加上線上首頁／各課內容 hash 讀回一致；HTTP/API 故障或 timeout 一律阻擋 Notion。
只出現 GitHub generator artifact 不算 Pages 成功。

## 4. Notion 去重、建立、讀回（Work connector）

只有 pages_verified 才可動 Notion。用 Lesson ID IN 目標七課查詢，完整結果寫成：
`{"dataSource":"collection://399114a6-0358-4421-964e-f300470ea2fa","complete":true,"checkedAt":"當下含時區 ISO","rows":[完整 properties]}`。

```powershell
.\run_weekly_pipeline.ps1 -Action notion-plan -Run .weekly\YYYY-Www -Snapshot .weekly\YYYY-Www\notion-before.json
```

按照 notion-write-plan.json：skip 不動學習進度；create 先再查該 Lesson ID（避免跨工具競爭），不存在才 create_pages。
一個 ID 多筆或日期/URL/Chapter衝突就停止，不任意修舊資料。新筆使用 properties + createOnly，狀態未讀、未完成、回饋未處理。
若 create timeout，先查 Lesson ID，再決定是否重試，禁止盲目再次 create。
每筆建立後 fetch 重新讀回原生 properties；最後完整目標集合再 query/fetch，保存 notion-readback.json。

```powershell
.\run_weekly_pipeline.ps1 -Action complete -Run .weekly\YYYY-Www -Snapshot .weekly\YYYY-Www\notion-readback.json
```

全部欄位吻合才 complete，並 fast-forward 本機正式 repo。Notion 學習狀態不被重置。
Notion 失敗不回滾已公開教材，只接續同步階段；回報部分完成。
更新本機成果總覽入口；回報 commit、Pages run、Notion 頁面、保護檔比對與未驗證事項。

## 排程提案（未建立）

同一個有 connector 的本機 Work/Codex 可執行任務：台北週日 18:00 + 週一 07:30。
週一只補同週的缺課／未完成 state，不正常生成第二批。電腦須開機且 app/登入/connector 可用。
建立前用真實排程環境試跑一次完整發布與 Notion；不能以 CLI 模型成功當成 connector 排程成功。
不用 GitHub-hosted runner 保存 ChatGPT 登入資訊；GitHub Actions 只驗證程式與已編寫 JSON。

## 人工恢復

本週 dry run 一鍵：`.\run_weekly_pipeline.ps1 -Action dry-run -Run .weekly\2026-W41`。
未來每週完整人工觸發：在有本機 repo 與 Notion connector 的 Work/Codex 任務輸入：
「依 generator/WEEKLY_WORK_RUNBOOK.md 執行本週日文流程，先更新 context，接續既有 state，完成 QA、Pages 與 Notion 讀回；失敗即停止並回報。」
這是執行任務，不是提醒。單獨 PowerShell 可產製/QA，但缺 connector 時不能假裝完成 Notion。

Candidate 校稿若改變 content.json，執行 stage 加 `--accept-revision`（PowerShell wrapper: `-AcceptRevision`），舊 manifest 自動保留於 manifest-history；必須重新 QA 與校閱。相同輸入重跑不需此參數。
