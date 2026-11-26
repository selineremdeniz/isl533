"""Streamlit arayüzü (iskelet). Çalıştırma: streamlit run app/streamlit_app.py"""
from pathlib import Path

import pandas as pd
import streamlit as st

DATA = Path(__file__).resolve().parents[1] / "data" / "processed" / "flights.parquet"

st.set_page_config(page_title="LTFM/LTFJ Yakıt Analizi", layout="wide")
st.title("LTFM / LTFJ terminal sahası yakıt tüketimi")

if not DATA.exists():
    st.warning("Önce `python scripts/run_pipeline.py ...` çalıştırın.")
    st.stop()

f = pd.read_parquet(DATA)
c1, c2 = st.columns(2)
op = c1.multiselect("Operasyon", sorted(f.operation.dropna().unique()), default=["inis", "kalkis"])
ap = c2.multiselect("Havalimanı", sorted(f.airport.dropna().unique()), default=["LTFM", "LTFJ"])
s = f[f.operation.isin(op) & f.airport.isin(ap)]

st.metric("Uçuş sayısı", len(s))
st.metric("Medyan yakıt (kg)", round(s.fuel_kg.median(), 0) if len(s) else "-")
st.bar_chart(s.groupby("typecode").fuel_kg.median().sort_values())
st.scatter_chart(s, x="duration_min", y="fuel_kg", color="operation")
st.dataframe(s.head(200))
