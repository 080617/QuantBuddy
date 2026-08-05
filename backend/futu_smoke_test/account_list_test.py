from __future__ import annotations

from typing import Any

from futu import (
    OpenSecTradeContext,
    RET_OK,
    TrdMarket,
)


HOST = "127.0.0.1"
PORT = 11111


def mask_account_id(value: Any) -> str:
    """只显示账户 ID 后四位，避免完整输出到日志。"""
    text = str(value)

    if len(text) <= 4:
        return "****"

    return f"{'*' * (len(text) - 4)}{text[-4:]}"


def test_market(market_name: str, market: TrdMarket) -> bool:
    trade_ctx = None

    try:
        print("\n" + "=" * 60)
        print(f"Checking {market_name} simulated accounts...")
        print("=" * 60)

        trade_ctx = OpenSecTradeContext(
            filter_trdmarket=market,
            host=HOST,
            port=PORT,
        )

        ret, data = trade_ctx.get_acc_list()

        if ret != RET_OK:
            print(f"{market_name} account query failed: {data}")
            return False

        if data is None or data.empty:
            print(f"No {market_name} trading accounts were returned.")
            return True

        print(f"Returned account count: {len(data)}")

        for index, row in data.iterrows():
            account_id = mask_account_id(row.get("acc_id", ""))
            trading_environment = row.get("trd_env", "UNKNOWN")
            account_type = row.get("acc_type", "UNKNOWN")
            security_firm = row.get("security_firm", "UNKNOWN")

            print(f"\nAccount {index + 1}")
            print(f"  Account ID: {account_id}")
            print(f"  Trading environment: {trading_environment}")
            print(f"  Account type: {account_type}")
            print(f"  Security firm: {security_firm}")

        return True

    except Exception as exc:
        print(
            f"{market_name} account test failed: "
            f"{type(exc).__name__}: {exc}"
        )
        return False

    finally:
        if trade_ctx is not None:
            trade_ctx.close()
            print(f"{market_name} trade context closed.")


def main() -> int:
    print(f"Connecting to FutuOpenD at {HOST}:{PORT}")
    print("READ-ONLY ACCOUNT LIST TEST")
    print("No order will be submitted.")

    hk_ok = test_market("Hong Kong market", TrdMarket.HK)
    us_ok = test_market("US market", TrdMarket.US)

    if hk_ok and us_ok:
        print("\nREAD-ONLY ACCOUNT LIST TEST: PASS")
        return 0

    print("\nREAD-ONLY ACCOUNT LIST TEST: PARTIAL OR FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())