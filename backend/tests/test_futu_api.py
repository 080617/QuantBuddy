"""Unit tests for the read-only Futu HTTP boundary."""

from __future__ import annotations

from types import SimpleNamespace
import unittest

from fastapi.testclient import TestClient

from backend.api.futu_service import FutuReadService, get_futu_read_service
from backend.api.main import app
from backend.api.schemas import (
    FutuAccountResponse,
    FutuConnectionResponse,
    FutuOrderResponse,
    FutuOrdersResponse,
    FutuPortfolioResponse,
    FutuPositionResponse,
    FutuPositionsResponse,
)
from backend.futu.exceptions import FutuConnectionError
from backend.futu.models import AccountSummary, FundsSummary, OrderRecord, Position


ACCOUNT = AccountSummary(
    account_id=1234562058,
    environment="SIMULATE",
    market="CN",
    status="ACTIVE",
    account_type="CASH",
)
FUNDS = FundsSummary(
    total_assets=100_000.0,
    market_value=25_000.0,
    cash=75_000.0,
    buying_power=75_000.0,
    frozen_cash=0.0,
)
POSITION = Position(
    code="SH.600104",
    name="上汽集团",
    quantity=100.0,
    sellable_quantity=100.0,
    current_price=12.5,
    cost_price=12.0,
    market_value=1250.0,
    profit_loss=50.0,
    profit_loss_ratio=4.17,
    currency="CNY",
)
ORDER = OrderRecord(
    order_id="9876543210",
    code="SH.600104",
    name="上汽集团",
    side="BUY",
    order_type="NORMAL",
    status="CANCELLED_ALL",
    quantity=100.0,
    price=12.0,
    dealt_quantity=0.0,
    dealt_average_price=None,
    created_at="2026-08-01 10:00:00",
    updated_at="2026-08-01 10:01:00",
    error_message=None,
)


class FakeClient:
    def __init__(self) -> None:
        self.config = SimpleNamespace(market="CN", trading_environment="SIMULATE")
        self.closed = False

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.closed = True

    def health_check(self) -> bool:
        return True


class FakeAccountService:
    def __init__(self, _: FakeClient) -> None:
        pass

    def get_simulated_cn_account(self) -> AccountSummary:
        return ACCOUNT

    def get_funds(self) -> FundsSummary:
        return FUNDS

    def get_positions(self) -> list[Position]:
        return [POSITION]


class FakeOrderService:
    def __init__(self, _: FakeClient) -> None:
        pass

    def get_recent_orders(self) -> list[OrderRecord]:
        return [ORDER]


def build_service() -> FutuReadService:
    return FutuReadService(
        client_factory=FakeClient,  # type: ignore[arg-type]
        account_service_factory=FakeAccountService,  # type: ignore[arg-type]
        order_service_factory=FakeOrderService,  # type: ignore[arg-type]
    )


class StubReadService:
    def __init__(self) -> None:
        self.connection = FutuConnectionResponse(
            connected=True,
            openD=True,
            market="CN",
            environment="SIMULATE",
            accountStatus="ACTIVE",
        )
        self.account_value = FutuAccountResponse(
            accountIdMasked="******2058",
            market="CN",
            environment="SIMULATE",
            accountType="CASH",
            status="ACTIVE",
            totalAssets=100_000.0,
            cash=75_000.0,
            marketValue=25_000.0,
        )
        self.position = FutuPositionResponse(
            code="SH.600104",
            name="上汽集团",
            quantity=100,
            canSellQuantity=100,
            price=12.5,
            costPrice=12.0,
            marketValue=1250,
            profitLoss=50,
            profitLossPercent=4.17,
        )
        self.order = FutuOrderResponse(
            orderIdMasked="******3210",
            code="SH.600104",
            name="上汽集团",
            side="BUY",
            status="CANCELLED_ALL",
            quantity=100,
            price=12,
            dealtQuantity=0,
            createdAt="2026-08-01 10:00:00",
        )

    def status(self) -> FutuConnectionResponse:
        return self.connection

    def account(self) -> FutuAccountResponse:
        return self.account_value

    def positions(self) -> FutuPositionsResponse:
        return FutuPositionsResponse(positions=[self.position], count=1)

    def orders(self) -> FutuOrdersResponse:
        return FutuOrdersResponse(orders=[self.order], count=1)

    def portfolio(self) -> FutuPortfolioResponse:
        return FutuPortfolioResponse(
            connection=self.connection,
            account=self.account_value,
            positions=[self.position],
            orders=[self.order],
        )


class FutuReadServiceTests(unittest.TestCase):
    def test_normalizes_and_masks_account_and_order_identifiers(self) -> None:
        service = build_service()
        account = service.account()
        orders = service.orders()
        self.assertEqual(account.accountIdMasked, "******2058")
        self.assertNotIn(str(ACCOUNT.account_id), account.model_dump_json())
        self.assertEqual(orders.orders[0].orderIdMasked, "******3210")
        self.assertNotIn(ORDER.order_id, orders.model_dump_json())

    def test_status_handles_opend_unavailable(self) -> None:
        def unavailable() -> FakeClient:
            raise FutuConnectionError("offline")

        status = FutuReadService(client_factory=unavailable).status()  # type: ignore[arg-type]
        self.assertFalse(status.connected)
        self.assertEqual(status.reason, "FUTU_OPEND_UNAVAILABLE")

    def test_portfolio_reuses_one_client_context(self) -> None:
        clients: list[FakeClient] = []

        def factory() -> FakeClient:
            client = FakeClient()
            clients.append(client)
            return client

        service = FutuReadService(
            client_factory=factory,  # type: ignore[arg-type]
            account_service_factory=FakeAccountService,  # type: ignore[arg-type]
            order_service_factory=FakeOrderService,  # type: ignore[arg-type]
        )
        portfolio = service.portfolio()
        self.assertEqual(len(clients), 1)
        self.assertTrue(clients[0].closed)
        self.assertEqual(portfolio.connection.environment, "SIMULATE")


class FutuApiRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stub = StubReadService()
        app.dependency_overrides[get_futu_read_service] = lambda: cls.stub
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.clear()

    def test_all_read_endpoints_return_json(self) -> None:
        for path in ("status", "account", "positions", "orders", "portfolio"):
            response = self.client.get(f"/api/futu/{path}")
            self.assertEqual(response.status_code, 200, path)
            self.assertIsInstance(response.json(), dict)

    def test_cors_is_restricted_to_frontend_origin(self) -> None:
        allowed = self.client.options(
            "/api/futu/status",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        denied = self.client.options(
            "/api/futu/status",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(allowed.headers.get("access-control-allow-origin"), "http://localhost:3000")
        self.assertNotEqual(denied.headers.get("access-control-allow-origin"), "*")
        self.assertIsNone(denied.headers.get("access-control-allow-origin"))

    def test_no_http_order_write_operation_is_exposed(self) -> None:
        routes = app.openapi()["paths"]
        self.assertEqual(set(routes), {
            "/api/futu/status",
            "/api/futu/account",
            "/api/futu/positions",
            "/api/futu/orders",
            "/api/futu/portfolio",
        })
        for methods in routes.values():
            self.assertEqual(set(methods), {"get"})


if __name__ == "__main__":
    unittest.main()

