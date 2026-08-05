"""Account, funds and position queries for the one safe simulated account."""

from __future__ import annotations

from typing import Any

from .client import FutuClient
from .models import AccountSummary, FundsSummary, Position, number, rows, value
from .safety import select_unique_active_cn_simulated_account


class AccountService:
    def __init__(self, client: FutuClient) -> None:
        self.client = client

    def _account_row(self) -> Any:
        frame = self.client.ensure_ok(
            self.client.trade_context.get_acc_list(), "get_simulated_cn_account"
        )
        return select_unique_active_cn_simulated_account(
            rows(frame), self.client.config.account_id
        )

    def get_simulated_cn_account(self) -> AccountSummary:
        row = self._account_row()
        return AccountSummary(
            account_id=int(value(row, "acc_id")),
            environment="SIMULATE",
            market="CN",
            status=str(value(row, "acc_status", "ACTIVE")),
            account_type=str(value(row, "acc_type")) if value(row, "acc_type") is not None else None,
        )

    def get_funds(self) -> FundsSummary:
        account = self.get_simulated_cn_account()
        frame = self.client.ensure_ok(
            self.client.trade_context.accinfo_query(
                trd_env=self.client.sdk.TrdEnv.SIMULATE,
                acc_id=account.account_id,
                refresh_cache=False,
            ),
            "get_funds",
        )
        returned_rows = rows(frame)
        row = returned_rows[0] if returned_rows else {}
        return FundsSummary(
            total_assets=number(row, "total_assets"),
            market_value=number(row, "market_val"),
            cash=number(row, "cash") if number(row, "cash") is not None else number(row, "cn_cash"),
            buying_power=number(row, "power"),
            frozen_cash=number(row, "frozen_cash"),
            currency=str(value(row, "currency", "CNY")),
        )

    def get_positions(self) -> list[Position]:
        account = self.get_simulated_cn_account()
        frame = self.client.ensure_ok(
            self.client.trade_context.position_list_query(
                position_market=self.client.sdk.TrdMarket.CN,
                trd_env=self.client.sdk.TrdEnv.SIMULATE,
                acc_id=account.account_id,
                refresh_cache=False,
            ),
            "get_positions",
        )
        return [
            Position(
                code=str(value(row, "code", "")),
                name=str(value(row, "stock_name", "")),
                quantity=number(row, "qty") or 0.0,
                sellable_quantity=number(row, "can_sell_qty") or 0.0,
                current_price=number(row, "nominal_price"),
                cost_price=number(row, "cost_price"),
                market_value=number(row, "market_val"),
                profit_loss=number(row, "pl_val"),
                profit_loss_ratio=number(row, "pl_ratio"),
                currency=str(value(row, "currency")) if value(row, "currency") is not None else None,
            )
            for row in rows(frame)
        ]
