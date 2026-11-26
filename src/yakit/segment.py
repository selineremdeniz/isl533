"""Satırları uçuşlara bölme ve uçuşu sınıflandırma (kalkış/iniş, LTFM/LTFJ)."""
from __future__ import annotations

import numpy as np
import pandas as pd

AIRPORTS = {
    "LTFM": (41.2611, 28.7419),  # İstanbul Havalimanı
    "LTFJ": (40.8986, 29.3092),  # Sabiha Gökçen
}
GAP_S = 600          # 10 dk'dan uzun boşluk = yeni uçuş
NEAR_DEG = 0.12      # havalimanına "yakın" eşiği (~10 km)
LOW_ALT_M = 1000     # kalkış/iniş ucunun bu irtifanın altında olması beklenir


def assign_flight_id(df: pd.DataFrame) -> pd.DataFrame:
    key = ["icao24", "callsign"] if "icao24" in df.columns else ["callsign"]
    df = df.sort_values(key + ["time"])
    new = df.groupby(key)["time"].diff().fillna(GAP_S + 1) > GAP_S
    seq = new.groupby([df[k] for k in key]).cumsum()
    df["flight_id"] = df[key].astype(str).agg("_".join, axis=1) + "_" + \
        pd.to_datetime(df["time"].astype("int64"), unit="s").dt.strftime("%Y%m%d") + "_" + seq.astype(str)
    return df


def _nearest_airport(lat, lon):
    best, dist = None, np.inf
    for code, (a, b) in AIRPORTS.items():
        d = np.hypot(lat - a, (lon - b) * np.cos(np.radians(a)))
        if d < dist:
            best, dist = code, d
    return best if dist < NEAR_DEG else None


def classify_flight(g: pd.DataFrame) -> dict:
    first, last = g.iloc[0], g.iloc[-1]
    ap_start = _nearest_airport(first.lat, first.lon) if first.baroaltitude < LOW_ALT_M else None
    ap_end = _nearest_airport(last.lat, last.lon) if last.baroaltitude < LOW_ALT_M else None
    if ap_end and not ap_start:
        op, ap = "inis", ap_end
    elif ap_start and not ap_end:
        op, ap = "kalkis", ap_start
    elif ap_start and ap_end:
        op, ap = "lokal", ap_start
    else:
        op, ap = "transit", None   # kutudan geçen ya da kısmi kayıt
    return {"operation": op, "airport": ap}
