"""CSV-backed public REST API for aggregate child development statistics."""

from __future__ import annotations

import csv
import hashlib
import os
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DATA_PATH = Path(os.getenv("DATA_PATH", Path(__file__).resolve().parents[1] / "data" / "source.csv"))
REQUIRED_COLUMNS = ("縣市", "年度", "項目", "男性人數", "女性人數")


class Record(BaseModel):
    id: str = Field(description="由縣市、年度、項目產生的穩定識別碼")
    county: str
    year_roc: int = Field(description="民國年度")
    year_gregorian: int = Field(description="西元年度，依民國年度 + 1911 換算")
    item: str = Field(description="原始資料指標，通報數與個案管理數的定義不同")
    male_count: int = Field(ge=0)
    female_count: int = Field(ge=0)
    total_count: int = Field(ge=0, description="同一筆指標的男女人數合計")


class SearchRequest(BaseModel):
    county: str | None = Field(default=None, max_length=100)
    year_roc: int | None = Field(default=None, ge=1)
    item: str | None = Field(default=None, max_length=100)
    q: str | None = Field(default=None, max_length=100, description="縣市或項目關鍵字")
    min_total: int = Field(default=0, ge=0)
    max_total: int | None = Field(default=None, ge=0)
    sort: Literal["county", "year_desc", "total_desc", "male_desc", "female_desc"] = "county"
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class RecordPage(BaseModel):
    total: int
    limit: int
    offset: int
    data_updated_at: str
    data: list[Record]


class SummaryRow(BaseModel):
    item: str
    record_count: int
    male_count: int
    female_count: int
    total_count: int
    male_share: float | None = Field(description="該指標男性占比；總數為 0 時為 null")
    female_share: float | None = Field(description="該指標女性占比；總數為 0 時為 null")


class PivotRequest(BaseModel):
    group_by: list[Literal["item", "county", "year_roc"]] = Field(default_factory=lambda: ["item"])
    county: str | None = None
    year_roc: int | None = Field(default=None, ge=1)
    item: str | None = None


class CompareRequest(BaseModel):
    left_id: str
    right_id: str


class Dataset:
    def __init__(self, path: Path = DATA_PATH):
        self.path = path
        self._lock = threading.Lock()
        self._mtime_ns: int | None = None
        self.records: list[Record] = []
        self.updated_at = ""

    def get(self) -> "Dataset":
        try:
            mtime_ns = self.path.stat().st_mtime_ns
        except OSError as exc:
            raise HTTPException(status_code=503, detail="CSV data file is unavailable") from exc
        if self._mtime_ns == mtime_ns:
            return self
        with self._lock:
            if self._mtime_ns == mtime_ns:
                return self
            try:
                with self.path.open(encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    if not reader.fieldnames or tuple(reader.fieldnames) != REQUIRED_COLUMNS:
                        raise ValueError("CSV columns do not match the documented schema")
                    rows = list(reader)
                records = [parse_row(row) for row in rows]
                if len({record.id for record in records}) != len(records):
                    raise ValueError("Duplicate county, year and item combination")
                self.records = records
                self.updated_at = datetime.fromtimestamp(mtime_ns / 1e9, timezone.utc).isoformat()
                self._mtime_ns = mtime_ns
            except (OSError, UnicodeError, ValueError, KeyError) as exc:
                raise HTTPException(status_code=503, detail=f"CSV data is invalid: {exc}") from exc
        return self


def parse_row(row: dict[str, str]) -> Record:
    county, item = row["縣市"].strip(), row["項目"].strip()
    if not county or not item:
        raise ValueError("County and item must be non-empty")
    year = int(row["年度"])
    male, female = int(row["男性人數"]), int(row["女性人數"])
    if year < 1 or male < 0 or female < 0:
        raise ValueError("Year and counts must be non-negative")
    record_id = hashlib.sha256(f"{county}|{year}|{item}".encode("utf-8")).hexdigest()[:12]
    return Record(id=record_id, county=county, year_roc=year, year_gregorian=year + 1911, item=item, male_count=male, female_count=female, total_count=male + female)


def find(records: list[Record], request: SearchRequest) -> tuple[int, list[Record]]:
    if request.max_total is not None and request.max_total < request.min_total:
        raise HTTPException(status_code=422, detail="max_total must be at least min_total")
    q = request.q.strip().casefold() if request.q else None
    filtered = [
        r for r in records
        if (request.county is None or r.county.casefold() == request.county.casefold())
        and (request.year_roc is None or r.year_roc == request.year_roc)
        and (request.item is None or r.item.casefold() == request.item.casefold())
        and (q is None or q in r.county.casefold() or q in r.item.casefold())
        and r.total_count >= request.min_total
        and (request.max_total is None or r.total_count <= request.max_total)
    ]
    if request.sort == "year_desc":
        filtered.sort(key=lambda r: (-r.year_roc, r.county, r.item))
    elif request.sort == "total_desc":
        filtered.sort(key=lambda r: (-r.total_count, r.county, r.item))
    elif request.sort == "male_desc":
        filtered.sort(key=lambda r: (-r.male_count, r.county, r.item))
    elif request.sort == "female_desc":
        filtered.sort(key=lambda r: (-r.female_count, r.county, r.item))
    else:
        filtered.sort(key=lambda r: (r.county, r.year_roc, r.item))
    return len(filtered), filtered[request.offset:request.offset + request.limit]


def summary(records: list[Record]) -> list[SummaryRow]:
    groups: dict[str, list[Record]] = defaultdict(list)
    for record in records:
        groups[record.item].append(record)
    result = []
    for item, rows in sorted(groups.items()):
        male = sum(r.male_count for r in rows)
        female = sum(r.female_count for r in rows)
        total = male + female
        result.append(SummaryRow(item=item, record_count=len(rows), male_count=male, female_count=female, total_count=total, male_share=round(male / total, 4) if total else None, female_share=round(female / total, 4) if total else None))
    return result


dataset = Dataset()
app = FastAPI(
    title="新住民子女發展遲緩統計 REST API",
    version="1.0.0",
    description="以使用者提供的 CSV 為資料來源。每筆是縣市、年度、項目的彙總人數。POST 用於複合查詢與分析，不修改原始 CSV。不同項目不可直接合計為不重複人數。",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


@app.get("/", tags=["service"])
def root():
    return {"name": app.title, "version": app.version, "docs": "/docs", "openapi": "/openapi.json"}


@app.get("/health", tags=["service"])
def health():
    source = dataset.get()
    return {"status": "ok", "record_count": len(source.records), "data_updated_at": source.updated_at}


@app.get("/v1/source", tags=["service"])
def source_info():
    source = dataset.get()
    return {"file": "data/source.csv", "encoding": "UTF-8", "columns": REQUIRED_COLUMNS, "record_count": len(source.records), "data_updated_at": source.updated_at, "refresh": "CSV file changes are loaded on the next request"}


@app.get("/v1/facets", tags=["records"])
def facets():
    records = dataset.get().records
    return {"counties": sorted({r.county for r in records}), "years_roc": sorted({r.year_roc for r in records}), "items": sorted({r.item for r in records})}


@app.get("/v1/records", response_model=RecordPage, tags=["records"])
def list_records(
    county: str | None = None,
    year_roc: int | None = Query(default=None, ge=1),
    item: str | None = None,
    q: str | None = Query(default=None, max_length=100),
    min_total: int = Query(default=0, ge=0),
    max_total: int | None = Query(default=None, ge=0),
    sort: Literal["county", "year_desc", "total_desc", "male_desc", "female_desc"] = "county",
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    source = dataset.get()
    total, rows = find(source.records, SearchRequest(county=county, year_roc=year_roc, item=item, q=q, min_total=min_total, max_total=max_total, sort=sort, limit=limit, offset=offset))
    return RecordPage(total=total, limit=limit, offset=offset, data_updated_at=source.updated_at, data=rows)


@app.post("/v1/records/search", response_model=RecordPage, tags=["records"])
def search_records(request: SearchRequest):
    """Complex JSON search with filter, sort and pagination."""
    source = dataset.get()
    total, rows = find(source.records, request)
    return RecordPage(total=total, limit=request.limit, offset=request.offset, data_updated_at=source.updated_at, data=rows)


@app.get("/v1/records/{record_id}", response_model=Record, tags=["records"])
def get_record(record_id: str):
    for record in dataset.get().records:
        if record.id == record_id:
            return record
    raise HTTPException(status_code=404, detail="Record not found")


@app.get("/v1/summary", response_model=list[SummaryRow], tags=["analytics"])
def get_summary(county: str | None = None, year_roc: int | None = Query(default=None, ge=1), item: str | None = None):
    records = dataset.get().records
    return summary([r for r in records if (county is None or r.county.casefold() == county.casefold()) and (year_roc is None or r.year_roc == year_roc) and (item is None or r.item.casefold() == item.casefold())])


@app.get("/v1/items/{item}/summary", response_model=SummaryRow, tags=["analytics"])
def item_summary(item: str):
    result = get_summary(county=None, year_roc=None, item=item)
    if not result:
        raise HTTPException(status_code=404, detail="Item not found")
    return result[0]


@app.post("/v1/analytics/pivot", tags=["analytics"])
def pivot(request: PivotRequest):
    """Group by item plus optional county and year, preserving metric boundaries."""
    if not request.group_by or len(set(request.group_by)) != len(request.group_by) or "item" not in request.group_by:
        raise HTTPException(status_code=422, detail="group_by must contain item exactly once and have no duplicates")
    records = [r for r in dataset.get().records if (request.county is None or r.county.casefold() == request.county.casefold()) and (request.year_roc is None or r.year_roc == request.year_roc) and (request.item is None or r.item.casefold() == request.item.casefold())]
    groups: dict[tuple, list[Record]] = defaultdict(list)
    for record in records:
        groups[tuple(getattr(record, key) for key in request.group_by)].append(record)
    data = []
    for key, rows in sorted(groups.items()):
        male, female = sum(r.male_count for r in rows), sum(r.female_count for r in rows)
        data.append({"group": dict(zip(request.group_by, key)), "record_count": len(rows), "male_count": male, "female_count": female, "total_count": male + female})
    return {"group_by": request.group_by, "count": len(data), "data": data}


@app.post("/v1/analytics/compare", tags=["analytics"])
def compare(request: CompareRequest):
    """Compare two rows of the same metric only."""
    by_id = {r.id: r for r in dataset.get().records}
    left, right = by_id.get(request.left_id), by_id.get(request.right_id)
    if left is None or right is None:
        raise HTTPException(status_code=404, detail="One or both records were not found")
    if left.item != right.item:
        raise HTTPException(status_code=422, detail="Cannot compare different items as one metric")
    return {"item": left.item, "left": left, "right": right, "difference_right_minus_left": {"male_count": right.male_count - left.male_count, "female_count": right.female_count - left.female_count, "total_count": right.total_count - left.total_count}}

