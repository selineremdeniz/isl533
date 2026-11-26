"""Uçtan uca işlem hattı: ham veri → günlük parquet → temizlik → uçuşlar → yakıt → özellikler.

Örnek:
    python scripts/run_pipeline.py --raw data/raw/LTFM_LTFJ_Haziran2026.csv.gz \
        --aircraft-db data/raw/aircraft_db.csv

icao24 sütunu yoksa (örnek Excel'deki gibi) --default-type ile tüm uçuşlara tek tip
atanabilir; bu yalnızca deneme amaçlıdır.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from yakit import aircraft, clean, features, fuel, io, segment  # noqa: E402

MIN_POINTS = 60  # 1 dk'dan kısa kayıtları at


def process_day(day_dir: Path, ac_db: dict | None, default_type: str | None) -> pd.DataFrame:
    df = clean.clean(io.read_day(day_dir))
    df = segment.assign_flight_id(df)
    rows = []
    for fid, g in df.groupby("flight_id", sort=False):
        if len(g) < MIN_POINTS:
            continue
        info = {"flight_id": fid, "callsign": g.callsign.iloc[0],
                "airline": g.callsign.iloc[0][:3], "t_start": int(g.time.iloc[0])}
        info.update(segment.classify_flight(g))
        typecode = None
        if ac_db is not None and "icao24" in g.columns:
            info["icao24"] = g.icao24.iloc[0]
            typecode = ac_db.get(info["icao24"])
        info["typecode"] = typecode or default_type
        info["openap_type"] = aircraft.to_openap_type(info["typecode"])
        if info["openap_type"] is None:
            rows.append(info)
            continue
        info.update({f"ac_{k}": v for k, v in aircraft.aircraft_props(info["openap_type"]).items()})
        gf = fuel.flight_fuel(g, info["openap_type"], info["operation"])
        info.update(features.flight_features(gf))
        rows.append(info)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", nargs="+", required=True, help="ham dosya(lar): xlsx/csv/csv.gz/parquet")
    ap.add_argument("--aircraft-db", default=None)
    ap.add_argument("--default-type", default=None, help="icao24 yoksa deneme tipi, örn. A320")
    ap.add_argument("--interim", default="data/interim")
    ap.add_argument("--out", default="data/processed/flights.parquet")
    a = ap.parse_args()

    for p in a.raw:
        io.to_daily_parquet(p, a.interim)
    ac_db = (aircraft.load_aircraft_db(a.aircraft_db).set_index("icao24")["typecode"].dropna().to_dict()
             if a.aircraft_db else None)

    days = sorted(Path(a.interim).glob("day=*"))
    out = [process_day(d, ac_db, a.default_type) for d in tqdm(days, desc="gün")]
    flights = features.add_traffic_density(pd.concat(out, ignore_index=True))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    flights.to_parquet(a.out, index=False)
    print(f"{len(flights)} uçuş → {a.out}")
    print(flights.groupby(["operation", "airport"], dropna=False).size())


if __name__ == "__main__":
    main()
