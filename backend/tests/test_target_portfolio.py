from __future__ import annotations

import unittest

from backend.execution.target_portfolio import derive_topk_dropout_transition

from backend.tests.execution_test_helpers import metadata, signals


class TargetPortfolioTests(unittest.TestCase):
    def test_empty_portfolio_enters_top_five(self) -> None:
        transition = derive_topk_dropout_transition(signals(), set(), metadata())
        self.assertEqual(transition.buy, tuple(item.code for item in signals()[:5]))
        self.assertFalse(transition.sell)

    def test_one_bottom_holding_is_replaced(self) -> None:
        current = {"SH600000", "SH600009", "SH600010", "SH600011", "SH600018"}
        transition = derive_topk_dropout_transition(signals(), current, metadata())
        self.assertEqual(transition.sell, ("SH600018",))
        self.assertEqual(transition.buy, ("SH600015",))
        self.assertEqual(len(transition.keep), 4)

    def test_no_replacement_when_outsider_does_not_beat_current_bottom(self) -> None:
        current = {item.code for item in signals()[:5]}
        transition = derive_topk_dropout_transition(signals(), current, metadata())
        self.assertFalse(transition.sell)
        self.assertFalse(transition.buy)

    def test_retained_holdings_are_membership_only_not_equal_weight_targets(self) -> None:
        current = {"SH600000", "SH600009", "SH600010", "SH600011", "SH600018"}
        transition = derive_topk_dropout_transition(signals(), current, metadata())
        self.assertIn("SH600000", transition.keep)
        self.assertFalse(hasattr(transition, "weights"))


if __name__ == "__main__":
    unittest.main()
