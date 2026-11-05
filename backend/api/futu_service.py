"""Thin, read-only HTTP-facing adapter over the existing Futu services."""

from __future__ import annotations

from collections.abc import Callable

from backend.futu import AccountService, FutuClient, OrderService
from backend.futu.exceptions import FutuConnectionError
from backend.futu.models import AccountSummary, FundsSummary, OrderRecord, Position
from backend.futu.safety import mask_identifier, require_cn_simulate

from .schemas import (
    FutuAccountResponse,
    FutuConnectionResponse,
    FutuOrderResponse,
    FutuOrdersResponse,
    FutuPortfolioResponse,
    FutuPositionResponse,
    FutuPositionsResponse,
)


class FutuReadService:
    """Expose only normalized reads; no order write method exists here."""

    def __init__(
        self,
        client_factory: Callable[[], FutuClient] = FutuClient,
        account_service_factory: Callable[[FutuClient], AccountService] = AccountService,
        order_service_factory: Callable[[FutuClient], OrderService] = OrderService,
    ) -> None:
        self._client_factory = client_factory
        self._account_service_factory = account_service_factory
        self._order_service_factory = order_service_factory

    @staticmethod
    def _enforce_read_boundary(client: FutuClient) -> None:
        require_cn_simulate(client.config.market, client.config.trading_environment)

    @staticmethod
    def _connection(account: AccountSummary) -> FutuConnectionResponse:
        return FutuConnectionResponse(
            connected=True,
            openD=True,
            market=account.market,
            environment=account.environment,
            accountStatus=account.status,
        )

    @staticmethod
    def _account(account: AccountSummary, funds: FundsSummary) -> FutuAccountResponse:
        return FutuAccountResponse(
            accountIdMasked=mask_identifier(account.account_id),
            market=account.market,
            environment=account.environment,
            accountType=account.account_type,
            status=account.status,
            totalAssets=funds.total_assets,
            cash=funds.cash,
            marketValue=funds.market_value,
        )

    @staticmethod
    def _position(position: Position) -> FutuPositionResponse:
        return FutuPositionResponse(
            code=position.code,
            name=position.name,
            quantity=position.quantity,
            canSellQuantity=position.sellable_quantity,
            price=position.current_price,
            costPrice=position.cost_price,
            marketValue=position.market_value,
            profitLoss=position.profit_loss,
            profitLossPercent=position.profit_loss_ratio,
        )

    @staticmethod
    def _order(order: OrderRecord) -> FutuOrderResponse:
        return FutuOrderResponse(
            orderIdMasked=mask_identifier(order.order_id),
            code=order.code,
            name=order.name,
            side=order.side,
            status=order.status,
            quantity=order.quantity,
            price=order.price,
            dealtQuantity=order.dealt_quantity,
            dealtAveragePrice=order.dealt_average_price,
            createdAt=order.created_at,
        )

    def status(self) -> FutuConnectionResponse:
        try:
            with self._client_factory() as client:
                self._enforce_read_boundary(client)
                if not client.health_check():
                    raise RuntimeError("FutuOpenD health check returned no state.")
                account = self._account_service_factory(client).get_simulated_cn_account()
                return self._connection(account)
        except Exception:
            return FutuConnectionResponse(
                connected=False,
                openD=False,
                market="CN",
                environment="SIMULATE",
                reason="FUTU_OPEND_UNAVAILABLE",
            )

    def account(self) -> FutuAccountResponse:
        with self._client_factory() as client:
            self._enforce_read_boundary(client)
            accounts = self._account_service_factory(client)
            account = accounts.get_simulated_cn_account()
            funds = accounts.get_funds()
            return self._account(account, funds)

    def positions(self) -> FutuPositionsResponse:
        with self._client_factory() as client:
            self._enforce_read_boundary(client)
            values = [
                self._position(position)
                for position in self._account_service_factory(client).get_positions()
            ]
            return FutuPositionsResponse(positions=values, count=len(values))

    def orders(self) -> FutuOrdersResponse:
        with self._client_factory() as client:
            self._enforce_read_boundary(client)
            values = [
                self._order(order)
                for order in self._order_service_factory(client).get_recent_orders()
            ]
            return FutuOrdersResponse(orders=values, count=len(values))

    def portfolio(self) -> FutuPortfolioResponse:
        with self._client_factory() as client:
            self._enforce_read_boundary(client)
            if not client.health_check():
                raise FutuConnectionError("FutuOpenD health check returned no state.")
            accounts = self._account_service_factory(client)
            account = accounts.get_simulated_cn_account()
            funds = accounts.get_funds()
            positions = [self._position(item) for item in accounts.get_positions()]
            orders = [
                self._order(item)
                for item in self._order_service_factory(client).get_recent_orders()
            ]
            return FutuPortfolioResponse(
                connection=self._connection(account),
                account=self._account(account, funds),
                positions=positions,
                orders=orders,
            )


_futu_read_service = FutuReadService()


def get_futu_read_service() -> FutuReadService:
    return _futu_read_service
