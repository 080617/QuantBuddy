from __future__ import annotations

from typing import Any

from futu import (
    OpenSecTradeContext,
    RET_OK,
    TrdEnv,
    TrdMarket,
)


HOST = "127.0.0.1"
PORT = 11111


def mask_account_id(value: Any) -> str:
    """仅显示账户 ID 后四位。"""
    text = str(value)

    if len(text) <= 4:
        return "****"

    return f"{'*' * (len(text) - 4)}{text[-4:]}"


def print_existing_fields(
    row: Any,
    fields: list[tuple[str, str]],
) -> None:
    """仅打印当前 SDK 实际返回的字段。"""
    for field_name, label in fields:
        if field_name in row.index:
            print(f"  {label}: {row[field_name]}")


def main() -> int:
    trade_ctx = None

    try:
        print(f"Connecting to FutuOpenD at {HOST}:{PORT}")
        print("A-SHARE SIMULATED ACCOUNT — READ-ONLY TEST")
        print("No order will be submitted.\n")

        trade_ctx = OpenSecTradeContext(
            filter_trdmarket=TrdMarket.CN,
            host=HOST,
            port=PORT,
        )

        # 1. 获取账户列表，不把账户 ID 手工写入代码。
        ret, accounts = trade_ctx.get_acc_list()

        if ret != RET_OK:
            print(f"FAILED to get account list: {accounts}")
            return 1

        if accounts is None or accounts.empty:
            print("FAILED: No A-share account was returned.")
            return 1

        # 只接受 CN + SIMULATE + ACTIVE。
        simulated_accounts = accounts[
            (accounts["trd_env"] == TrdEnv.SIMULATE)
            & accounts["trdmarket_auth"].apply(
                lambda markets: TrdMarket.CN in markets
            )
        ]

        if "acc_status" in simulated_accounts.columns:
            simulated_accounts = simulated_accounts[
                simulated_accounts["acc_status"].astype(str) == "ACTIVE"
            ]

        if simulated_accounts.empty:
            print("FAILED: No active A-share simulated account found.")
            return 1

        if len(simulated_accounts) > 1:
            print(
                "SAFETY STOP: More than one active A-share "
                "simulated account was found."
            )
            return 2

        selected_account = simulated_accounts.iloc[0]
        account_id = int(selected_account["acc_id"])

        print("Selected account:")
        print(f"  Account ID: {mask_account_id(account_id)}")
        print(f"  Environment: {selected_account.get('trd_env', 'N/A')}")
        print(f"  Account type: {selected_account.get('acc_type', 'N/A')}")
        print(
            "  Market authorization: "
            f"{selected_account.get('trdmarket_auth', 'N/A')}"
        )
        print(f"  Status: {selected_account.get('acc_status', 'N/A')}")

        # 二次安全检查。
        if selected_account.get("trd_env") != TrdEnv.SIMULATE:
            print("SAFETY STOP: Selected account is not SIMULATE.")
            return 2

        # 2. 查询资金。
        print("\n" + "=" * 60)
        print("ACCOUNT FUNDS")
        print("=" * 60)

        ret, funds = trade_ctx.accinfo_query(
            trd_env=TrdEnv.SIMULATE,
            acc_id=account_id,
            refresh_cache=False,
        )

        if ret != RET_OK:
            print(f"FAILED to query account funds: {funds}")
            return 1

        if funds is None or funds.empty:
            print("No account fund data returned.")
        else:
            fund_row = funds.iloc[0]

            print_existing_fields(
                fund_row,
                [
                    ("total_assets", "Total assets"),
                    ("market_val", "Securities market value"),
                    ("cash", "Cash"),
                    ("cn_cash", "CNY cash"),
                    ("power", "Buying power"),
                    ("cnh_net_cash_power", "CNY cash buying power"),
                    ("frozen_cash", "Frozen cash"),
                    (
                        "avl_withdrawal_cash",
                        "Withdrawable cash",
                    ),
                    ("risk_status", "Risk status"),
                ],
            )

        # 3. 查询 A 股持仓。
        print("\n" + "=" * 60)
        print("A-SHARE POSITIONS")
        print("=" * 60)

        ret, positions = trade_ctx.position_list_query(
            position_market=TrdMarket.CN,
            trd_env=TrdEnv.SIMULATE,
            acc_id=account_id,
            refresh_cache=False,
        )

        if ret != RET_OK:
            print(f"FAILED to query positions: {positions}")
            return 1

        if positions is None or positions.empty:
            print(
                "The A-share simulated account currently "
                "has no positions."
            )
        else:
            print(f"Position count: {len(positions)}")

            wanted_columns = [
                "code",
                "stock_name",
                "qty",
                "can_sell_qty",
                "nominal_price",
                "cost_price",
                "market_val",
                "pl_val",
                "pl_ratio",
                "currency",
            ]

            available_columns = [
                column
                for column in wanted_columns
                if column in positions.columns
            ]

            print(
                positions[available_columns].to_string(
                    index=False
                )
            )

        print("\nREAD-ONLY CN FUNDS AND POSITIONS TEST: PASS")
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