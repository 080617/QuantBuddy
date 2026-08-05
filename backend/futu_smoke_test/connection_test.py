from __future__ import annotations

import sys
from futu import OpenQuoteContext, RET_OK


HOST = "127.0.0.1"
PORT = 11111


def main() -> int:
    quote_ctx = None

    try:
        print(f"Python: {sys.executable}")
        print(f"Connecting to FutuOpenD at {HOST}:{PORT}...")

        quote_ctx = OpenQuoteContext(host=HOST, port=PORT)

        ret, data = quote_ctx.get_global_state()

        if ret != RET_OK:
            print(f"FAILED: {data}")
            return 1

        print("\nConnection succeeded.")
        print(f"OpenD status: {data.get('program_status_type')}")
        print(f"Quote server logged in: {data.get('qot_logined')}")
        print(f"Trade server logged in: {data.get('trd_logined')}")
        print(f"OpenD version: {data.get('server_ver')}")
        print(f"Status description: {data.get('program_status_desc', '')}")

        if data.get("program_status_type") != "READY":
            print("\nWARNING: OpenD connected, but status is not READY.")
            return 2

        if data.get("qot_logined") is not True:
            print("\nWARNING: The quote server is not logged in.")
            return 3

        print("\nREAD-ONLY CONNECTION TEST: PASS")
        return 0

    except Exception as exc:
        print(f"\nCONNECTION TEST FAILED: {type(exc).__name__}: {exc}")
        return 1

    finally:
        if quote_ctx is not None:
            quote_ctx.close()
            print("Quote context closed.")


if __name__ == "__main__":
    raise SystemExit(main())