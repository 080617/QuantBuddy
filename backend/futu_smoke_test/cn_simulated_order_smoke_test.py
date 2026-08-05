from __future__ import annotations

import argparse
import math
import time
from decimal import Decimal, ROUND_DOWN
from typing import Any

import pandas as pd
from futu import (
    ModifyOrderOp,
    OpenQuoteContext,
    OpenSecTradeContext,
    OrderType,
    RET_OK,
    TrdEnv,
    TrdMarket,
    TrdSide,
)


HOST = "127.0.0.1"
PORT = 11111

TEST_CODE = "SZ.000001"
EXPECTED_NAME = "平安银行"
EXECUTE_FLAG = "--execute-simulated-order"
CONFIRMATION_TEXT = "PLACE SIMULATED ORDER"


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
            "Safety stop: expected exactly one active CN "
            f"simulated account, found {len(selected)}."
        )

    account = selected.iloc[0]

    if account.get("trd_env") != TrdEnv.SIMULATE:
        raise RuntimeError(
            "Safety stop: selected account is not SIMULATE."
        )

    return account


def round_down_to_tick(
    price: float,
    tick: float,
) -> float:
    price_decimal = Decimal(str(price))
    tick_decimal = Decimal(str(tick))

    units = (
        price_decimal / tick_decimal
    ).quantize(Decimal("1"), rounding=ROUND_DOWN)

    return float(units * tick_decimal)


def query_order(
    trade_ctx: OpenSecTradeContext,
    account_id: int,
    order_id: str,
) -> pd.DataFrame | None:
    ret, data = trade_ctx.order_list_query(
        order_id=order_id,
        order_market=TrdMarket.CN,
        trd_env=TrdEnv.SIMULATE,
        acc_id=account_id,
        refresh_cache=False,
    )

    if ret != RET_OK:
        print(f"Order query failed: {data}")
        return None

    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "QuantBuddy A-share simulated order smoke test. "
            "Dry-run by default."
        )
    )
    parser.add_argument(
        EXECUTE_FLAG,
        action="store_true",
        help="Actually place one simulated order and cancel it.",
    )
    args = parser.parse_args()

    quote_ctx = None
    trade_ctx = None

    try:
        print(f"Connecting to FutuOpenD at {HOST}:{PORT}")
        print("A-SHARE SIMULATED ORDER SMOKE TEST")

        if args.execute_simulated_order:
            print("MODE: EXECUTE — SIMULATED ACCOUNT ONLY")
        else:
            print("MODE: DRY RUN — NO ORDER WILL BE SUBMITTED")

        # 1. 获取行情。
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

        stock_name = str(snapshot.get("name", ""))
        last_price = float(snapshot["last_price"])
        prev_close = float(snapshot["prev_close_price"])
        lot_size = int(snapshot["lot_size"])
        tick_size = float(snapshot.get("price_spread", 0.01))
        suspended = bool(snapshot.get("suspension", False))

        if stock_name != EXPECTED_NAME:
            print(
                "SAFETY STOP: unexpected stock identity: "
                f"{stock_name}"
            )
            return 2

        if suspended:
            print("SAFETY STOP: security is suspended.")
            return 2

        if last_price <= 0 or prev_close <= 0:
            print("SAFETY STOP: invalid market price.")
            return 2

        if lot_size <= 0:
            print("SAFETY STOP: invalid lot size.")
            return 2

        if tick_size <= 0:
            tick_size = 0.01

        # 使用明显低于当前价、但不过度偏离昨收价的测试价格。
        candidate_price = max(
            last_price * 0.95,
            prev_close * 0.91,
        )

        test_price = round_down_to_tick(
            candidate_price,
            tick_size,
        )

        test_qty = lot_size
        estimated_value = test_price * test_qty
        discount = (
            (test_price / last_price) - 1
        ) * 100

        print("\nPlanned simulated order:")
        print(f"  Code: {TEST_CODE}")
        print(f"  Name: {stock_name}")
        print(f"  Latest price: {last_price:.2f}")
        print(f"  Previous close: {prev_close:.2f}")
        print(f"  Price tick: {tick_size}")
        print(f"  Quantity: {test_qty}")
        print(f"  Limit price: {test_price:.2f}")
        print(
            "  Difference from latest price: "
            f"{discount:.2f}%"
        )
        print(
            "  Estimated simulated amount: "
            f"{estimated_value:,.2f} CNY"
        )

        # 2. 获取模拟账户。
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
        print(f"  Environment: {account.get('trd_env')}")
        print(f"  Account type: {account.get('acc_type')}")
        print(f"  Status: {account.get('acc_status')}")

        # 3. 再次验证测试价格下至少可以买一手。
        ret, trading_info = trade_ctx.acctradinginfo_query(
            order_type=OrderType.NORMAL,
            code=TEST_CODE,
            price=test_price,
            trd_env=TrdEnv.SIMULATE,
            acc_id=account_id,
        )

        if ret != RET_OK:
            print(
                "FAILED to query tradable quantity: "
                f"{trading_info}"
            )
            return 1

        if trading_info is None or trading_info.empty:
            print("FAILED: no tradable quantity data returned.")
            return 1

        max_cash_buy = float(
            trading_info.iloc[0]["max_cash_buy"]
        )

        print(f"\nMaximum cash buy at test price: {max_cash_buy}")

        if max_cash_buy < test_qty:
            print(
                "SAFETY STOP: account cannot buy one board lot "
                "at the planned price."
            )
            return 2

        # 默认只运行到这里。
        if not args.execute_simulated_order:
            print("\nDRY RUN: PASS")
            print("No order was submitted.")
            print(
                "Review the order plan before using "
                f"{EXECUTE_FLAG}."
            )
            return 0

        # 4. 执行模式需要人工输入完整确认语句。
        print("\nThis will affect only the SIMULATE account.")
        typed = input(
            f'Type exactly "{CONFIRMATION_TEXT}" to continue: '
        )

        if typed != CONFIRMATION_TEXT:
            print("Confirmation did not match. No order submitted.")
            return 2

        # 5. 提交一手模拟限价单。
        ret, order_data = trade_ctx.place_order(
            price=test_price,
            qty=test_qty,
            code=TEST_CODE,
            trd_side=TrdSide.BUY,
            order_type=OrderType.NORMAL,
            trd_env=TrdEnv.SIMULATE,
            acc_id=account_id,
        )

        if ret != RET_OK:
            print(f"SIMULATED ORDER FAILED: {order_data}")
            return 1

        if order_data is None or order_data.empty:
            print("FAILED: no order result returned.")
            return 1

        order_id = str(order_data.iloc[0]["order_id"])

        print("\nSIMULATED ORDER SUBMITTED")
        print(f"  Order ID suffix: ...{order_id[-6:]}")
        print(
            f"  Initial status: "
            f"{order_data.iloc[0].get('order_status', 'N/A')}"
        )

        # 给服务器短暂时间更新状态。
        time.sleep(1.5)

        queried = query_order(
            trade_ctx,
            account_id,
            order_id,
        )

        dealt_qty = 0.0

        if queried is not None and not queried.empty:
            row = queried.iloc[0]
            dealt_qty = float(row.get("dealt_qty", 0) or 0)

            print("\nStatus before cancellation:")
            print(f"  Status: {row.get('order_status', 'N/A')}")
            print(f"  Dealt quantity: {dealt_qty}")
            print(
                f"  Average dealt price: "
                f"{row.get('dealt_avg_price', 0)}"
            )

        if dealt_qty > 0:
            print(
                "\nWARNING: The simulated order was partially "
                "or fully filled before cancellation."
            )

        # 6. 撤销尚未成交部分。
        ret, cancel_data = trade_ctx.modify_order(
            modify_order_op=ModifyOrderOp.CANCEL,
            order_id=order_id,
            qty=0,
            price=0,
            trd_env=TrdEnv.SIMULATE,
            acc_id=account_id,
        )

        if ret != RET_OK:
            print(f"CANCEL REQUEST FAILED: {cancel_data}")
            return 1

        print("\nCANCEL REQUEST: ACCEPTED")

        time.sleep(1.5)

        final_order = query_order(
            trade_ctx,
            account_id,
            order_id,
        )

        if final_order is not None and not final_order.empty:
            row = final_order.iloc[0]

            print("\nFinal order state:")
            print(f"  Status: {row.get('order_status', 'N/A')}")
            print(f"  Quantity: {row.get('qty', 'N/A')}")
            print(f"  Dealt quantity: {row.get('dealt_qty', 'N/A')}")
            print(f"  Price: {row.get('price', 'N/A')}")
            print(
                f"  Last error: "
                f"{row.get('last_err_msg', '')}"
            )

        print(
            "\nSIMULATED PLACE-AND-CANCEL TEST: PASS"
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