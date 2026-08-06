"""Export a read-only CN trading calendar from FutuOpenD; never touches orders."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from futu import OpenQuoteContext, RET_OK, TradeDateMarket


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11111)
    args = parser.parse_args()
    context = OpenQuoteContext(host=args.host, port=args.port)
    try:
        ret, data = context.request_trading_days(
            market=TradeDateMarket.CN, start=args.start, end=args.end
        )
        if ret != RET_OK:
            raise RuntimeError(str(data))
    finally:
        context.close()
    payload = {
        "source": "FutuOpenD TradeDateMarket.CN read-only calendar",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "start": args.start,
        "end": args.end,
        "trading_days": [item["time"] for item in data],
        "order_writes": False,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
