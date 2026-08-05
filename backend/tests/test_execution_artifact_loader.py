from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from backend.execution.artifact_loader import export_execution_artifact, load_execution_artifact
from backend.execution.exceptions import ArtifactError


def task_config():
    return {
        "model": {"class": "LGBModel"},
        "dataset": {"kwargs": {"handler": {"class": "Alpha158", "kwargs": {"instruments": "csi300"}}}},
        "record": [
            {
                "class": "PortAnaRecord",
                "kwargs": {
                    "config": {
                        "strategy": {
                            "class": "TopkDropoutStrategy",
                            "kwargs": {"topk": 5, "n_drop": 1, "risk_degree": 0.95, "only_tradable": True},
                        },
                        "backtest": {
                            "benchmark": "SH000300",
                            "exchange_kwargs": {
                                "deal_price": "close", "open_cost": 0.0005, "close_cost": 0.0015, "min_cost": 5
                            },
                        },
                    }
                },
            }
        ],
    }


class ArtifactLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.root = Path(self.temp.name)
        self.backtest = self.root / "outputs" / "backtest" / "v2"
        self.output = self.root / "outputs" / "execution_artifacts"
        self.calendar = self.root / "data" / "calendar.txt"
        self.universe = self.root / "data" / "csi300.txt"
        self.backtest.mkdir(parents=True)
        self.calendar.parent.mkdir(parents=True)
        self.calendar.write_text("2026-07-30\n2026-07-31\n", encoding="utf-8")
        codes = ["SH600000", "SH600009", "SH600010", "SH600011", "SH600015"]
        self.universe.write_text("".join(f"{code}\t2020-01-01\t2026-12-31\n" for code in codes), encoding="utf-8")
        (self.backtest / "task_config.json").write_text(json.dumps(task_config()), encoding="utf-8")
        (self.backtest / "artifact_manifest.json").write_text(json.dumps({"recorder_id": "rec-1"}), encoding="utf-8")
        rows = ["datetime,instrument,score,rank_desc,score_percentile"]
        rows.extend(f"2026-07-30,{code},{1-i/10},{i+1},{1-i/20}" for i, code in enumerate(codes))
        csv = "\n".join(rows) + "\n"
        (self.backtest / "predictions.csv").write_text(csv, encoding="utf-8")
        (self.backtest / "top5_predictions.csv").write_text(csv, encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_exports_traceable_backend_artifact_deterministically(self) -> None:
        first = export_execution_artifact(
            backtest_dir=self.backtest, output_dir=self.output, calendar_path=self.calendar,
            universe_path=self.universe, project_root=self.root,
        )
        second = export_execution_artifact(
            backtest_dir=self.backtest, output_dir=self.output, calendar_path=self.calendar,
            universe_path=self.universe, project_root=self.root,
        )
        loaded = load_execution_artifact(first)
        self.assertEqual(first, second)
        self.assertEqual(loaded.source_kind, "backend_qlib_recorder_export")
        self.assertEqual(loaded.signal_date, "2026-07-30")
        self.assertEqual(len(loaded.signals), 5)
        self.assertFalse(loaded.is_mock)

    def test_missing_source_is_rejected(self) -> None:
        (self.backtest / "predictions.csv").unlink()
        with self.assertRaises(ArtifactError):
            export_execution_artifact(
                backtest_dir=self.backtest, output_dir=self.output, calendar_path=self.calendar,
                universe_path=self.universe, project_root=self.root,
            )

    def test_missing_artifact_fields_are_rejected(self) -> None:
        path = self.root / "bad.json"
        path.write_text("{}", encoding="utf-8")
        with self.assertRaises(ArtifactError):
            load_execution_artifact(path)


if __name__ == "__main__":
    unittest.main()
