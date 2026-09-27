# AI 輔助開發紀錄

本專案依課程要求使用 AI 輔助開發工具完成設計與實作。提供給助理的任務是：使用附加的「5-18 桃園市婦女生育平均年齡.csv」，建立符合資料主題的 RESTful CRUD API，使用 Python、FastAPI、自動產生 Swagger UI、提供 API Client、測試及 GitHub README。

AI 輔助的內容：

1. 檢視 UTF-8 BOM CSV，確認欄位為民國年與婦女生育平均年齡，共 22 筆。
2. 對照桃園市政府[官方資料頁](https://opendata.tycg.gov.tw/datalist/f8903a8d-9044-47a5-b061-dab3d52128c0)，確認資料定義、單位、來源和授權。
3. 設計 `birth-ages` 年度紀錄資源的 GET／POST／PUT／DELETE 端點、篩選與錯誤碼。
4. 生成 FastAPI 伺服器、SQLite 持久化、Pydantic 驗證、標準函式庫 Client、自動化測試與說明文件。
5. 執行測試，檢查實際 Request / Response 與 `/openapi.json`，再匯出離線 OpenAPI 快照。

後續修改可參考根目錄 [`AGENTS.md`](../AGENTS.md)；所有範例及文件仍需以實際測試結果為準。
