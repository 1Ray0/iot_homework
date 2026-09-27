"""用獨立資料庫檢驗匯入、CRUD、過濾和重啟後持久性。"""

from fastapi.testclient import TestClient

from app.main import create_app


def test_import_filters_and_schema(tmp_path):
    with TestClient(create_app(db_path=tmp_path / "db.sqlite3")) as client:
        result = client.get("/api/v1/birth-ages")
        assert result.status_code == 200
        assert result.json()["total"] == 22
        assert result.json()["items"][0] == {
            "roc_year": 93, "gregorian_year": 2004, "average_age": 28.4,
        }
        filtered = client.get("/api/v1/birth-ages", params={"year_from": 112, "limit": 2})
        assert filtered.json()["total"] == 3
        assert [row["roc_year"] for row in filtered.json()["items"]] == [112, 113]
        assert client.get("/api/v1/birth-ages", params={"min_age": 32.5}).json()["total"] == 1
        assert client.get("/openapi.json").json()["paths"]["/api/v1/birth-ages/{roc_year}"]["put"]


def test_create_update_delete_and_restart(tmp_path):
    db = tmp_path / "db.sqlite3"
    with TestClient(create_app(db_path=db)) as client:
        path = "/api/v1/birth-ages/115"
        created = client.post("/api/v1/birth-ages", json={"roc_year": 115, "average_age": 33.5})
        assert created.status_code == 201
        assert created.headers["location"] == path
        assert created.json()["gregorian_year"] == 2026
        assert client.post("/api/v1/birth-ages", json={"roc_year": 115, "average_age": 32}).status_code == 409
        assert client.put(path, json={"average_age": 33.8}).json()["average_age"] == 33.8
        assert client.get(path).json()["average_age"] == 33.8
        assert client.post("/api/v1/birth-ages", json={"roc_year": 116, "average_age": -1}).status_code == 422
        assert client.get("/api/v1/birth-ages", params={"year_from": 116, "year_to": 115}).status_code == 422
        assert client.delete(path).status_code == 204
        assert client.get(path).status_code == 404
        assert client.put(path, json={"average_age": 33}).status_code == 404
        assert client.delete(path).status_code == 404
        assert client.delete("/api/v1/birth-ages/93").status_code == 204
    with TestClient(create_app(db_path=db)) as client:
        assert client.get("/api/v1/birth-ages").json()["total"] == 21
        assert client.get("/api/v1/birth-ages/93").status_code == 404
