"""Read-only market quote service."""

from __future__ import annotations

from .client import FutuClient
from .code_mapper import validate_futu_code
from .exceptions import FutuApiError
from .models import QuoteSnapshot, number, rows, value


class QuoteService:
    def __init__(self, client: FutuClient) -> None:
        self.client = client

    def get_snapshot(self, codes: list[str]) -> list[QuoteSnapshot]:
        normalized = [validate_futu_code(code) for code in codes]
        if not normalized:
            return []
        frame = self.client.ensure_ok(
            self.client.quote_context.get_market_snapshot(normalized), "get_snapshot"
        )
        snapshots: list[QuoteSnapshot] = []
        for row in rows(frame):
            price = number(row, "last_price")
            lot_size = number(row, "lot_size")
            if price is None or lot_size is None:
                raise FutuApiError("Snapshot is missing last_price or lot_size.")
            snapshots.append(
                QuoteSnapshot(
                    code=validate_futu_code(str(value(row, "code"))),
                    name=str(value(row, "name", "")),
                    last_price=price,
                    lot_size=int(lot_size),
                    suspended=bool(value(row, "suspension", False)),
                    update_time=str(value(row, "update_time")) if value(row, "update_time") else None,
                )
            )
        return snapshots

    def get_lot_size(self, code: str) -> int:
        snapshots = self.get_snapshot([code])
        if len(snapshots) != 1:
            raise FutuApiError(f"Expected one snapshot for {code!r}.")
        return snapshots[0].lot_size
