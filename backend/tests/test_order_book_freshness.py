from __future__ import annotations

from datetime import datetime, timezone
import inspect
import unittest

from backend.futu.client import FutuClient
from backend.futu.quote_service import QuoteService


NOW = datetime(2026, 8, 6, 5, 50, tzinfo=timezone.utc)  # 13:50 Asia/Shanghai


class FakeSdk:
    RET_OK = 0

    class SubType:
        ORDER_BOOK = "ORDER_BOOK"


class BookContext:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.subscribe_count = 0
        self.read_count = 0
        self.closed = False

    def subscribe(self, codes, subtypes, is_first_push=False):
        self.subscribe_count += 1
        return 0, None

    def get_order_book(self, code, num=1):
        self.read_count += 1
        payload = self.payloads.pop(0) if len(self.payloads) > 1 else self.payloads[0]
        return 0, payload

    def close(self):
        self.closed = True


class FakeClient:
    sdk = FakeSdk()

    def __init__(self, context):
        self.quote_context = context

    def ensure_ok(self, result, operation):
        code, payload = result
        if code != 0:
            raise RuntimeError(operation)
        return payload


def payload(*, ask=102.55, ask_time="2026-08-06 13:50:00"):
    asks = [] if ask is None else [(ask, 1000)]
    return {"Ask": asks, "svr_recv_time_ask": ask_time}


def acquire(payloads, *, sleeper=lambda _seconds: None):
    context = BookContext(payloads)
    result = QuoteService(FakeClient(context)).acquire_fresh_order_book_top(
        "SZ.000988", clock=lambda: NOW, sleeper=sleeper
    )
    return result, context


class OrderBookFreshnessTests(unittest.TestCase):
    def test_01_missing_first_time_then_fresh_passes(self):
        result, context = acquire([payload(ask_time=""), payload()])
        self.assertIsNotNone(result.order_book)
        self.assertEqual(result.diagnostics.order_book_attempt_count, 2)
        self.assertIsNone(result.diagnostics.first_order_book_ask_time)
        self.assertEqual(context.read_count, 2)

    def test_02_stale_first_time_then_fresh_passes(self):
        result, _ = acquire([payload(ask_time="2026-08-06 13:49:00"), payload()])
        self.assertIsNotNone(result.order_book)
        self.assertEqual(result.diagnostics.final_order_book_age_seconds, 0)

    def test_03_ten_missing_times_returns_stale_diagnostic(self):
        result, context = acquire([payload(ask_time="")] * 10)
        self.assertIsNone(result.order_book)
        self.assertEqual(result.diagnostics.order_book_attempt_count, 10)
        self.assertEqual(context.read_count, 10)

    def test_04_empty_ask_never_passes(self):
        result, _ = acquire([payload(ask=None)] * 10)
        self.assertIsNone(result.order_book)
        self.assertIsNone(result.diagnostics.best_ask)

    def test_05_non_positive_best_ask_never_passes(self):
        result, _ = acquire([payload(ask=0)] * 10)
        self.assertIsNone(result.order_book)
        self.assertEqual(result.diagnostics.best_ask, 0)

    def test_06_older_than_fifteen_seconds_never_passes(self):
        result, _ = acquire([payload(ask_time="2026-08-06 13:49:44")] * 10)
        self.assertIsNone(result.order_book)
        self.assertEqual(result.diagnostics.final_order_book_age_seconds, 16)
        self.assertEqual(result.diagnostics.freshness_threshold_seconds, 15)

    def test_07_snapshot_or_last_price_is_not_a_fallback(self):
        source = inspect.getsource(QuoteService.acquire_fresh_order_book_top)
        self.assertNotIn("last_price", source)
        self.assertNotIn("get_snapshot", source)

    def test_08_waiting_uses_the_existing_quote_context(self):
        result, context = acquire([payload(ask_time=""), payload()])
        self.assertIsNotNone(result.order_book)
        self.assertEqual(context.subscribe_count, 1)
        self.assertEqual(context.read_count, 2)

    def test_09_order_book_is_subscribed_exactly_once(self):
        _, context = acquire([payload(ask_time="")] * 10)
        self.assertEqual(context.subscribe_count, 1)

    def test_10_context_closes_after_timeout(self):
        context = BookContext([payload(ask_time="")] * 10)
        with FutuClient(
            sdk=FakeSdk(), quote_context_factory=lambda **_kwargs: context
        ) as client:
            result = QuoteService(client).acquire_fresh_order_book_top(
                "SZ.000988", clock=lambda: NOW, sleeper=lambda _seconds: None
            )
            self.assertIsNone(result.order_book)
            self.assertFalse(context.closed)
        self.assertTrue(context.closed)

    def test_11_acquisition_never_calls_place_order(self):
        source = inspect.getsource(QuoteService.acquire_fresh_order_book_top)
        self.assertNotIn("place_order", source)

    def test_12_acquisition_never_calls_cancel_or_modify(self):
        source = inspect.getsource(QuoteService.acquire_fresh_order_book_top)
        self.assertNotIn("cancel", source)
        self.assertNotIn("modify_order", source)


if __name__ == "__main__":
    unittest.main()
