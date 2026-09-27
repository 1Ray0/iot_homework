# API 規格與實測範例

Base URL：`http://127.0.0.1:8000/api/v1`；交換格式：JSON；資源：`birth-ages`（桃園市各民國年度婦女生育平均年齡）。動態 Swagger UI：`http://127.0.0.1:8000/docs`；動態 OpenAPI：`http://127.0.0.1:8000/openapi.json`。另提供離線快照 [`openapi.json`](openapi.json)。

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| GET | `/birth-ages` | 可選 `year_from`, `year_to`, `min_age`, `max_age`, `limit`, `offset` | `200`：`{items: [...], total, limit, offset}` |
| GET | `/birth-ages/{roc_year}` | `roc_year`：民國年 | `200`：單筆年度紀錄；`404`：不存在 |
| POST | `/birth-ages` | `{"roc_year": 115, "average_age": 33.5}` | `201`：新增紀錄及 Location；`409`：年別重複 |
| PUT | `/birth-ages/{roc_year}` | `{"average_age": 33.8}` | `200`：更新後紀錄；`404`：不存在 |
| DELETE | `/birth-ages/{roc_year}` | 無 | `204`：無內容；`404`：不存在 |

`roc_year` 限 1–999；`average_age` 必須大於 0 且不大於 120。型別或範圍錯誤回傳 `422`。紀錄回應包含 `roc_year`、`gregorian_year`、`average_age`，年齡單位為歲。篩選邊界包含等號；列表按照民國年升序，`total` 是分頁前的篩選總數。

## Request / Response 範例

以下 GET 範例使用附帶的原始資料；寫入範例請依序操作，避免測試互相干擾。

**GET /api/v1/birth-ages/114**

```http
GET /api/v1/birth-ages/114 HTTP/1.1
Host: 127.0.0.1:8000
```

`200 OK`：

```json
{"roc_year":114,"average_age":32.57,"gregorian_year":2025}
```

**GET /api/v1/birth-ages?year_from=112&limit=2**

`200 OK`：

```json
{"items":[{"roc_year":112,"average_age":32.24,"gregorian_year":2023},{"roc_year":113,"average_age":32.32,"gregorian_year":2024}],"total":3,"limit":2,"offset":0}
```

**POST /api/v1/birth-ages**

```http
POST /api/v1/birth-ages HTTP/1.1
Content-Type: application/json

{"roc_year":115,"average_age":33.5}
```

`201 Created`，`Location: /api/v1/birth-ages/115`：

```json
{"roc_year":115,"average_age":33.5,"gregorian_year":2026}
```

再送一次相同年別：`409 Conflict`，`{"detail":"該民國年紀錄已存在"}`。

**PUT /api/v1/birth-ages/115**

```http
PUT /api/v1/birth-ages/115 HTTP/1.1
Content-Type: application/json

{"average_age":33.8}
```

`200 OK`：

```json
{"roc_year":115,"average_age":33.8,"gregorian_year":2026}
```

**DELETE /api/v1/birth-ages/115**

`204 No Content`，response body 為空。再次 GET 該年：`404 Not Found`，`{"detail":"找不到該年紀錄"}`。

> OpenAPI 規格由 FastAPI 從 Python 路由和 Pydantic 模型自動產生。文件中的寫入數值只是教學測試值，並非桃園市政府發布的實際統計資料。
