# 專案開發約定（供 AI 輔助工具使用）

- 原始資料是 `data/5-18 桃園市婦女生育平均年齡.csv`；維持原始 CSV 不變，勿將測試用的寫入結果誤稱官方統計資料。
- 主要資源是一個民國年度生育平均年齡紀錄；保持 POST/GET/PUT/DELETE 的狀態碼與 SQLite 持久化行為。
- API 變動時同步檢查 Swagger `/openapi.json`、`docs/API_SPEC.md`、README 與 Client。
- 測試請使用臨時資料庫，不要覆蓋使用者的正式 SQLite 資料庫。
