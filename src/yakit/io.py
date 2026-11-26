"""Ham yörünge verisini okuma ve günlük parquet parçalarına dönüştürme.

1 aylık veri tek bir Excel'e sığmaz (Excel en fazla ~1,05 milyon satır alır).
Bu yüzden ham veriyi CSV/parquet olarak alıp güne göre bölünmüş parquet
dosyalarına çeviriyoruz; sonraki adımlar her günü ayrı işler.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

NUMERIC_COLS = ["lat", "lon", "baroaltitude", "geoaltitude", "velocity",
                "heading", "vertrate"]
STR_COLS = ["callsign", "icao24"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower() for c in df.columns]
    for c in STR_COLS:
        if c in df.columns:
            df[c] = df[c].astype("string").str.strip().str.lower() if c == "icao24" \
                else df[c].astype("string").str.strip().str.upper()
    for c in NUMERIC_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "onground" in df.columns:
        df["onground"] = df["onground"].astype(str).str.lower().isin(["true", "1"])
    df["time"] = pd.to_numeric(df["time"], errors="coerce").astype("Int64")
    return df


def read_raw(path: str | Path, chunksize: int = 2_000_000):
    """Ham dosyayı parça parça okur (xlsx, csv, csv.gz, parquet)."""
    path = Path(path)
    suf = "".join(path.suffixes).lower()
    if suf.endswith(".xlsx"):
        yield _normalize(pd.read_excel(path, engine="openpyxl", dtype={"callsign": str, "icao24": str}))
    elif suf.endswith(".parquet"):
        yield _normalize(pd.read_parquet(path))
    else:  # csv / csv.gz
        for chunk in pd.read_csv(path, chunksize=chunksize, dtype={"callsign": str, "icao24": str}):
            yield _normalize(chunk)


def to_daily_parquet(path: str | Path, out_dir: str | Path) -> list[Path]:
    """Ham dosyayı data/interim/day=YYYY-MM-DD/part-N.parquet şeklinde böler."""
    out_dir = Path(out_dir)
    written = []
    for i, chunk in enumerate(read_raw(path)):
        day = pd.to_datetime(chunk["time"].astype("int64"), unit="s", utc=True).dt.strftime("%Y-%m-%d")
        for d, part in chunk.groupby(day):
            p = out_dir / f"day={d}" / f"{Path(path).stem}-part{i}.parquet"
            p.parent.mkdir(parents=True, exist_ok=True)
            part.to_parquet(p, index=False)
            written.append(p)
    return written


def read_day(day_dir: str | Path) -> pd.DataFrame:
    return pd.concat([pd.read_parquet(p) for p in sorted(Path(day_dir).glob("*.parquet"))],
                     ignore_index=True)
