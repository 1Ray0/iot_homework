from pathlib import Path

from fastapi.testclient import TestClient

from app.main import Dataset, app, dataset

client = TestClient(app)


def test_csv_load_and_schema():
    source = dataset.get()
    assert len(source.records) == 2
    assert [(r.item, r.male_count, r.female_count, r.total_count) for r in source.records] == [
        ("通報數", 141, 83, 224),
        ("個案管理數", 142, 79, 221),
    ]
    assert source.records[0].year_gregorian == 2025
    assert client.get("/health").json()["status"] == "ok"
    assert "/v1/analytics/pivot" in client.get("/openapi.json").json()["paths"]


def test_get_filters_and_single_record():
    response = client.get("/v1/records", params={"county": "彰化縣", "year_roc": 114, "item": "通報數", "min_total": 200})
    assert response.status_code == 200
    assert response.json()["total"] == 1
    record_id = response.json()["data"][0]["id"]
    assert client.get(f"/v1/records/{record_id}").json()["total_count"] == 224
    assert client.get("/v1/records/unknown").status_code == 404
    assert client.get("/v1/facets").json() == {"counties": ["彰化縣"], "years_roc": [114], "items": ["個案管理數", "通報數"]}


def test_post_search_and_validation():
    response = client.post("/v1/records/search", json={"q": "管理", "sort": "total_desc", "limit": 10})
    assert response.json()["total"] == 1
    assert response.json()["data"][0]["female_count"] == 79
    assert client.post("/v1/records/search", json={"min_total": 300, "max_total": 100}).status_code == 422
    assert client.post("/v1/records/search", json={"limit": 501}).status_code == 422


def test_summary_keeps_items_separate():
    result = client.get("/v1/summary").json()
    assert len(result) == 2
    assert {r["item"]: r["total_count"] for r in result} == {"通報數": 224, "個案管理數": 221}
    assert client.get("/v1/items/通報數/summary").json()["male_share"] == round(141 / 224, 4)
    assert client.get("/v1/items/unknown/summary").status_code == 404


def test_pivot_and_compare_do_not_mix_metrics():
    pivot = client.post("/v1/analytics/pivot", json={"group_by": ["item", "county", "year_roc"]}).json()
    assert pivot["count"] == 2
    assert {r["total_count"] for r in pivot["data"]} == {224, 221}
    assert client.post("/v1/analytics/pivot", json={"group_by": ["county"]}).status_code == 422
    ids = [r.id for r in dataset.get().records]
    assert client.post("/v1/analytics/compare", json={"left_id": ids[0], "right_id": ids[1]}).status_code == 422


def test_csv_reloads_when_file_changes(tmp_path: Path):
    path = tmp_path / "test.csv"
    path.write_text("縣市,年度,項目,男性人數,女性人數\n彰化縣,114,通報數,1,2\n", encoding="utf-8")
    source = Dataset(path)
    assert source.get().records[0].total_count == 3
    path.write_text("縣市,年度,項目,男性人數,女性人數\n彰化縣,114,通報數,5,6\n", encoding="utf-8")
    assert source.get().records[0].total_count == 11


def test_invalid_csv_returns_service_error(tmp_path: Path):
    path = tmp_path / "bad.csv"
    path.write_text("縣市,年度,項目,男性人數,女性人數\n彰化縣,114,通報數,-1,2\n", encoding="utf-8")
    try:
        Dataset(path).get()
    except Exception as error:
        assert getattr(error, "status_code", None) == 503
    else:
        raise AssertionError("Invalid CSV was accepted")

