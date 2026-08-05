from __future__ import annotations

from futu import OpenQuoteContext, RET_OK


HOST = "127.0.0.1"
PORT = 11111

# 这两只股票已经出现在你的本地 Qlib / 沪深300数据验证流程中。
QLIB_CODES = [
    "SZ000001",
    "SH600104",
]


def qlib_code_to_futu(code: str) -> str:
    """
    将 Qlib 代码转换为富途代码。

    SZ000001 -> SZ.000001
    SH600104 -> SH.600104
    """
    normalized = code.strip().upper()

    if normalized.startswith("SH") and len(normalized) == 8:
        return f"SH.{normalized[2:]}"

    if normalized.startswith("SZ") and len(normalized) == 8:
        return f"SZ.{normalized[2:]}"

    raise ValueError(f"Unsupported Qlib code: {code}")


def main() -> int:
    quote_ctx = None

    try:
        print(f"Connecting to FutuOpenD at {HOST}:{PORT}")
        print("A-SHARE MARKET SNAPSHOT — READ-ONLY TEST")
        print("No order will be submitted.\n")

        futu_codes = [
            qlib_code_to_futu(code)
            for code in QLIB_CODES
        ]

        print("Code mapping:")

        for qlib_code, futu_code in zip(QLIB_CODES, futu_codes):
            print(f"  {qlib_code} -> {futu_code}")

        quote_ctx = OpenQuoteContext(
            host=HOST,
            port=PORT,
        )

        ret, snapshots = quote_ctx.get_market_snapshot(futu_codes)

        if ret != RET_OK:
            print(f"\nFAILED to query market snapshots: {snapshots}")
            return 1

        if snapshots is None or snapshots.empty:
            print("\nFAILED: No snapshot data returned.")
            return 1

        print(f"\nReturned snapshot count: {len(snapshots)}")

        # 不假定每个 SDK 版本都返回完全相同的字段。
        preferred_columns = [
            "code",
            "name",
            "stock_name",
            "update_time",
            "last_price",
            "open_price",
            "high_price",
            "low_price",
            "prev_close_price",
            "volume",
            "turnover",
            "lot_size",
            "suspension",
        ]

        available_columns = [
            column
            for column in preferred_columns
            if column in snapshots.columns
        ]

        print("\nMarket snapshots:")
        print(
            snapshots[available_columns].to_string(
                index=False
            )
        )

        returned_codes = set(snapshots["code"].astype(str))
        missing_codes = [
            code
            for code in futu_codes
            if code not in returned_codes
        ]

        if missing_codes:
            print(
                "\nWARNING: No snapshot returned for: "
                + ", ".join(missing_codes)
            )
            return 2

        print("\nREAD-ONLY CN QUOTE SNAPSHOT TEST: PASS")
        return 0

    except Exception as exc:
        print(
            "\nTEST FAILED: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    finally:
        if quote_ctx is not None:
            quote_ctx.close()
            print("Quote context closed.")


if __name__ == "__main__":
    raise SystemExit(main())