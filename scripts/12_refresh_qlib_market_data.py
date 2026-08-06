"""Incrementally refresh the frozen CSI300 Qlib dataset from its Tencent source.

The script stages all network results before touching normalized files. It extends
the existing normalization factor from the last trusted row and never retrains a
model. The benchmark is used as the same-source market calendar authority.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
import json
import math
from pathlib import Path
import time

import akshare as ak
from akshare.utils import demjson
import numpy as np
import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONSTITUENTS_FILE = PROJECT_ROOT / "data" / "raw" / "akshare" / "csi300_current.csv"
NORMALIZED_DIR = PROJECT_ROOT / "data" / "normalized" / "qlib_csv"
CSI300_INSTRUMENTS = PROJECT_ROOT / "data" / "qlib" / "cn_data" / "instruments" / "csi300.txt"
QLIB_CALENDAR = PROJECT_ROOT / "data" / "qlib" / "cn_data" / "calendars" / "day.txt"
OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "market_refresh"
REQUIRED = {"date", "open", "close", "high", "low", "volume", "amount"}


@dataclass(frozen=True)
class DownloadedPair:
    qlib_code: str
    raw: pd.DataFrame
    hfq: pd.DataFrame


def _symbols(code: str, exchange: str) -> tuple[str, str]:
    code = str(code).zfill(6)
    if "上海" in exchange:
        return f"SH{code}", f"sh{code}"
    if "深圳" in exchange:
        return f"SZ{code}", f"sz{code}"
    raise ValueError(f"Unsupported exchange for {code}: {exchange}")


def _validate(frame: pd.DataFrame, symbol: str, adjustment: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        raise RuntimeError(f"{symbol} {adjustment} returned no data")
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise RuntimeError(f"{symbol} {adjustment} missing columns: {sorted(missing)}")
    result = frame[list(REQUIRED)].copy()
    result["date"] = pd.to_datetime(result["date"], errors="raise")
    for column in REQUIRED - {"date"}:
        result[column] = pd.to_numeric(result[column], errors="raise")
    result = result.sort_values("date").drop_duplicates("date", keep="last")
    if (result[["open", "close", "high", "low"]] <= 0).any().any():
        raise RuntimeError(f"{symbol} {adjustment} contains non-positive prices")
    if (result[["volume", "amount"]] < 0).any().any():
        raise RuntimeError(f"{symbol} {adjustment} contains negative volume/amount")
    return result.reset_index(drop=True)


def _download_one(qlib_code: str, tx_code: str, start: str, end: str) -> DownloadedPair:
    def fetch(adjustment: str) -> pd.DataFrame:
        year = start[:4]
        url = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
        params = {
            "_var": f"kline_day{adjustment}{year}",
            "param": f"{tx_code},day,{year}-01-01,{int(year) + 1}-12-31,640,{adjustment}",
            "r": "0.8205512681390605",
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        text = response.text
        payload = demjson.decode(text[text.find("={") + 1 :])["data"][tx_code]
        key = "day" if adjustment == "" else f"{adjustment}day"
        # Tencent returns only ``day`` for securities with no adjustment series.
        # In that case the provider's adjusted response is explicitly identical
        # to the raw series; it is not a locally invented adjustment.
        if key not in payload and adjustment and "day" in payload:
            key = "day"
        frame = pd.DataFrame(payload[key]).iloc[:, [0, 1, 2, 3, 4, 5, 7, 8]]
        frame.columns = ["date", "open", "close", "high", "low", "volume", "turnover", "amount"]
        frame["date"] = pd.to_datetime(frame["date"], errors="raise")
        for column in ["open", "close", "high", "low", "volume", "turnover", "amount"]:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        if not tx_code.startswith(("sh688", "sz399", "sh000", "sz000")):
            frame["volume"] *= 100.0
        frame["amount"] *= 10000.0
        start_timestamp = pd.Timestamp(start)
        end_timestamp = pd.Timestamp(end)
        return frame[frame["date"].between(start_timestamp, end_timestamp)].reset_index(drop=True)

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            raw = fetch("")
            hfq = fetch("hfq")
            return DownloadedPair(
                qlib_code,
                _validate(raw, tx_code, "unadjusted"),
                _validate(hfq, tx_code, "hfq"),
            )
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"{qlib_code} refresh failed: {last_error}")


def _volume_multiplier(raw: pd.DataFrame) -> float:
    volume = raw["volume"].replace(0, np.nan).astype(float)
    close = raw["close"].astype(float)
    amount = raw["amount"].astype(float)

    def error(multiplier: float) -> float:
        candidate = amount / (volume * multiplier)
        valid = candidate.notna() & (candidate > 0) & (close > 0)
        if not valid.any():
            return math.inf
        return float(np.median(np.abs(np.log(candidate[valid] / close[valid]))))

    return 100.0 if error(100.0) < error(1.0) else 1.0


def _append_stock(pair: DownloadedPair, cutoff: pd.Timestamp) -> int:
    destination = NORMALIZED_DIR / f"{pair.qlib_code}.csv"
    existing = pd.read_csv(destination)
    existing["date"] = pd.to_datetime(existing["date"], errors="raise")
    last_date = existing["date"].max()
    raw = pair.raw[pair.raw["date"].le(cutoff)]
    hfq = pair.hfq[pair.hfq["date"].le(cutoff)]
    merged = raw.merge(
        hfq[["date", "close"]].rename(columns={"close": "hfq_close"}),
        on="date",
        validate="one_to_one",
    )
    anchor = merged[merged["date"].eq(last_date)]
    if anchor.empty:
        raise RuntimeError(f"{pair.qlib_code} response does not contain anchor {last_date.date()}")
    anchor_ratio = float(anchor.iloc[0]["hfq_close"] / anchor.iloc[0]["close"])
    old_factor = float(existing.loc[existing["date"].eq(last_date), "factor"].iloc[-1])
    scale = old_factor / anchor_ratio
    new_rows = merged[merged["date"].gt(last_date)].copy()
    if new_rows.empty:
        return 0
    factor = (new_rows["hfq_close"] / new_rows["close"]) * scale
    multiplier = _volume_multiplier(raw)
    volume_shares = new_rows["volume"] * multiplier
    raw_vwap = np.where(volume_shares > 0, new_rows["amount"] / volume_shares, np.nan)
    additions = pd.DataFrame(
        {
            "date": new_rows["date"],
            "open": new_rows["open"] * factor,
            "high": new_rows["high"] * factor,
            "low": new_rows["low"] * factor,
            "close": new_rows["close"] * factor,
            "volume": volume_shares / factor,
            "factor": factor,
            "vwap": raw_vwap * factor,
        }
    )
    combined = pd.concat([existing, additions], ignore_index=True)
    combined = combined.sort_values("date").drop_duplicates("date", keep="last")
    combined["date"] = pd.to_datetime(combined["date"]).dt.strftime("%Y-%m-%d")
    temporary = destination.with_suffix(".csv.phase2c1.tmp")
    combined.to_csv(temporary, index=False, encoding="utf-8")
    temporary.replace(destination)
    return len(additions)


def _append_benchmark(benchmark: pd.DataFrame, through: pd.Timestamp) -> int:
    destination = NORMALIZED_DIR / "SH000300.csv"
    existing = pd.read_csv(destination)
    existing["date"] = pd.to_datetime(existing["date"], errors="raise")
    last_date = existing["date"].max()
    factor = float(existing.loc[existing["date"].eq(last_date), "factor"].iloc[-1])
    frame = benchmark.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    for column in ["open", "high", "low", "close", "amount"]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    frame = frame[frame["date"].gt(last_date) & frame["date"].le(through)].copy()
    if frame.empty:
        return 0
    additions = pd.DataFrame(
        {
            "date": frame["date"],
            "open": frame["open"] * factor,
            "high": frame["high"] * factor,
            "low": frame["low"] * factor,
            "close": frame["close"] * factor,
            "volume": frame["amount"] * 100.0 / factor,
            "factor": factor,
            "vwap": frame["close"] * factor,
        }
    )
    combined = pd.concat([existing, additions], ignore_index=True)
    combined = combined.sort_values("date").drop_duplicates("date", keep="last")
    combined["date"] = pd.to_datetime(combined["date"]).dt.strftime("%Y-%m-%d")
    temporary = destination.with_suffix(".csv.phase2c1.tmp")
    combined.to_csv(temporary, index=False, encoding="utf-8")
    temporary.replace(destination)
    return len(additions)


def _extend_frozen_universe(through: pd.Timestamp) -> None:
    rows = []
    for line in CSI300_INSTRUMENTS.read_text(encoding="utf-8").splitlines():
        code, start, _end = line.split("\t")
        rows.append(f"{code}\t{start}\t{through.date().isoformat()}")
    temporary = CSI300_INSTRUMENTS.with_suffix(".txt.phase2c1.tmp")
    temporary.write_text("\n".join(rows) + "\n", encoding="utf-8")
    temporary.replace(CSI300_INSTRUMENTS)


def _extend_frozen_calendar(verified_days: list[pd.Timestamp], through: pd.Timestamp) -> None:
    existing = {
        pd.Timestamp(line.strip())
        for line in QLIB_CALENDAR.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    additions = {value for value in verified_days if value <= through}
    combined = sorted(existing.union(additions))
    temporary = QLIB_CALENDAR.with_suffix(".txt.phase2c1.tmp")
    temporary.write_text(
        "\n".join(value.date().isoformat() for value in combined) + "\n", encoding="utf-8"
    )
    temporary.replace(QLIB_CALENDAR)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh frozen CSI300 data without retraining")
    parser.add_argument("--through", default=date.today().isoformat())
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--verified-calendar",
        required=True,
        help="JSON produced by the read-only Futu CN trading-calendar check",
    )
    args = parser.parse_args()
    constituents = pd.read_csv(CONSTITUENTS_FILE, dtype={"成分券代码": str, "交易所": str})
    jobs = []
    anchor_dates = []
    for _, row in constituents.iterrows():
        qlib_code, tx_code = _symbols(row["成分券代码"], row["交易所"])
        existing = pd.read_csv(NORMALIZED_DIR / f"{qlib_code}.csv", usecols=["date"])
        anchor = pd.to_datetime(existing["date"], errors="raise").max()
        anchor_dates.append(anchor)
        jobs.append((qlib_code, tx_code, anchor.strftime("%Y%m%d"), args.through.replace("-", "")))
    if len(set(anchor_dates)) != 1:
        raise RuntimeError("Normalized stock files do not share one trusted anchor date")
    anchor = anchor_dates[0]
    downloaded: dict[str, DownloadedPair] = {}
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_download_one, *job): job[0] for job in jobs}
        for index, future in enumerate(as_completed(futures), start=1):
            code = futures[future]
            try:
                downloaded[code] = future.result()
            except Exception as exc:
                failures.append(f"{code}: {exc}")
            if index % 25 == 0 or index == len(futures):
                print(f"downloaded {index}/{len(futures)}; failures={len(failures)}", flush=True)
    if failures:
        raise RuntimeError("Refresh staging failed; no normalized files changed:\n" + "\n".join(failures))

    coverage: Counter[pd.Timestamp] = Counter()
    for pair in downloaded.values():
        for value in pair.raw.loc[pair.raw["date"].gt(anchor), "date"].unique():
            coverage[pd.Timestamp(value)] += 1
    minimum_coverage = math.ceil(len(downloaded) * 0.90)
    eligible = sorted(day for day, count in coverage.items() if count >= minimum_coverage)
    if not eligible:
        raise RuntimeError("No post-anchor date has at least 90% cross-sectional coverage")
    cutoff = eligible[-1]

    benchmark = ak.stock_zh_index_daily_tx(symbol="sh000300")
    benchmark["date"] = pd.to_datetime(benchmark["date"], errors="raise")
    calendar_payload = json.loads(Path(args.verified_calendar).read_text(encoding="utf-8"))
    verified_days = sorted(pd.Timestamp(value) for value in calendar_payload["trading_days"])
    historical = {pd.Timestamp(value).date() for value in benchmark["date"]}
    overlap = {value.date() for value in verified_days if value <= cutoff}
    if not overlap or not overlap.issubset(historical):
        raise RuntimeError("Verified CN calendar conflicts with the Tencent benchmark calendar")
    next_days = [value for value in verified_days if value > cutoff]
    if not next_days:
        raise RuntimeError("Verified CN calendar has no trading day after the stock cutoff")
    next_trading_day = pd.Timestamp(next_days[0])

    audit_dir = OUTPUT_ROOT / cutoff.date().isoformat()
    audit_dir.mkdir(parents=True, exist_ok=True)
    for code, pair in downloaded.items():
        pair.raw.to_csv(audit_dir / f"{code}_raw.csv", index=False, encoding="utf-8")
        pair.hfq.to_csv(audit_dir / f"{code}_hfq.csv", index=False, encoding="utf-8")

    appended = {code: _append_stock(pair, cutoff) for code, pair in sorted(downloaded.items())}
    benchmark_rows = _append_benchmark(benchmark, cutoff)
    _extend_frozen_universe(next_trading_day)
    _extend_frozen_calendar(verified_days, next_trading_day)
    manifest = {
        "source": "AKShare Tencent stock_zh_a_hist_tx / stock_zh_index_daily_tx",
        "mock": False,
        "anchor_date": anchor.date().isoformat(),
        "data_as_of": cutoff.date().isoformat(),
        "next_trading_day": next_trading_day.date().isoformat(),
        "calendar_authority": calendar_payload.get("source", "FutuOpenD CN read-only calendar"),
        "constituents": len(downloaded),
        "minimum_cross_sectional_coverage": minimum_coverage,
        "actual_cutoff_coverage": coverage[cutoff],
        "stock_rows_appended": sum(appended.values()),
        "benchmark_rows_appended": benchmark_rows,
        "generated_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(),
    }
    (audit_dir / "refresh_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
