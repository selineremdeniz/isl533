"""Veri temizleme.

Örnek veride görülen sorunlar:
- Ondalık ayırıcı kaymış değerler (lat=40875 → 40.875, heading=357313 → 357.313)
- callsign boş satırlar (~%1,6)
- velocity/heading eksik satırlar
- Aynı konumun tekrarlandığı (pozisyon güncellenmemiş) ardışık satırlar
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Çalışma alanı (veri sorgusunun kutusu)
BBOX = dict(lat=(40.5, 41.5), lon=(28.0, 29.8))
LIMITS = dict(lat=90, lon=180, heading=360, velocity=400)  # velocity m/s


def _fix_decimal_shift(s: pd.Series, limit: float, lo: float | None = None,
                       hi: float | None = None) -> pd.Series:
    """Sınırı aşan değeri 10'a bölerek makul aralığa çekmeye çalışır; olmazsa NaN."""
    s = s.astype(float).copy()
    bad = s.abs() > limit
    if bad.any():
        v = s[bad]
        for _ in range(8):
            v = np.where(np.abs(v) > limit, v / 10.0, v)
        v = pd.Series(v, index=s[bad].index)
        if lo is not None:
            v[(v < lo) | (v > hi)] = np.nan
        s[bad] = v
    return s


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["lat"] = _fix_decimal_shift(df["lat"], LIMITS["lat"], *BBOX["lat"])
    df["lon"] = _fix_decimal_shift(df["lon"], LIMITS["lon"], *BBOX["lon"])
    df["heading"] = _fix_decimal_shift(df["heading"], LIMITS["heading"], 0, 360)
    # hız için ondalık kayması tahmini güvenilir değil → NaN yap, sonra enterpole et
    df.loc[df["velocity"] > LIMITS["velocity"], "velocity"] = np.nan

    df = df.dropna(subset=["callsign", "lat", "lon", "baroaltitude"])
    df = df[df["callsign"].str.len() > 0]
    key = ["icao24", "callsign", "time"] if "icao24" in df.columns else ["callsign", "time"]
    df = df.drop_duplicates(subset=key).sort_values(key[:-1] + ["time"])

    grp = df.groupby(key[:-1], sort=False)
    for c in ["velocity", "heading"]:
        df[c] = grp[c].transform(lambda s: s.interpolate(limit=30, limit_direction="both"))
    return df.reset_index(drop=True)
