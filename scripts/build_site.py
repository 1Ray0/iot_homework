"""Generate OpenAPI documentation and public JSON snapshots for GitHub Pages."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app, dataset, summary  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    source = dataset.get()
    generated_at = datetime.now(timezone.utc).isoformat()
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / ".nojekyll").touch()
    (SITE / "index.html").write_text((ROOT / "web" / "index.html").read_text(encoding="utf-8"), encoding="utf-8")
    write_json(SITE / "openapi.json", app.openapi())
    write_json(SITE / "api" / "v1" / "records.json", {"total": len(source.records), "generated_at": generated_at, "data": [r.model_dump() for r in source.records]})
    write_json(SITE / "api" / "v1" / "summary.json", {"generated_at": generated_at, "data": [r.model_dump() for r in summary(source.records)]})
    write_json(SITE / "api" / "v1" / "facets.json", {"counties": sorted({r.county for r in source.records}), "years_roc": sorted({r.year_roc for r in source.records}), "items": sorted({r.item for r in source.records})})
    print(f"Built site with {len(source.records)} records")


if __name__ == "__main__":
    main()


