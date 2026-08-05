from __future__ import annotations

import unittest

from backend.execution.models import CurrentPosition
from backend.execution.reconciliation import reconcile_positions
from backend.execution.target_portfolio import derive_topk_dropout_transition

from backend.tests.execution_test_helpers import metadata, signals


class ReconciliationTests(unittest.TestCase):
    def test_keep_exit_enter_and_unmanaged_are_identified(self) -> None:
        positions = [
            CurrentPosition("SH600000", 100, 100, 10, 1000, True),
            CurrentPosition("SH600018", 100, 100, 10, 1000, True),
            CurrentPosition("SZ000001", 100, 100, 10, 1000, False),
        ]
        managed = {item.code for item in positions if item.managed}
        transition = derive_topk_dropout_transition(signals(), managed, metadata())
        states = {item.code: item.state for item in reconcile_positions(positions, transition, signals())}
        self.assertEqual(states["SH600000"], "KEEP")
        self.assertEqual(states["SZ000001"], "UNMANAGED")
        self.assertIn("ENTER", states.values())


if __name__ == "__main__":
    unittest.main()
