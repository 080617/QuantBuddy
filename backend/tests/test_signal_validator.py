from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
import tempfile
import unittest

from backend.execution.exceptions import ArtifactError
from backend.execution.models import PlanningConfig, SignalRecord
from backend.execution.signal_validator import validate_execution_artifact

from backend.tests.execution_test_helpers import artifact, metadata, signals


class SignalValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.root = Path(self.temp.name)
        calendar = self.root / "data/qlib/cn_data/calendars/day.txt"
        universe = self.root / "data/qlib/cn_data/instruments/csi300.txt"
        calendar.parent.mkdir(parents=True)
        universe.parent.mkdir(parents=True)
        calendar.write_text("2026-07-30\n2026-07-31\n", encoding="utf-8")
        universe.write_text(
            "".join(f"{item.code}\t2020-01-01\t2026-12-31\n" for item in signals()), encoding="utf-8"
        )
        self.config = PlanningConfig(max_signal_age_calendar_days=3)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def validate(self, item, as_of=date(2026, 7, 31)):
        return validate_execution_artifact(
            item, project_root=self.root, config=self.config, as_of=as_of, verify_source_hash=False
        )

    def test_valid_artifact_resolves_next_qlib_session(self) -> None:
        result = self.validate(artifact())
        self.assertEqual(result.planned_execution_date, "2026-07-31")
        self.assertFalse(result.blockers)

    def test_mock_and_frontend_sources_are_rejected(self) -> None:
        with self.assertRaises(ArtifactError):
            self.validate(artifact(is_mock=True))
        with self.assertRaises(ArtifactError):
            self.validate(artifact(source_artifact=["frontend/public/data/dashboard_v1/latest_signals.json"]))

    def test_stale_signal_is_non_executable_blocker(self) -> None:
        result = self.validate(artifact(), as_of=date(2026, 8, 5))
        self.assertIn("STALE_SIGNAL", {item.code for item in result.blockers})

    def test_missing_next_calendar_date_is_not_invented(self) -> None:
        calendar = self.root / "data/qlib/cn_data/calendars/day.txt"
        calendar.write_text("2026-07-30\n", encoding="utf-8")
        result = self.validate(artifact(), as_of=date(2026, 8, 5))
        self.assertIsNone(result.planned_execution_date)
        self.assertIn("EXECUTION_DATE_NOT_IN_CALENDAR", {item.code for item in result.blockers})

    def test_weekend_is_not_used_as_execution_day(self) -> None:
        calendar = self.root / "data/qlib/cn_data/calendars/day.txt"
        calendar.write_text("2026-07-31\n2026-08-03\n", encoding="utf-8")
        item = artifact(signal_date="2026-07-31", data_as_of="2026-07-31")
        result = self.validate(item, as_of=date(2026, 7, 31))
        self.assertEqual(result.planned_execution_date, "2026-08-03")

    def test_duplicate_and_illegal_codes_are_rejected(self) -> None:
        duplicate = signals()
        duplicate[-1] = replace(duplicate[-1], code=duplicate[0].code)
        with self.assertRaises(ArtifactError):
            self.validate(artifact(signals=duplicate))
        illegal = signals()
        illegal[-1] = replace(illegal[-1], code="US.AAPL")
        with self.assertRaises(Exception):
            self.validate(artifact(signals=illegal))

    def test_non_universe_code_is_rejected(self) -> None:
        outside = signals()
        outside[-1] = SignalRecord("SH600019", 0.1, 7, 0.5)
        with self.assertRaises(ArtifactError):
            self.validate(artifact(signals=outside))

    def test_invalid_weight_semantics_and_risk_degree_are_rejected(self) -> None:
        with self.assertRaises(ArtifactError):
            self.validate(artifact(metadata=metadata(weight_semantics="equal weight")))
        with self.assertRaises(ArtifactError):
            self.validate(artifact(metadata=metadata(risk_degree=-0.1)))

    def test_top5_rank_mismatch_is_rejected(self) -> None:
        bad = signals()
        bad[4] = replace(bad[4], rank=8)
        with self.assertRaises(ArtifactError):
            self.validate(artifact(signals=bad))


if __name__ == "__main__":
    unittest.main()
