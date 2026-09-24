# 新住民子女發展遲緩統計 REST API

以 `data/source.csv` 為資料來源的公開查詢專案。提供 FastAPI REST API、OpenAPI／Swagger 互動文件，以及由 GitHub Actions 發布到 GitHub Pages 的可查詢網頁和 JSON 快照。

**公開網頁：** https://1ray0.github.io/iot_homework/  
**原始碼：** https://github.com/1Ray0/iot_homework

## 資料範圍與解讀

來源是使用者提供的 `114新住民子女發展遲緩.csv`，已由 Big5 轉為 UTF-8 放在 `data/source.csv`。目前僅有 **2 筆**，皆為彰化縣、民國 114 年（西元 2025 年）：

| 項目 | 男性人數 | 女性人數 | 該項目合計 |
| --- | ---: | ---: | ---: |
| 通報數 | 141 | 83 | 224 |
| 個案管理數 | 142 | 79 | 221 |

「通報數」和「個案管理數」是不同指標，**不可把兩列相加解讀為不重複兒童總人數**。API 的彙總結果始終按項目分開；比較端點也拒絕比較不同項目的差值。CSV 不含個人資料、站點資訊或即時 YouBike 資料。

## 功能

| 方法 | 路徑 | 用途 |
| --- | --- | --- |
| GET | `/health` | 服務與 CSV 狀態 |
| GET | `/v1/source` | 來源欄位、更新時間與資料筆數 |
| GET | `/v1/facets` | 可用縣市、年度與項目 |
| GET | `/v1/records` | 篩選、搜尋、排序與分頁 |
| GET | `/v1/records/{id}` | 單筆資料 |
| POST | `/v1/records/search` | 用 JSON 執行複合條件查詢 |
| GET | `/v1/summary` | 按項目彙總，可再篩選縣市／年度／項目 |
| GET | `/v1/items/{item}/summary` | 單一項目彙總 |
| POST | `/v1/analytics/pivot` | 按項目及縣市／年度分組統計 |
| POST | `/v1/analytics/compare` | 比較兩筆**同項目**資料 |
| GET | `/docs` | Swagger UI 互動文件 |
| GET | `/redoc` | ReDoc 文件 |
| GET | `/openapi.json` | 自動產生的 OpenAPI 3 schema |

所有 POST 端點都是**唯讀分析**，不會修改 CSV。沒有使用者帳號、API key 或個人資料寫入功能。資料檔變動後，長駐 FastAPI 服務會在下一個請求自動重新讀取；GitHub Pages 須重新執行 Actions 才會更新快照。

## 在本機啟動 API

需要 Python 3.12 以上。

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

開啟 http://127.0.0.1:8000/docs，即可查看欄位、範例與直接測試 GET／POST。若要指定不同 CSV，設定環境變數 `DATA_PATH` 為檔案路徑；檔案須為 UTF-8，且欄位順序和名稱保持 `縣市,年度,項目,男性人數,女性人數`。

### 請求範例

```bash
curl 'http://127.0.0.1:8000/v1/records?county=%E5%BD%B0%E5%8C%96%E7%B8%A3&year_roc=114&limit=10'

curl -X POST 'http://127.0.0.1:8000/v1/records/search' \
  -H 'Content-Type: application/json' \
  -d '{"county":"彰化縣","year_roc":114,"min_total":220,"sort":"total_desc"}'

curl -X POST 'http://127.0.0.1:8000/v1/analytics/pivot' \
  -H 'Content-Type: application/json' \
  -d '{"group_by":["item","county","year_roc"]}'
```

搜尋參數包括 `county`、`year_roc`、`item`、關鍵字 `q`、`min_total`、`max_total`、`sort`、`limit` 與 `offset`。無符合資料時回傳空陣列；不合法的參數回傳 HTTP 422，找不到單筆資料回傳 404，CSV 遺失或格式錯誤回傳 503。

## GitHub Actions 與公開網站

`.github/workflows/ci.yml` 在推送和 Pull Request 時執行測試與網站建置。`.github/workflows/pages.yml` 在推送到 `main` 或手動啟動時，從 CSV 產生網站及 JSON 快照並部署 GitHub Pages。

首次需在 **Settings → Pages → Build and deployment → Source** 選擇 **GitHub Actions**。之後每次修改 `data/source.csv` 並推送到 `main`，Actions 會重新產生：

- `/api/v1/records.json` — 全部資料快照
- `/api/v1/summary.json` — 按項目彙總
- `/api/v1/facets.json` — 動態查詢選項
- `/openapi.json` — API 文件 schema
- `/` — 可按縣市、年度、項目與關鍵字查詢的網頁

GitHub Pages 是靜態網站，以上 JSON 是建置時的**唯讀快照**，不會處理 HTTP POST，也不會在每個請求重新讀 CSV。網頁會在載入時讀取最新發布的快照，讓訪客互動篩選。

## 對外部署可接收 POST 的 API

要讓網際網路上的使用者直接呼叫 POST，需將 FastAPI 部署到可持續運行容器或 Python 服務的主機。專案包含 `Dockerfile`：

```bash
docker build -t csv-stat-api .
docker run --rm -p 8000:8000 csv-stat-api
```

在雲端主機將此公開 repository 連接至服務，使用 Dockerfile 建置，對外開放服務指定的 `PORT`，健康檢查設為 `/health`。部署後 API 的 `/docs` 可直接 Try it out；也可在 GitHub Pages 網頁底部填入服務的 HTTPS 網址使用文件中的 Try it out。`/v1/records` 等 API 均允許跨來源讀取。請依預期流量在部署平台設定資源和速率限制。

GitHub Actions 負責測試和發布，**不能充當長時間運行的 POST 伺服器**。因此 Pages 網址與 FastAPI 服務網址會是兩個不同的端點。

## 更新資料與測試

CSV 每列需有縣市、民國年度、項目、男性人數、女性人數，且縣市＋年度＋項目組合不可重複。人數需為非負整數。新增其他縣市、年度或項目後，篩選選項、統計與文件仍可沿用；API 會在檔案變動後重讀資料。

```bash
pip install -r requirements-dev.txt
pytest -q
python scripts/build_site.py
```

## 授權

程式碼採 MIT License。`data/source.csv` 由使用者提供，原始資料授權未附；引用或再利用資料時請另確認來源授權。


