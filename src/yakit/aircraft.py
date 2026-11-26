"""icao24 → uçak tipi (ICAO typecode) eşlemesi ve OpenAP'e uygun hale getirme.

Kaynak: OpenSky aircraft database (aircraftDatabase.csv / aircraft-database-complete).
Dosyayı indirip data/raw/aircraft_db.csv olarak koyun; sütunlar: icao24, typecode,
(isteğe bağlı) operatoricao, registration, model.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from openap import prop

OPENAP_TYPES = {t.upper() for t in prop.available_aircraft()}

# OpenAP'te doğrudan olmayan yaygın tipler için en yakın vekil
FALLBACK = {
    "A21N": "A21N", "A20N": "A20N", "B38M": "B38M", "B39M": "B39M",
    "A333": "A333", "A332": "A332", "A339": "A333", "A338": "A332",
    "A359": "A359", "A35K": "A359", "B77W": "B77W", "B772": "B772",
    "B78X": "B789", "B763": "B763", "B764": "B763", "B753": "B752",
    "AT76": None, "AT75": None, "DH8D": None,   # turboprop: OpenAP fuel modeli yok
    "BCS3": "A20N", "BCS1": "A319", "E290": "E190", "E295": "E195",
    "A310": "A332", "B733": "B734", "B736": "B737", "CRJ7": "CRJ9",
    "C56X": "C550", "GLF5": "GLF6", "GLEX": "GLF6",
}


def load_aircraft_db(path: str | Path) -> pd.DataFrame:
    db = pd.read_csv(path, dtype=str, usecols=lambda c: c.strip("'").lower() in
                     {"icao24", "typecode", "operatoricao", "registration", "model"},
                     quotechar="'" if "complete" in str(path) else '"')
    db.columns = [c.strip("'").lower() for c in db.columns]
    db["icao24"] = db["icao24"].str.strip().str.lower()
    db["typecode"] = db["typecode"].str.strip().str.upper()
    return db.dropna(subset=["icao24"]).drop_duplicates("icao24")


def to_openap_type(typecode: str | None) -> str | None:
    if not isinstance(typecode, str) or not typecode:
        return None
    t = typecode.upper()
    if t in OPENAP_TYPES:
        return t
    if t in FALLBACK:
        return FALLBACK[t]
    try:  # OpenAP synonym tablosu
        prop.aircraft(t, use_synonym=True)
        return t
    except Exception:
        return None


def attach_types(flights: pd.DataFrame, db: pd.DataFrame) -> pd.DataFrame:
    out = flights.merge(db[["icao24", "typecode"]], on="icao24", how="left")
    out["openap_type"] = out["typecode"].map(to_openap_type)
    return out


def aircraft_props(openap_type: str) -> dict:
    a = prop.aircraft(openap_type, use_synonym=True)
    return {"mtow": a["mtow"], "oew": a.get("oew"), "engine": a["engine"]["default"],
            "n_engines": a["engine"].get("number"), "wing_area": a["wing"]["area"]}
