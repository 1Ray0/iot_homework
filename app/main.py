"""以政府開放資料建立可持久化的年度生育平均年齡 REST API。"""

import csv
import os
import sqlite3
from contextlib import asynccontextmanager, closing
from pathlib import Path

from fastapi import FastAPI, HTTPException, Path as PathParam, Query, Response, status
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = PROJECT_ROOT / "data" / "5-18 桃園市婦女生育平均年齡.csv"


class BirthAgeCreate(BaseModel):
    roc_year: int = Field(ge=1, le=999, description="民國年，例如 114")
    average_age: float = Field(gt=0, le=120, description="當年生育婦女的平均年齡，單位：歲")


class BirthAgeUpdate(BaseModel):
    average_age: float = Field(gt=0, le=120, description="新的平均年齡，單位：歲；年別為不可修改的資源識別碼")


class BirthAgeRecord(BirthAgeCreate):
    gregorian_year: int = Field(description="西元年，由民國年加 1911 得出")


class BirthAgeList(BaseModel):
    items: list[BirthAgeRecord]
    total: int = Field(description="篩選後的總筆數，不受 limit/offset 影響")
    limit: int
    offset: int


class ErrorResponse(BaseModel):
    detail: str


def as_record(row: sqlite3.Row) -> BirthAgeRecord:
    year = int(row["roc_year"])
    return BirthAgeRecord(
        roc_year=year, gregorian_year=year + 1911, average_age=row["average_age"]
    )


def create_app(db_path: Path | None = None, csv_path: Path | None = None) -> FastAPI:
    """接受測試用路徑；正式環境可設定 BIRTH_AGE_DB_PATH。"""
    database = Path(db_path or os.getenv("BIRTH_AGE_DB_PATH", PROJECT_ROOT / "birth_ages.sqlite3"))
    source = Path(csv_path or DEFAULT_CSV)

    def connect():
        conn = sqlite3.connect(database, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize() -> None:
        database.parent.mkdir(parents=True, exist_ok=True)
        with closing(connect()) as conn, conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS birth_ages ("
                "roc_year INTEGER PRIMARY KEY CHECK (roc_year BETWEEN 1 AND 999), "
                "average_age REAL NOT NULL CHECK (average_age > 0 AND average_age <= 120))"
            )
            conn.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            if conn.execute("SELECT 1 FROM metadata WHERE key = 'seeded'").fetchone():
                return
            with source.open("r", encoding="utf-8-sig", newline="") as file:
                records = list(csv.DictReader(file))
            for row in records:
                conn.execute(
                    "INSERT INTO birth_ages (roc_year, average_age) VALUES (?, ?)",
                    (int(row["年別"]), float(row["婦女生育平均年齡"])),
                )
            conn.execute("INSERT INTO metadata (key, value) VALUES ('seeded', '1')")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        initialize()
        yield

    app = FastAPI(
        title="桃園市婦女生育平均年齡 API",
        description=(
            "桃園市政府開放資料的年度紀錄；年別使用民國年，平均年齡單位為歲。"
            "首次執行會從附帶的 CSV 匯入 SQLite；後續修改保存在 SQLite。"
        ),
        version="1.0.0",
        lifespan=lifespan,
        openapi_tags=[{"name": "年度紀錄", "description": "每一民國年一筆，可新增、查詢、修改及刪除。"}],
    )

    @app.get("/api/v1/birth-ages", response_model=BirthAgeList, tags=["年度紀錄"])
    def list_records(
        year_from: int | None = Query(None, ge=1, le=999),
        year_to: int | None = Query(None, ge=1, le=999),
        min_age: float | None = Query(None, gt=0, le=120),
        max_age: float | None = Query(None, gt=0, le=120),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        if year_from is not None and year_to is not None and year_from > year_to:
            raise HTTPException(422, "year_from 不得大於 year_to")
        if min_age is not None and max_age is not None and min_age > max_age:
            raise HTTPException(422, "min_age 不得大於 max_age")
        clauses, values = [], []
        for condition, parameter in (
            ("roc_year >= ?", year_from),
            ("roc_year <= ?", year_to),
            ("average_age >= ?", min_age),
            ("average_age <= ?", max_age),
        ):
            if parameter is not None:
                clauses.append(condition)
                values.append(parameter)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with closing(connect()) as conn:
            total = conn.execute("SELECT COUNT(*) FROM birth_ages" + where, values).fetchone()[0]
            rows = conn.execute(
                "SELECT roc_year, average_age FROM birth_ages" + where
                + " ORDER BY roc_year ASC LIMIT ? OFFSET ?", [*values, limit, offset]
            ).fetchall()
        return BirthAgeList(items=[as_record(row) for row in rows], total=total, limit=limit, offset=offset)

    @app.get(
        "/api/v1/birth-ages/{roc_year}", response_model=BirthAgeRecord, tags=["年度紀錄"],
        responses={404: {"model": ErrorResponse, "description": "該年紀錄不存在"}},
    )
    def get_record(roc_year: int = PathParam(ge=1, le=999)):
        with closing(connect()) as conn:
            row = conn.execute(
                "SELECT roc_year, average_age FROM birth_ages WHERE roc_year = ?", (roc_year,)
            ).fetchone()
        if row is None:
            raise HTTPException(404, "找不到該年紀錄")
        return as_record(row)

    @app.post(
        "/api/v1/birth-ages", response_model=BirthAgeRecord,
        status_code=status.HTTP_201_CREATED, tags=["年度紀錄"],
        responses={409: {"model": ErrorResponse, "description": "該民國年已有紀錄"}},
    )
    def create_record(body: BirthAgeCreate, response: Response):
        with closing(connect()) as conn, conn:
            try:
                conn.execute(
                    "INSERT INTO birth_ages (roc_year, average_age) VALUES (?, ?)",
                    (body.roc_year, body.average_age),
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(409, "該民國年紀錄已存在") from exc
        response.headers["Location"] = f"/api/v1/birth-ages/{body.roc_year}"
        return BirthAgeRecord(**body.model_dump(), gregorian_year=body.roc_year + 1911)

    @app.put(
        "/api/v1/birth-ages/{roc_year}", response_model=BirthAgeRecord, tags=["年度紀錄"],
        responses={404: {"model": ErrorResponse, "description": "該年紀錄不存在"}},
    )
    def update_record(body: BirthAgeUpdate, roc_year: int = PathParam(ge=1, le=999)):
        with closing(connect()) as conn, conn:
            cursor = conn.execute(
                "UPDATE birth_ages SET average_age = ? WHERE roc_year = ?",
                (body.average_age, roc_year),
            )
            if cursor.rowcount == 0:
                raise HTTPException(404, "找不到該年紀錄")
        return BirthAgeRecord(roc_year=roc_year, gregorian_year=roc_year + 1911,
                              average_age=body.average_age)

    @app.delete(
        "/api/v1/birth-ages/{roc_year}", status_code=status.HTTP_204_NO_CONTENT,
        tags=["年度紀錄"],
        responses={404: {"model": ErrorResponse, "description": "該年紀錄不存在"}},
    )
    def delete_record(roc_year: int = PathParam(ge=1, le=999)):
        with closing(connect()) as conn, conn:
            cursor = conn.execute("DELETE FROM birth_ages WHERE roc_year = ?", (roc_year,))
            if cursor.rowcount == 0:
                raise HTTPException(404, "找不到該年紀錄")
        return Response(status_code=204)

    return app


app = create_app()
