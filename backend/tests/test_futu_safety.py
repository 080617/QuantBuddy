from __future__ import annotations

import unittest

from backend.futu.config import FutuConfig
from backend.futu.exceptions import AccountSelectionError, FutuConfigurationError, FutuSafetyError
from backend.futu.safety import (
    require_cn_simulate,
    select_unique_active_cn_simulated_account,
    validate_maximum_quantity,
    validate_order_input,
)


ACTIVE_CN = {
    "acc_id": 1001,
    "trd_env": "SIMULATE",
    "acc_status": "ACTIVE",
    "trdmarket_auth": ["CN"],
}


class SafetyTests(unittest.TestCase):
    def test_real_environment_is_rejected(self) -> None:
        with self.assertRaises(FutuSafetyError):
            require_cn_simulate("CN", "REAL")
        with self.assertRaises(FutuConfigurationError):
            FutuConfig(trading_environment="REAL")

    def test_non_cn_market_is_rejected(self) -> None:
        with self.assertRaises(FutuSafetyError):
            require_cn_simulate("HK", "SIMULATE")

    def test_non_active_account_is_rejected(self) -> None:
        account = dict(ACTIVE_CN, acc_status="DISABLED")
        with self.assertRaises(AccountSelectionError):
            select_unique_active_cn_simulated_account([account])

    def test_missing_status_or_market_authorization_is_rejected(self) -> None:
        missing_status = dict(ACTIVE_CN)
        missing_status.pop("acc_status")
        missing_market = dict(ACTIVE_CN)
        missing_market.pop("trdmarket_auth")
        for account in (missing_status, missing_market):
            with self.subTest(account=account), self.assertRaises(AccountSelectionError):
                select_unique_active_cn_simulated_account([account])

    def test_multiple_accounts_trigger_safety_stop(self) -> None:
        with self.assertRaises(AccountSelectionError):
            select_unique_active_cn_simulated_account([ACTIVE_CN, dict(ACTIVE_CN, acc_id=1002)])

    def test_writes_are_disabled_by_default(self) -> None:
        with self.assertRaisesRegex(FutuSafetyError, "disabled"):
            validate_order_input(
                config=FutuConfig(), code="SH.600104", quantity=100, price=10, lot_size=100
            )

    def test_non_lot_quantity_is_rejected(self) -> None:
        config = FutuConfig(enable_simulated_orders=True)
        with self.assertRaisesRegex(FutuSafetyError, "lot_size"):
            validate_order_input(
                config=config, code="SH.600104", quantity=101, price=10, lot_size=100
            )

    def test_invalid_quantity_price_and_amount_are_rejected(self) -> None:
        config = FutuConfig(enable_simulated_orders=True, max_simulated_order_amount=2_000)
        with self.assertRaises(FutuSafetyError):
            validate_order_input(config=config, code="SH.600104", quantity=0, price=10, lot_size=100)
        with self.assertRaises(FutuSafetyError):
            validate_order_input(config=config, code="SH.600104", quantity=100, price=0, lot_size=100)
        with self.assertRaisesRegex(FutuSafetyError, "amount limit"):
            validate_order_input(config=config, code="SH.600104", quantity=300, price=10, lot_size=100)

    def test_maximum_tradable_quantity_is_enforced(self) -> None:
        with self.assertRaisesRegex(FutuSafetyError, "exceeds"):
            validate_maximum_quantity(200, 100)


if __name__ == "__main__":
    unittest.main()
