"""Explicit, read-only integration smoke test for a running FutuOpenD."""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any

from .account_service import AccountService
from .client import FutuClient
from .config import FutuConfig
from .order_service import OrderService
from .quote_service import QuoteService
from .safety import mask_identifier


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, indent=2)


def main() -> int:
    """Read FutuOpenD state. This command cannot place or cancel an order."""
    config = FutuConfig.from_env()
    try:
        with FutuClient(config) as client:
            accounts = AccountService(client)
            quotes = QuoteService(client)
            orders = OrderService(client)

            print(f"FutuOpenD health: {'OK' if client.health_check() else 'UNKNOWN'}")
            account = accounts.get_simulated_cn_account()
            print(
                "Account: "
                + _safe_json(
                    {
                        "account_id": mask_identifier(account.account_id),
                        "environment": account.environment,
                        "market": account.market,
                        "status": account.status,
                        "account_type": account.account_type,
                    }
                )
            )
            print("Funds: " + _safe_json(asdict(accounts.get_funds())))
            print("Positions: " + _safe_json([asdict(item) for item in accounts.get_positions()]))
            print(
                "Quote snapshot: "
                + _safe_json([asdict(item) for item in quotes.get_snapshot(["SZ.000001"])])
            )
            recent = [asdict(item) for item in orders.get_recent_orders()]
            historical = [asdict(item) for item in orders.get_historical_orders()]
            for collection in (recent, historical):
                for order in collection:
                    order["order_id"] = mask_identifier(order["order_id"], visible=6)
            print("Recent orders: " + _safe_json(recent))
            print("Historical orders: " + _safe_json(historical))
        print("READ-ONLY CN SIMULATE SMOKE TEST: PASS")
        return 0
    except Exception as exc:
        print(f"READ-ONLY CN SIMULATE SMOKE TEST: FAIL: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
