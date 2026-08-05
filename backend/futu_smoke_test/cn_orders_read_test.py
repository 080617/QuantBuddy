from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from futu import (
    OpenSecTradeContext,
    RET_OK,
    TrdEnv,
    TrdMarket,
)


HOST = "127.0.0.1"
PORT = 11111
HISTORY_DAYS = 30


def mask_account_id(value: Any) -> str:
    """只显示账户 ID 后四位。"""
    text = str(value)

    if len(text) <= 4:
        return "****"

    return f"{'*' * (len(text) - 4)}{text[-4:]}"


def mask_order_id(value: Any) -> str:
    """只显示订单 ID 后六位。"""
    text = str(value)

    if not text or text.lower() == "nan":
        return "N/A"

    if len(text) <= 6:
        return "******"

    return f"{'*' * (len(text) - 6)}{text[-6:]}"


def has_cn_authorization(value: Any) -> bool:
    """兼容 SDK 可能返回枚举或字符串列表的情况。"""
    if isinstance(value, (list, tuple, set)):
        return any(
            item == TrdMarket.CN or str(item).upper() == "CN"
            for item in value
        )

    return value == TrdMarket.CN or str(value).upper() == "CN"


def select_simulated_cn_account(accounts: pd.DataFrame) -> pd.Series:
    """只选择唯一的、处于 ACTIVE 状态的 A 股模拟账户。"""
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

    if selected.empty:
        raise RuntimeError(
            "No active A-share simulated account was found."
        )

    if len(selected) != 1:
        raise RuntimeError(
            "Safety stop: expected exactly one active "
            f"A-share simulated account, found {len(selected)}."
        )

    account = selected.iloc[0]

    if account.get("trd_env") != TrdEnv.SIMULATE:
        raise RuntimeError(
            "Safety stop: selected account is not SIMULATE."
        )

    return account


def print_orders(title: str, orders: pd.DataFrame) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)

    if orders is None or orders.empty:
        print("No orders returned.")
        return

    display = orders.copy()

    if "order_id" in display.columns:
        display["order_id"] = display["order_id"].apply(
            mask_order_id
        )

    preferred_columns = [
        "code",
        "stock_name",
        "trd_side",
        "order_type",
        "order_status",
        "order_id",
        "qty",
        "price",
        "dealt_qty",
        "dealt_avg_price",
        "create_time",
        "updated_time",
        "last_err_msg",
    ]

    available_columns = [
        column
        for column in preferred_columns
        if column in display.columns
    ]

    print(f"Order count: {len(display)}")
    print(display[available_columns].to_string(index=False))


def main() -> int:
    trade_ctx = None

    try:
        print(f"Connecting to FutuOpenD at {HOST}:{PORT}")
        print("A-SHARE SIMULATED ORDERS — READ-ONLY TEST")
        print("No order will be submitted or modified.\n")

        trade_ctx = OpenSecTradeContext(
            filter_trdmarket=TrdMarket.CN,
            host=HOST,
            port=PORT,
        )

        # 1. 找到唯一的 A 股模拟账户。
        ret, accounts = trade_ctx.get_acc_list()

        if ret != RET_OK:
            print(f"FAILED to query account list: {accounts}")
            return 1

        account = select_simulated_cn_account(accounts)
        account_id = int(account["acc_id"])

        print("Selected account:")
        print(f"  Account ID: {mask_account_id(account_id)}")
        print(f"  Environment: {account.get('trd_env', 'N/A')}")
        print(f"  Account type: {account.get('acc_type', 'N/A')}")
        print(f"  Status: {account.get('acc_status', 'N/A')}")

        # 2. 查询当前订单和近24小时相关订单。
        ret, current_orders = trade_ctx.order_list_query(
            order_market=TrdMarket.CN,
            trd_env=TrdEnv.SIMULATE,
            acc_id=account_id,
            refresh_cache=False,
        )

        if ret != RET_OK:
            print(f"FAILED to query current orders: {current_orders}")
            return 1

        print_orders(
            "CURRENT / RECENT ORDERS",
            current_orders,
        )

        # 3. 查询最近30天历史订单。
        end_time = datetime.now()
        start_time = end_time - timedelta(days=HISTORY_DAYS)

        start_text = start_time.strftime("%Y-%m-%d %H:%M:%S")
        end_text = end_time.strftime("%Y-%m-%d %H:%M:%S")

        print(
            f"\nHistorical query range: "
            f"{start_text} → {end_text}"
        )

        ret, historical_orders = (
            trade_ctx.history_order_list_query(
                order_market=TrdMarket.CN,
                start=start_text,
                end=end_text,
                trd_env=TrdEnv.SIMULATE,
                acc_id=account_id,
            )
        )

        if ret != RET_OK:
            print(
                "FAILED to query historical orders: "
                f"{historical_orders}"
            )
            return 1

        print_orders(
            f"HISTORICAL ORDERS — LAST {HISTORY_DAYS} DAYS",
            historical_orders,
        )

        print("\nREAD-ONLY CN ORDER QUERY TEST: PASS")
        return 0

    except Exception as exc:
        print(
            "\nTEST FAILED: "
            f"{type(exc).__name__}: {exc}"
        )
        return 1

    finally:
        if trade_ctx is not None:
            trade_ctx.close()
            print("A-share trade context closed.")


if __name__ == "__main__":
    raise SystemExit(main())