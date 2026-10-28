"""
Seed script untuk dua DBMS.

  python database/seed_data.py --target all        # PostgreSQL + SQLite
  python database/seed_data.py --target sqlite     # hanya SQLite (data/referensi.sqlite)
  python database/seed_data.py --target postgres   # hanya PostgreSQL

Koneksi PostgreSQL dibaca dari environment variable DATABASE_URL, misalnya:
  postgresql://user:password@host/dbname?sslmode=require
"""
import argparse
import io
import os
import sqlite3
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "katalog_gempa.csv"
SQLITE_PATH = Path(os.environ.get("SQLITE_PATH", ROOT / "data" / "referensi.sqlite"))
PG_SCHEMA = ROOT / "database" / "schema_postgres.sql"
SQLITE_SCHEMA = ROOT / "database" / "schema_sqlite.sql"

# --- Pemetaan nama wilayah (kolom `remark`) ke kelompok wilayah ---------------
# Pengelompokan ini bersifat pendekatan (berdasarkan nama region katalog).
WILAYAH = {
    # Sumatra
    "Northern Sumatra - Indonesia": ("Sumatra", "Indonesia"),
    "Southern Sumatra - Indonesia": ("Sumatra", "Indonesia"),
    "Off West Coast of Northern Sumatra": ("Sumatra", "Indonesia"),
    "Southwest of Sumatra - Indonesia": ("Sumatra", "Indonesia"),
    # Jawa
    "Java - Indonesia": ("Jawa", "Indonesia"),
    "South of Java - Indonesia": ("Jawa", "Indonesia"),
    "Sunda Strait - Indonesia": ("Jawa", "Indonesia"),
    "Java Sea": ("Jawa", "Indonesia"),
    # Bali & Nusa Tenggara
    "Bali Region - Indonesia": ("Bali & Nusa Tenggara", "Indonesia"),
    "South of Bali - Indonesia": ("Bali & Nusa Tenggara", "Indonesia"),
    "Bali Sea": ("Bali & Nusa Tenggara", "Indonesia"),
    "Sumbawa Region - Indonesia": ("Bali & Nusa Tenggara", "Indonesia"),
    "South of Sumbawa - Indonesia": ("Bali & Nusa Tenggara", "Indonesia"),
    "Flores Region - Indonesia": ("Bali & Nusa Tenggara", "Indonesia"),
    "Flores Sea": ("Bali & Nusa Tenggara", "Indonesia"),
    "Sumba Region - Indonesia": ("Bali & Nusa Tenggara", "Indonesia"),
    "Savu Sea": ("Bali & Nusa Tenggara", "Indonesia"),
    "Timor Region": ("Bali & Nusa Tenggara", "Indonesia"),
    "Timor Sea": ("Bali & Nusa Tenggara", "Indonesia"),
    # Kalimantan
    "Borneo": ("Kalimantan", "Indonesia"),
    # Sulawesi
    "Minahassa Peninsula - Sulawesi": ("Sulawesi", "Indonesia"),
    "Sulawesi - Indonesia": ("Sulawesi", "Indonesia"),
    "Celebes Sea": ("Sulawesi", "Indonesia"),
    "Talaud Islands - Indonesia": ("Sulawesi", "Indonesia"),
    # Maluku
    "Banda Sea": ("Maluku", "Indonesia"),
    "Northern Molucca Sea": ("Maluku", "Indonesia"),
    "Southern Molucca Sea": ("Maluku", "Indonesia"),
    "Seram - Indonesia": ("Maluku", "Indonesia"),
    "Ceram Sea": ("Maluku", "Indonesia"),
    "Halmahera - Indonesia": ("Maluku", "Indonesia"),
    "North of Halmahera - Indonesia": ("Maluku", "Indonesia"),
    "Buru - Indonesia": ("Maluku", "Indonesia"),
    "Tanimbar Islands Reg. - Indonesia": ("Maluku", "Indonesia"),
    "Aru Islands Region - Indonesia": ("Maluku", "Indonesia"),
    # Papua
    "Irian Jaya Region - Indonesia": ("Papua", "Indonesia"),
    "Irian Jaya - Indonesia": ("Papua", "Indonesia"),
    "Near North Coast of Irian Jaya": ("Papua", "Indonesia"),
    "Near South Coast of Irian Jaya": ("Papua", "Indonesia"),
    "Arafura Sea": ("Papua", "Indonesia"),
    # Luar Indonesia
    "Mindanao - Philippines": ("Luar Indonesia", "Filipina"),
    "Philippine Islands Region": ("Luar Indonesia", "Filipina"),
    "East of Philippine Islands": ("Luar Indonesia", "Filipina"),
    "Sulu Archipelago - Philippines": ("Luar Indonesia", "Filipina"),
    "New Guinea - Papua New Guinea": ("Luar Indonesia", "Papua Nugini"),
    "Near N. Coast of New Guinea - PNG.": ("Luar Indonesia", "Papua Nugini"),
    "Near S. Coast of New Guinea - PNG.": ("Luar Indonesia", "Papua Nugini"),
    "Ninigo Islands Region - P.N.G.": ("Luar Indonesia", "Papua Nugini"),
    "W. Caroline Islands - Micronesia": ("Luar Indonesia", "Mikronesia"),
    "Malay Peninsula": ("Luar Indonesia", "Malaysia"),
    "South China Sea": ("Luar Indonesia", "Perairan Internasional"),
    "South Indian Ocean": ("Luar Indonesia", "Perairan Internasional"),
}

# Kelas magnitudo (mengacu pada klasifikasi umum USGS) dan kelas kedalaman
KAT_MAG = [
    (1, "Mikro (<3)", 0.0, 3.0),
    (2, "Minor (3-3,9)", 3.0, 4.0),
    (3, "Ringan (4-4,9)", 4.0, 5.0),
    (4, "Sedang (5-5,9)", 5.0, 6.0),
    (5, "Kuat (6-6,9)", 6.0, 7.0),
    (6, "Besar (>=7)", 7.0, 99.0),
]
KAT_DEPTH = [
    (1, "Dangkal (<70 km)", 0.0, 70.0),
    (2, "Menengah (70-300 km)", 70.0, 300.0),
    (3, "Dalam (>300 km)", 300.0, 9999.0),
]


def jenis_sesar(rake: float) -> str:
    """Klasifikasi sederhana jenis sesar dari sudut rake bidang 1."""
    if 45 <= rake <= 135:
        return "Naik (thrust/reverse)"
    if -135 <= rake <= -45:
        return "Normal"
    return "Mendatar (strike-slip)"


def load_catalog() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)
    df["waktu_kejadian"] = pd.to_datetime(
        df["tgl"] + " " + df["ot"], format="%Y/%m/%d %H:%M:%S.%f"
    )
    df = df.sort_values("waktu_kejadian").reset_index(drop=True)
    df["event_id"] = df.index + 1  # kunci deterministik lintas DBMS
    unknown = set(df["remark"]) - set(WILAYAH)
    if unknown:
        raise ValueError(f"Wilayah belum dipetakan: {unknown}")
    return df


def seed_postgres(df: pd.DataFrame) -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Set environment variable DATABASE_URL terlebih dahulu.")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    engine = create_engine(url)

    out = df.rename(columns={"depth": "kedalaman_km", "mag": "magnitudo"})[
        ["event_id", "waktu_kejadian", "lat", "lon", "kedalaman_km", "magnitudo", "remark"]
    ]
    buf = io.StringIO()
    out.to_csv(buf, index=False, header=False)
    buf.seek(0)

    conn = engine.raw_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(PG_SCHEMA.read_text())
            cur.execute("TRUNCATE TABLE gempa")
            cur.copy_expert(
                "COPY gempa (event_id, waktu_kejadian, lat, lon, kedalaman_km, magnitudo, remark) "
                "FROM STDIN WITH (FORMAT csv)",
                buf,
            )
        conn.commit()
    finally:
        conn.close()
    print(f"[PostgreSQL] gempa: {len(out):,} baris dimuat")


def seed_sqlite(df: pd.DataFrame) -> None:
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SQLITE_PATH.exists():
        SQLITE_PATH.unlink()
    con = sqlite3.connect(SQLITE_PATH)
    try:
        con.executescript(SQLITE_SCHEMA.read_text())
        con.executemany(
            "INSERT INTO ref_wilayah VALUES (?,?,?)",
            [(k, v[0], v[1]) for k, v in WILAYAH.items()],
        )
        con.executemany("INSERT INTO ref_kategori_magnitudo VALUES (?,?,?,?)", KAT_MAG)
        con.executemany("INSERT INTO ref_kategori_kedalaman VALUES (?,?,?,?)", KAT_DEPTH)

        fm = df.dropna(subset=["strike1"]).copy()
        fm["jenis_sesar"] = fm["rake1"].apply(jenis_sesar)
        fm = fm[
            ["event_id", "strike1", "dip1", "rake1", "strike2", "dip2", "rake2", "jenis_sesar"]
        ]
        fm.to_sql("mekanisme_fokal", con, if_exists="append", index=False)
        con.commit()
        con.execute("VACUUM")
    finally:
        con.close()
    print(f"[SQLite] {SQLITE_PATH.name}: {len(WILAYAH)} wilayah, {len(fm):,} mekanisme fokal")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["all", "postgres", "sqlite"], default="all")
    args = ap.parse_args()
    catalog = load_catalog()
    if args.target in ("all", "sqlite"):
        seed_sqlite(catalog)
    if args.target in ("all", "postgres"):
        seed_postgres(catalog)
