"""Lapisan akses data: PostgreSQL (DBMS 1) + SQLite (DBMS 2) + penggabungan di Pandas."""
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

ROOT = Path(__file__).parent
SQLITE_PATH = Path(os.environ.get("SQLITE_PATH", ROOT / "data" / "referensi.sqlite"))


# ---------------------------------------------------------------- koneksi ----
def _pg_url() -> str:
    """Ambil URL PostgreSQL dari env var DATABASE_URL atau st.secrets (tanpa hardcode)."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        try:
            url = st.secrets["postgres"]["url"]
        except Exception:
            url = None
    if not url:
        raise RuntimeError(
            "DATABASE_URL belum diatur. Isi environment variable DATABASE_URL "
            "atau .streamlit/secrets.toml (lihat README)."
        )
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


@st.cache_resource(show_spinner=False)
def pg_engine():
    return create_engine(_pg_url(), pool_pre_ping=True, pool_recycle=300)


@st.cache_resource(show_spinner=False)
def sqlite_engine():
    # mode=ro: aplikasi hanya membaca data referensi
    return create_engine(f"sqlite:///file:{SQLITE_PATH}?mode=ro&uri=true")


# ------------------------------------------------------- DBMS 2: SQLite ------
@st.cache_data(show_spinner=False)
def load_ref_wilayah() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM ref_wilayah", sqlite_engine())


@st.cache_data(show_spinner=False)
def load_kategori() -> tuple[pd.DataFrame, pd.DataFrame]:
    mag = pd.read_sql("SELECT * FROM ref_kategori_magnitudo ORDER BY urutan", sqlite_engine())
    dep = pd.read_sql("SELECT * FROM ref_kategori_kedalaman ORDER BY urutan", sqlite_engine())
    return mag, dep


@st.cache_data(show_spinner=False)
def load_fokal() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM mekanisme_fokal", sqlite_engine())


# ----------------------------------------------------- DBMS 1: PostgreSQL ----
@st.cache_data(show_spinner=False)
def pg_bounds() -> dict:
    sql = """SELECT MIN(waktu_kejadian) AS t0, MAX(waktu_kejadian) AS t1,
                    MIN(magnitudo) AS m0, MAX(magnitudo) AS m1,
                    MIN(kedalaman_km) AS d0, MAX(kedalaman_km) AS d1,
                    COUNT(*) AS n
             FROM gempa"""
    return pd.read_sql(sql, pg_engine()).iloc[0].to_dict()


@st.cache_data(show_spinner="Mengambil data dari PostgreSQL...", ttl=3600)
def query_events(t0, t1, m0, m1, d0, d1, remarks: tuple) -> pd.DataFrame:
    """Predicate pushdown: filter wilayah (dari SQLite) dikirim ke PostgreSQL sebagai ANY(:remarks)."""
    sql = text(
        """
        SELECT event_id, waktu_kejadian, lat, lon, kedalaman_km, magnitudo, remark
        FROM gempa
        WHERE waktu_kejadian >= :t0 AND waktu_kejadian < :t1
          AND magnitudo BETWEEN :m0 AND :m1
          AND kedalaman_km BETWEEN :d0 AND :d1
          AND remark = ANY(:remarks)
        """
    )
    params = dict(t0=t0, t1=t1, m0=m0, m1=m1, d0=d0, d1=d1, remarks=list(remarks))
    with pg_engine().connect() as conn:
        return pd.read_sql(sql, conn, params=params)


# ------------------------------------------------ penggabungan (federation) --
def build_dataset(events: pd.DataFrame) -> pd.DataFrame:
    """Gabungkan hasil PostgreSQL dengan tabel referensi SQLite menggunakan Pandas."""
    wil = load_ref_wilayah()
    fokal = load_fokal()
    kat_mag, kat_dep = load_kategori()

    df = events.merge(wil, on="remark", how="left")                # kunci: remark
    df = df.merge(fokal, on="event_id", how="left")                # kunci: event_id

    mag_bins = list(kat_mag["min_mag"]) + [float(kat_mag["max_mag"].iloc[-1])]
    df["kategori_magnitudo"] = pd.cut(
        df["magnitudo"], bins=mag_bins, labels=list(kat_mag["label"]), right=False
    )
    dep_bins = list(kat_dep["min_km"]) + [float(kat_dep["max_km"].iloc[-1])]
    df["kategori_kedalaman"] = pd.cut(
        df["kedalaman_km"], bins=dep_bins, labels=list(kat_dep["label"]), right=False
    )
    df["tahun"] = df["waktu_kejadian"].dt.year
    return df


@st.cache_data(show_spinner=False)
def db_stats() -> dict:
    with pg_engine().connect() as conn:
        n_pg = conn.execute(text("SELECT COUNT(*) FROM gempa")).scalar()
        ver = conn.execute(text("SHOW server_version")).scalar()
    with sqlite_engine().connect() as conn:
        n_w = conn.execute(text("SELECT COUNT(*) FROM ref_wilayah")).scalar()
        n_f = conn.execute(text("SELECT COUNT(*) FROM mekanisme_fokal")).scalar()
        sv = conn.execute(text("SELECT sqlite_version()")).scalar()
    return dict(n_pg=n_pg, pg_version=ver, n_wilayah=n_w, n_fokal=n_f, sqlite_version=sv)
