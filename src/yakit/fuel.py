"""OpenAP ile nokta bazında yakıt akışı (kg/s) ve uçuş bazında toplam yakıt.

OpenAP FuelFlow.enroute girdileri: mass [kg], tas [kt], alt [ft], vs [ft/min], acc [m/s²].
Veride TAS yok → velocity (yer hızı) TAS yerine kullanılır (rüzgar yok varsayımı).
Rüzgar verisi (ERA5) eklenirse tas = |gs_vektörü - rüzgar_vektörü| ile düzeltilebilir.
Kütle bilinmiyor → MTOW'un sabit bir oranı varsayılır (MASS_FRAC).
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from openap import FuelFlow

from .aircraft import aircraft_props

M2FT = 3.28084
MS2KT = 1.94384
MASS_FRAC = {"kalkis": 0.85, "inis": 0.70, "lokal": 0.75, "transit": 0.75}


@lru_cache(maxsize=64)
def _ff(openap_type: str) -> FuelFlow:
    return FuelFlow(openap_type, use_synonym=True)


def add_kinematics(g: pd.DataFrame) -> pd.DataFrame:
    """Dikey hız ve ivmeyi irtifa/hız farkından türetir (vertrate sütunu yoksa)."""
    g = g.copy()
    dt = g["time"].diff().astype(float).replace(0, np.nan)
    alt_s = g["baroaltitude"].rolling(15, center=True, min_periods=1).median()
    if "vertrate" in g.columns and g["vertrate"].notna().mean() > 0.5:
        g["vs_ms"] = g["vertrate"].interpolate(limit_direction="both")
    else:
        g["vs_ms"] = (alt_s.diff() / dt).rolling(15, center=True, min_periods=1).mean()
    spd = g["velocity"].rolling(9, center=True, min_periods=1).mean()
    g["acc_ms2"] = (spd.diff() / dt).clip(-3, 3)
    g["dt_s"] = dt.fillna(1.0).clip(upper=60)
    return g.fillna({"vs_ms": 0, "acc_ms2": 0})


def flight_fuel(g: pd.DataFrame, openap_type: str, operation: str = "transit",
                mass_frac: float | None = None) -> pd.DataFrame:
    g = add_kinematics(g)
    props = aircraft_props(openap_type)
    mass = props["mtow"] * (mass_frac or MASS_FRAC.get(operation, 0.75))
    ff = _ff(openap_type)
    g["fuel_flow_kgs"] = ff.enroute(
        mass=mass,
        tas=g["velocity"].to_numpy() * MS2KT,
        alt=g["baroaltitude"].to_numpy() * M2FT,
        vs=g["vs_ms"].to_numpy() * M2FT * 60,
        acc=g["acc_ms2"].to_numpy(),
    )
    g["fuel_kg"] = g["fuel_flow_kgs"] * g["dt_s"]
    g["mass_kg"] = mass
    return g
