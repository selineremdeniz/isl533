"""Uçuş bazında özellik (girdi değişkeni) çıkarımı. Hedef: fuel_kg (toplam) ve fuel_per_km.

Değişkenlerin gerekçeleri docs/degiskenler.md içinde.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

R_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dlat, dlon = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlon / 2) ** 2
    return 2 * R_KM * np.arcsin(np.sqrt(a))


def flight_features(g: pd.DataFrame) -> dict:
    """g: tek uçuşun zaman sıralı noktaları (fuel.flight_fuel çıktısı)."""
    seg = haversine_km(g.lat.values[:-1], g.lon.values[:-1], g.lat.values[1:], g.lon.values[1:])
    track_km = float(np.nansum(seg))
    direct_km = float(haversine_km(g.lat.iloc[0], g.lon.iloc[0], g.lat.iloc[-1], g.lon.iloc[-1]))
    dur_s = float(g["time"].iloc[-1] - g["time"].iloc[0])
    vs = g["vs_ms"]
    level = vs.abs() < 1.5  # ~300 ft/dk altı = yatay uçuş
    hdg = np.unwrap(np.radians(g["heading"].ffill().bfill().to_numpy()))
    turn_deg = float(np.degrees(np.abs(np.diff(hdg)).sum())) if len(hdg) > 1 else 0.0
    t0 = pd.to_datetime(int(g["time"].iloc[0]), unit="s", utc=True).tz_convert("Europe/Istanbul")
    fuel = float(g["fuel_kg"].sum()) if "fuel_kg" in g else np.nan
    return {
        "duration_min": dur_s / 60,
        "track_km": track_km,
        "direct_km": direct_km,
        "path_ratio": track_km / direct_km if direct_km > 1 else np.nan,  # rota uzaması
        "alt_mean_m": g.baroaltitude.mean(),
        "alt_min_m": g.baroaltitude.min(),
        "alt_max_m": g.baroaltitude.max(),
        "alt_change_m": g.baroaltitude.iloc[-1] - g.baroaltitude.iloc[0],
        "spd_mean_ms": g.velocity.mean(),
        "spd_std_ms": g.velocity.std(),
        "vs_mean_abs_ms": vs.abs().mean(),
        "level_share": float(level.mean()),          # yatay uçuş (level-off) payı
        "level_low_min": float((level & (g.baroaltitude < 3000)).sum() * g.dt_s.median() / 60),
        "turn_total_deg": turn_deg,                   # holding/vektörleme göstergesi
        "acc_abs_mean": g["acc_ms2"].abs().mean(),
        "hour_local": t0.hour,
        "weekday": t0.dayofweek,
        "mass_kg": g["mass_kg"].iloc[0] if "mass_kg" in g else np.nan,
        "fuel_kg": fuel,
        "fuel_per_min": fuel / (dur_s / 60) if dur_s > 0 else np.nan,
        "fuel_per_km": fuel / track_km if track_km > 0 else np.nan,
        "n_points": len(g),
    }


def add_traffic_density(flights: pd.DataFrame, bin_min: int = 15) -> pd.DataFrame:
    """Aynı zaman diliminde alandaki uçuş sayısı (yoğunluk → bekleme/vektörleme)."""
    f = flights.copy()
    b = (f["t_start"] // (bin_min * 60)).astype(int)
    f["traffic_15min"] = b.map(b.value_counts())
    return f
