"""標準函式庫實作的 CLI API Client；可測試 CRUD 與查詢參數。"""

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description="桃園市婦女生育平均年齡 API Client")
    parser.add_argument("action", choices=["list", "get", "create", "update", "delete"])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--year", type=int, help="民國年")
    parser.add_argument("--age", type=float, help="平均年齡（歲）")
    parser.add_argument("--year-from", type=int)
    parser.add_argument("--year-to", type=int)
    parser.add_argument("--min-age", type=float)
    parser.add_argument("--max-age", type=float)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int)
    args = parser.parse_args()

    if args.action in {"get", "create", "update", "delete"} and args.year is None:
        parser.error(f"{args.action} 需要 --year")
    if args.action in {"create", "update"} and args.age is None:
        parser.error(f"{args.action} 需要 --age")

    base = args.base_url.rstrip("/") + "/api/v1/birth-ages"
    path = base if args.action in {"list", "create"} else f"{base}/{args.year}"
    if args.action == "list":
        filters = {
            "year_from": args.year_from, "year_to": args.year_to,
            "min_age": args.min_age, "max_age": args.max_age,
            "limit": args.limit, "offset": args.offset,
        }
        query = urlencode({key: val for key, val in filters.items() if val is not None})
        if query:
            path += "?" + query

    body = None
    if args.action in {"create", "update"}:
        payload = {"average_age": args.age}
        if args.action == "create":
            payload["roc_year"] = args.year
        body = json.dumps(payload).encode("utf-8")
    method = {"list": "GET", "get": "GET", "create": "POST",
              "update": "PUT", "delete": "DELETE"}[args.action]
    request = Request(path, data=body, method=method)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read()
            print(f"HTTP {response.status}")
            if response.headers.get("Location"):
                print("Location:", response.headers["Location"])
            if raw:
                print(json.dumps(json.loads(raw), indent=2, ensure_ascii=False))
            return 0
    except HTTPError as exc:
        print(f"HTTP {exc.code}", file=sys.stderr)
        print(exc.read().decode("utf-8"), file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"連線失敗：{exc.reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
