from __future__ import annotations

import math
from typing import Any

import pandas as pd
from futu import (
    OpenQuoteContext,
    OpenSecTradeContext,
    OrderType,
    RET_OK,
    TrdEnv,
    TrdMarket,
)


HOST = "127.0.0.1"
PORT = 11111

# 仅用于接口 Smoke Test，不代表模型交易信号。
TEST_CODE = "SZ.000001"


def mask_account_id(value: Any) -> str:
    text = str(value)
    if len(text) <= 4:
        return "****"
    return f"{'*' * (len(text) - 4)}{text[-4:]}"


def has_cn_authorization(value: Any) -> bool:
    if isinstance(value, (list, tuple, set)):
        return any(
            item == TrdMarket.CN or str(item).upper() == "CN"
            for item in value
        )

    return value == TrdMarket.CN or str(value).upper() == "CN"


def select_simulated_cn_account(
    accounts: pd.DataFrame,
) -> pd.Series:
    if accounts is None or accounts.empty:
        raise RuntimeError("No trading account was returned.")

    selected = accounts[
        accounts["trd_env"] == TrdEnv.SIMULATE
    ].copy()

    if "trdmarket_auth" in selected.columns:
        selected = selected[
            selected["trdmarket_auth"].apply(
                has_cn_authorization
            )
        ]

    if "acc_status" in selected.columns:
        selected = selected[
            selected["acc_status"].astype(str).str.upper()
            == "ACTIVE"
        ]

    if len(selected) != 1:
        raise RuntimeError(
            "Safety stop: expected exactly one active "
            f"A-share simulated account, found {len(selected)}."
        )

    return selected.iloc[0]


def get_number(
    row: pd.Series,
    field: str,
) -> float | None:
    if field not in row.index:
        return None

    value = row[field]

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if math.isnan(number):
        return None

    return number


def main() -> int:
    quote_ctx = None
    trade_ctx = None

    try:
        print(f"Connecting to FutuOpenD at {HOST}:{PORT}")
        print("A-SHARE MAXIMUM TRADABLE QUANTITY TEST")
        print("READ-ONLY: no order will be submitted.\n")

        # 1. 获取测试股票的实际行情与每手股数。
        quote_ctx = OpenQuoteContext(
            host=HOST,
            port=PORT,
        )

        ret, snapshots = quote_ctx.get_market_snapshot(
            [TEST_CODE]
        )

        if ret != RET_OK:
            print(f"FAILED to get snapshot: {snapshots}")
            return 1

        if snapshots is None or snapshots.empty:
            print("FAILED: no market snapshot returned.")
            return 1

        snapshot = snapshots.iloc[0]

        last_price = float(snapshot["last_price"])
        lot_size = int(snapshot["lot_size"])
        stock_name = snapshot.get("name", "N/A")
        suspended = bool(snapshot.get("suspension", False))

        print("Test security:")
        print(f"  Code: {TEST_CODE}")
        print(f"  Name: {stock_name}")
        print(f"  Last price: {last_price}")
        print(f"  Lot size: {lot_size}")
        print(f"  Suspended: {suspended}")

        if suspended:
            print("SAFETY STOP: test security is suspended.")
            return 2

        if last_price <= 0:
            print("SAFETY STOP: invalid reference price.")
            return 2

        # 2. 获取唯一的 A 股模拟账户。
        trade_ctx = OpenSecTradeContext(
            filter_trdmarket=TrdMarket.CN,
            host=HOST,
            port=PORT,
        )

        ret, accounts = trade_ctx.get_acc_list()

        if ret != RET_OK:
            print(f"FAILED to get account list: {accounts}")
            return 1

        account = select_simulated_cn_account(accounts)
        account_id = int(account["acc_id"])

        print("\nSelected account:")
        print(f"  Account ID: {mask_account_id(account_id)}")
        print(f"  Environment: {account.get('trd_env', 'N/A')}")
        print(f"  Account type: {account.get('acc_type', 'N/A')}")
        print(f"  Status: {account.get('acc_status', 'N/A')}")

        # 3. 查询该价格下的最大可买、最大可卖数量。
        ret, trading_info = trade_ctx.acctradinginfo_query(
            order_type=OrderType.NORMAL,
            code=TEST_CODE,
            price=last_price,
            trd_env=TrdEnv.SIMULATE,
            acc_id=account_id,
        )

        if ret != RET_OK:
            print(
                "\nFAILED to query maximum tradable quantity: "
                f"{trading_info}"
            )
            return 1

        if trading_info is None or trading_info.empty:
            print("\nFAILED: no trading information returned.")
            return 1

        info = trading_info.iloc[0]

        print("\n" + "=" * 64)
        print("MAXIMUM TRADABLE QUANTITY")
        print("=" * 64)

        fields = [
            ("max_cash_buy", "Maximum cash buy"),
            (
                "max_cash_and_margin_buy",
                "Maximum cash and margin buy",
            ),
            ("max_position_sell", "Maximum position sell"),
            ("max_sell_short", "Maximum short sell"),
            ("max_buy_back", "Maximum buy back"),
        ]

        for field, label in fields:
            if field in info.index:
                print(f"  {label}: {info[field]}")

        max_cash_buy = get_number(
            info,
            "max_cash_buy",
        )

        if max_cash_buy is None:
            print("\nNo usable max_cash_buy value was returned.")
            return 2

        lot_aligned_qty = (
            math.floor(max_cash_buy / lot_size) * lot_size
        )

        estimated_value = lot_aligned_qty * last_price

        print("\nCalculated order constraints:")
        print(f"  Raw maximum cash buy: {max_cash_buy}")
        print(f"  Lot-aligned maximum: {lot_aligned_qty}")
        print(
            "  Estimated maximum value: "
            f"{estimated_value:,.2f} CNY"
        )

        if max_cash_buy <= 0:
            print(
                "\nRESULT: The API currently reports zero "
                "cash-buy quantity."
            )
            print(
                "Do not proceed to an order test until "
                "the cause is confirmed."
            )
            return 2

        if lot_aligned_qty < lot_size:
            print(
                "\nRESULT: Positive quantity returned, "
                "but it is below one board lot."
            )
            return 2

        print(
            "\nREAD-ONLY CN MAXIMUM TRADABLE "
            "QUANTITY TEST: PASS"
        )
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

        if trade_ctx is not None:
            trade_ctx.close()
            print("A-share trade context closed.")


if __name__ == "__main__":
    raise SystemExit(main())