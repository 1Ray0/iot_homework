# 桃園市婦女生育平均年齡 RESTful API

以桃園市政府的年度開放資料建立 Python + FastAPI API。每筆資源對應一個民國年，提供完整 CRUD、條件篩選、Swagger UI 和命令列 API Client。

## 資料集與欄位

- 官方資料頁：[桃園市婦女生育平均年齡每年統計](https://opendata.tycg.gov.tw/datalist/f8903a8d-9044-47a5-b061-dab3d52128c0)。資料提供機關為桃園市政府主計處；官方說明指出平均年齡是當年生育婦女的平均年齡，以各年齡組中點計算，單位為歲。
- 本作業的原始資料：[`data/5-18 桃園市婦女生育平均年齡.csv`](data/5-18%20桃園市婦女生育平均年齡.csv)，UTF-8 BOM，22 筆，民國 93–114 年。此檔是本次作業提供的資料快照；API 不會每次啟動都重新下載官方網站。
- `年別` 為民國年，`婦女生育平均年齡` 的單位是歲。回應額外提供 `gregorian_year = roc_year + 1911`，方便閱讀。
- 資料集授權：政府資料開放授權條款第 1 版；本專案的資料來源應保留上述出處。此 API 是課程練習，不代表政府官方 API；透過 CRUD 寫入的資料屬本機練習資料。

## 環境建置

需求：Python 3.10 以上。

從此儲存庫下載或複製專案，進入資料夾：

```bash
git clone https://github.com/1Ray0/iot_homework.git
cd iot_homework
python -m venv .venv
```

啟用虛擬環境：

- Windows PowerShell：`.venv\Scripts\Activate.ps1`
- macOS / Linux：`source .venv/bin/activate`

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

開啟 [Swagger UI](http://127.0.0.1:8000/docs)、[ReDoc](http://127.0.0.1:8000/redoc) 或 [OpenAPI JSON](http://127.0.0.1:8000/openapi.json)。API 預設位址是 `http://127.0.0.1:8000`；Swagger UI 的 **Try it out** 可直接呼叫所有端點，啟動後即可線上互動測試。

第一次啟動會將 CSV 匯入 `birth_ages.sqlite3`。此資料庫會保留後續 CRUD 變更，並已列入 `.gitignore`；原始 CSV 不會被改動。若要恢復原始 22 筆資料，停止伺服器後刪除 `birth_ages.sqlite3`，重新啟動即可。可用環境變數 `BIRTH_AGE_DB_PATH` 指定其他 SQLite 檔案位置。

## REST API 一覽

| 操作 | Method | URL Path | 成功回應 |
| --- | --- | --- | --- |
| 列出／篩選年度紀錄 | GET | `/api/v1/birth-ages` | `200`，含 `items`, `total`, `limit`, `offset` |
| 讀取指定年 | GET | `/api/v1/birth-ages/{roc_year}` | `200`，單筆紀錄 |
| 新增年度紀錄 | POST | `/api/v1/birth-ages` | `201`，單筆紀錄與 `Location` header |
| 更新指定年平均年齡 | PUT | `/api/v1/birth-ages/{roc_year}` | `200`，更新後紀錄 |
| 刪除指定年 | DELETE | `/api/v1/birth-ages/{roc_year}` | `204`，無 response body |

GET 列表可帶 `year_from`、`year_to`、`min_age`、`max_age`、`limit`（預設 100，上限 500）、`offset`（預設 0）。依民國年由小到大排序。年別為不可修改的識別碼，PUT 只需提供完整的可修改內容 `average_age`。不存在的紀錄回傳 `404`，重複新增回傳 `409`，無效欄位／參數回傳 `422`。詳細規格與範例參見 [`docs/API_SPEC.md`](docs/API_SPEC.md)。

## 使用 Python API Client 實測

先啟動伺服器，接著在另一個終端機執行：

```bash
python client.py list --year-from 112 --limit 2
python client.py get --year 114
python client.py create --year 115 --age 33.5
python client.py update --year 115 --age 33.8
python client.py delete --year 115
```

Client 僅使用 Python 標準函式庫。若 API 部署在別處，每個指令加上 `--base-url https://你的網址`。新增與刪除也可在 Swagger UI 實測，但注意操作會修改本機資料庫。

## 測試

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

測試在臨時 SQLite 資料庫中驗證原始資料匯入、CRUD、篩選、狀態碼、Swagger 規格和重啟後的持久性，不會更動作業的資料庫。`docs/openapi.json` 是由 FastAPI 自動產生並另存的規格快照；執行中的權威版本為 `/openapi.json`。

## 專案結構

```text
iot_homework/
├── app/main.py             # FastAPI 路由、驗證及 SQLite 存取
├── data/*.csv              # 單一原始 Open Data 檔
├── client.py               # Python API Client
├── tests/test_api.py       # 自動化 API 測試
├── docs/API_SPEC.md        # 規格及 Request/Response 範例
├── docs/openapi.json       # 自動產生的 OpenAPI 文件
├── docs/AI_ASSISTANCE.md   # AI 輔助開發紀錄
├── AGENTS.md               # 後續 AI 開發的專案指示
├── requirements.txt        # 執行環境
└── requirements-dev.txt    # 測試環境
```

## 繳交前確認

1. 此專案公開網址：[https://github.com/1Ray0/iot_homework](https://github.com/1Ray0/iot_homework)。用無痕視窗確認網址可讀、檔案齊全。
2. 若自行部署雲端，再附上可存取的 API URL；只在本機啟動時不要填寫虛構部署網址。GitHub 儲存庫網址並非可接受 CRUD 請求的伺服器網址。
3. 將 [`docs/SUBMISSION.md`](docs/SUBMISSION.md) 中的學號、姓名填妥，寄至課程指定信箱。提早繳交與最終期限依作業公告為準。
