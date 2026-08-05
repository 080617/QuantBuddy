from __future__ import annotations

from typing import Any

from futu import OpenSecTradeContext, RET_OK, TrdEnv, TrdMarket


HOST = "127.0.0.1"
PORT = 11111


def mask_account_id(value: Any) -> str:
    text = str(value)

    if len(text) <= 4:
        return "****"

    return f"{'*' * (len(text) - 4)}{text[-4:]}"


def main() -> int:
    trade_ctx = None

    try:
        print(f"Connecting to FutuOpenD at {HOST}:{PORT}")
        print("A-SHARE SIMULATED ACCOUNT TEST")
        print("No order will be submitted.\n")

        trade_ctx = OpenSecTradeContext(
            filter_trdmarket=TrdMarket.CN,
            host=HOST,
            port=PORT,
        )

        ret, accounts = trade_ctx.get_acc_list()

        if ret != RET_OK:
            print(f"FAILED to query A-share accounts: {accounts}")
            return 1

        if accounts is None or accounts.empty:
            print("No A-share trading account was returned.")
            return 2

        print(f"Returned account count: {len(accounts)}")

        simulated_count = 0

        for index, row in accounts.iterrows():
            account_id = row.get("acc_id", "")
            trading_environment = row.get("trd_env", "UNKNOWN")
            account_type = row.get("acc_type", "UNKNOWN")
            market_auth = row.get("trdmarket_auth", "UNKNOWN")
            account_status = row.get("acc_status", "UNKNOWN")

            print(f"\nAccount {index + 1}")
            print(f"  Account ID: {mask_account_id(account_id)}")
            print(f"  Trading environment: {trading_environment}")
            print(f"  Account type: {account_type}")
            print(f"  Market authorization: {market_auth}")
            print(f"  Account status: {account_status}")

            if trading_environment == TrdEnv.SIMULATE:
                simulated_count += 1

        print(f"\nA-share simulated account count: {simulated_count}")

        if simulated_count == 0:
            print("A-SHARE SIMULATED ACCOUNT TEST: BLOCKED")
            return 2

        print("A-SHARE SIMULATED ACCOUNT TEST: PASS")
        return 0

    except Exception as exc:
        print(f"TEST FAILED: {type(exc).__name__}: {exc}")
        return 1

    finally:
        if trade_ctx is not None:
            trade_ctx.close()
            print("A-share trade context closed.")


if __name__ == "__main__":
    raise SystemExit(main())