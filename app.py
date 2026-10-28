"""Dashboard Seismisitas Indonesia - Multi-DBMS (PostgreSQL + SQLite) dengan Streamlit & Plotly."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import db

st.set_page_config(page_title="Seismisitas Indonesia", page_icon="🌏", layout="wide")

MAP_STYLE = "open-street-map"
FAULT_COLORS = {
    "Naik (thrust/reverse)": "#d95f02",
    "Normal": "#1b9e77",
    "Mendatar (strike-slip)": "#7570b3",
}

st.title("🌏 Seismisitas Indonesia 2008–2023")
st.caption(
    "Data master kejadian gempa di **PostgreSQL** digabung dengan metadata wilayah, kategori, "
    "dan mekanisme fokal di **SQLite** melalui Pandas."
)

# ------------------------------------------------------------ koneksi & batas
try:
    bounds = db.pg_bounds()
    ref_wil = db.load_ref_wilayah()
except Exception as e:  # tampilkan pesan yang jelas bila koneksi gagal
    st.error(f"Gagal terhubung ke database: {e}")
    st.stop()

# -------------------------------------------------------------------- filter
st.sidebar.header("Filter")
d_min, d_max = bounds["t0"].date(), bounds["t1"].date()
rentang = st.sidebar.date_input("Rentang tanggal", (d_min, d_max), min_value=d_min, max_value=d_max)
if not (isinstance(rentang, tuple) and len(rentang) == 2):
    st.info("Pilih tanggal awal dan akhir.")
    st.stop()

mag_rng = st.sidebar.slider(
    "Magnitudo", float(bounds["m0"]), float(bounds["m1"]), (3.0, float(bounds["m1"])), 0.1
)
dep_rng = st.sidebar.slider(
    "Kedalaman (km)", int(bounds["d0"]), int(bounds["d1"]), (int(bounds["d0"]), int(bounds["d1"]))
)
kelompok_all = sorted(ref_wil["kelompok_wilayah"].unique())
kelompok = st.sidebar.multiselect("Kelompok wilayah", kelompok_all, default=kelompok_all)
max_pts = st.sidebar.slider("Maks. titik di peta", 1000, 20000, 5000, 1000)

if not kelompok:
    st.warning("Pilih minimal satu kelompok wilayah.")
    st.stop()

# langkah 1 (SQLite): terjemahkan kelompok wilayah -> daftar remark
remarks = tuple(sorted(ref_wil.loc[ref_wil["kelompok_wilayah"].isin(kelompok), "remark"]))
# langkah 2 (PostgreSQL): ambil kejadian dengan filter di sisi server
events = db.query_events(
    pd.Timestamp(rentang[0]),
    pd.Timestamp(rentang[1]) + pd.Timedelta(days=1),
    mag_rng[0], mag_rng[1], dep_rng[0], dep_rng[1], remarks,
)
if events.empty:
    st.warning("Tidak ada kejadian untuk filter ini.")
    st.stop()
# langkah 3 (Pandas): gabungkan dengan referensi SQLite
df = db.build_dataset(events)

# ----------------------------------------------------------------------- KPI
c1, c2, c3, c4 = st.columns(4)
c1.metric("Jumlah kejadian", f"{len(df):,}".replace(",", "."))
c2.metric("Magnitudo maks.", f"{df['magnitudo'].max():.1f}")
c3.metric("Rata-rata kedalaman", f"{df['kedalaman_km'].mean():.0f} km")
c4.metric("Punya mekanisme fokal", f"{df['jenis_sesar'].notna().sum():,}".replace(",", "."))

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Ringkasan", "Peta", "Distribusi", "Mekanisme fokal", "Data & arsitektur"]
)

# ------------------------------------------------------------------ Ringkasan
with tab1:
    monthly = (
        df.assign(bulan=df["waktu_kejadian"].dt.to_period("M").dt.to_timestamp())
        .groupby("bulan").size().reset_index(name="jumlah")
    )
    fig = px.area(monthly, x="bulan", y="jumlah", title="Jumlah gempa per bulan",
                  labels={"bulan": "Bulan", "jumlah": "Jumlah gempa"})
    fig.update_traces(line_color="#c0392b", fillcolor="rgba(192,57,43,0.25)")
    st.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)
    per_wil = df.groupby("kelompok_wilayah").size().reset_index(name="jumlah").sort_values("jumlah")
    fig = px.bar(per_wil, x="jumlah", y="kelompok_wilayah", orientation="h",
                 title="Gempa per kelompok wilayah",
                 labels={"jumlah": "Jumlah gempa", "kelompok_wilayah": ""})
    fig.update_traces(marker_color="#2c7fb8")
    left.plotly_chart(fig, width="stretch")

    top_mag = df.nlargest(10, "magnitudo")[
        ["waktu_kejadian", "remark", "magnitudo", "kedalaman_km"]
    ].rename(columns={"waktu_kejadian": "Waktu (UTC)", "remark": "Wilayah",
                      "magnitudo": "Mag", "kedalaman_km": "Kedalaman (km)"})
    right.markdown("**10 gempa terbesar pada filter ini**")
    right.dataframe(top_mag, hide_index=True, width="stretch")

# ----------------------------------------------------------------------- Peta
with tab2:
    mode = st.radio("Mode peta", ["Titik (gempa terbesar)", "Kepadatan"], horizontal=True)
    if mode.startswith("Titik"):
        pts = df.nlargest(max_pts, "magnitudo")
        fig = px.scatter_map(
            pts, lat="lat", lon="lon", color="magnitudo", size="magnitudo", size_max=14,
            color_continuous_scale="YlOrRd", zoom=3.2, height=620, map_style=MAP_STYLE,
            hover_name="remark",
            hover_data={"waktu_kejadian": True, "kedalaman_km": True, "magnitudo": ":.1f",
                        "lat": False, "lon": False},
            labels={"magnitudo": "Mag"},
        )
        st.caption(f"Menampilkan {len(pts):,} gempa dengan magnitudo terbesar dari {len(df):,}.")
    else:
        pts = df.sample(min(len(df), 50000), random_state=1)
        fig = px.density_map(pts, lat="lat", lon="lon", z="magnitudo", radius=8, zoom=3.2,
                             height=620, map_style=MAP_STYLE, color_continuous_scale="YlOrRd")
        st.caption(f"Kepadatan dari {len(pts):,} titik (sampel acak bila data lebih besar).")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------------------ Distribusi
with tab3:
    a, b = st.columns(2)
    fig = px.histogram(df, x="magnitudo", nbins=40, title="Distribusi magnitudo",
                       labels={"magnitudo": "Magnitudo"})
    fig.update_traces(marker_color="#c0392b")
    a.plotly_chart(fig, width="stretch")

    fig = px.histogram(df, x="kedalaman_km", nbins=50, title="Distribusi kedalaman",
                       labels={"kedalaman_km": "Kedalaman (km)"})
    fig.update_traces(marker_color="#2c7fb8")
    b.plotly_chart(fig, width="stretch")

    kat = (df.groupby(["kelompok_wilayah", "kategori_kedalaman"], observed=True)
             .size().reset_index(name="jumlah"))
    fig = px.bar(kat, x="kelompok_wilayah", y="jumlah", color="kategori_kedalaman",
                 title="Kategori kedalaman per kelompok wilayah",
                 labels={"kelompok_wilayah": "", "jumlah": "Jumlah", "kategori_kedalaman": "Kedalaman"},
                 color_discrete_sequence=["#fdae61", "#d7191c", "#2c7bb6"])
    st.plotly_chart(fig, width="stretch")

    # Hubungan frekuensi-magnitudo (Gutenberg-Richter)
    mags = np.sort(df["magnitudo"].round(1).to_numpy())
    levels = np.round(np.arange(mags.min(), mags.max() + 0.05, 0.1), 1)
    cum = len(mags) - np.searchsorted(mags, levels - 1e-9, side="left")
    vals, counts = np.unique(mags, return_counts=True)
    mc = float(vals[counts.argmax()])  # magnitude of completeness (max curvature)
    sel = mags[mags >= mc]
    b_val = np.log10(np.e) / (sel.mean() - (mc - 0.05)) if len(sel) > 50 else float("nan")
    fig = go.Figure(go.Scatter(x=levels, y=cum, mode="lines+markers", line_color="#c0392b",
                               name="N(M ≥ m)"))
    fig.add_vline(x=mc, line_dash="dash", annotation_text=f"Mc ≈ {mc:.1f}")
    fig.update_yaxes(type="log", title="Jumlah gempa kumulatif (log)")
    fig.update_xaxes(title="Magnitudo")
    fig.update_layout(title=f"Frekuensi–magnitudo (Gutenberg–Richter), b-value ≈ {b_val:.2f}")
    st.plotly_chart(fig, width="stretch")
    st.caption("Mc ditaksir dengan metode maximum curvature; b-value dengan estimator Aki–Utsu. "
               "Nilai ini bersifat indikatif untuk eksplorasi.")

# ------------------------------------------------------------ Mekanisme fokal
with tab4:
    fm = df.dropna(subset=["jenis_sesar"])
    if fm.empty:
        st.info("Tidak ada data mekanisme fokal pada filter ini. Perluas rentang magnitudo/tanggal.")
    else:
        a, b = st.columns(2)
        jenis = fm["jenis_sesar"].value_counts().reset_index()
        jenis.columns = ["jenis_sesar", "jumlah"]
        fig = px.pie(jenis, names="jenis_sesar", values="jumlah", hole=0.45,
                     title="Komposisi jenis sesar", color="jenis_sesar",
                     color_discrete_map=FAULT_COLORS)
        a.plotly_chart(fig, width="stretch")

        bins = np.arange(0, 370, 10)
        fm_s = fm.assign(arah=pd.cut(fm["strike1"], bins=bins, labels=bins[:-1], right=False))
        rose = fm_s.groupby("arah", observed=True).size().reset_index(name="jumlah")
        rose["arah"] = rose["arah"].astype(float)
        fig = px.bar_polar(rose, r="jumlah", theta="arah", title="Arah strike bidang 1 (rose diagram)",
                           color_discrete_sequence=["#7570b3"])
        fig.update_layout(polar=dict(angularaxis=dict(direction="clockwise", rotation=90)))
        b.plotly_chart(fig, width="stretch")

        fig = px.scatter_map(
            fm, lat="lat", lon="lon", color="jenis_sesar", color_discrete_map=FAULT_COLORS,
            size="magnitudo", size_max=14, zoom=3.2, height=560, map_style=MAP_STYLE,
            hover_name="remark",
            hover_data={"magnitudo": ":.1f", "strike1": ":.0f", "dip1": ":.0f", "rake1": ":.0f",
                        "lat": False, "lon": False},
            title="Sebaran gempa menurut jenis sesar",
        )
        fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, width="stretch")

        st.caption("Jenis sesar diturunkan dari sudut rake bidang 1 (thrust 45–135°, normal −135–−45°, "
                   "lainnya strike-slip) sehingga bersifat klasifikasi sederhana.")

# ---------------------------------------------------------- Data & arsitektur
with tab5:
    st.subheader("Alur data")
    st.markdown(
        """
1. **SQLite (DBMS 2)** menerjemahkan *kelompok wilayah* yang dipilih menjadi daftar nama region.
2. **PostgreSQL (DBMS 1)** menerima filter tanggal, magnitudo, kedalaman, dan daftar region (`remark = ANY(...)`).
3. **Pandas** menggabungkan hasilnya dengan `merge()` pada `remark` (wilayah) dan `event_id` (mekanisme fokal),
   lalu memberi label kategori magnitudo/kedalaman dengan `pd.cut()` berdasarkan tabel referensi SQLite.
        """
    )
    try:
        s = db.db_stats()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("PostgreSQL: baris `gempa`", f"{s['n_pg']:,}".replace(",", "."))
        k2.metric("SQLite: `ref_wilayah`", s["n_wilayah"])
        k3.metric("SQLite: `mekanisme_fokal`", f"{s['n_fokal']:,}".replace(",", "."))
        k4.metric("Versi DBMS", f"PG {s['pg_version'].split()[0]} / SQLite {s['sqlite_version']}")
    except Exception as e:
        st.warning(f"Statistik database tidak tersedia: {e}")

    st.subheader("Hasil penggabungan (maks. 1.000 baris)")
    cols = ["event_id", "waktu_kejadian", "lat", "lon", "kedalaman_km", "magnitudo", "remark",
            "kelompok_wilayah", "negara", "kategori_magnitudo", "kategori_kedalaman",
            "jenis_sesar", "strike1", "dip1", "rake1"]
    st.dataframe(df[cols].head(1000), hide_index=True, width="stretch")
    st.download_button("Unduh hasil filter (CSV)", df[cols].to_csv(index=False).encode("utf-8"),
                       file_name="gempa_hasil_filter.csv", mime="text/csv")

    st.subheader("Sumber & referensi")
    st.markdown(
        "- Sumber data: katalog gempa BMKG (lihat README untuk tautan dataset asli).\n"
        "- Kode & dokumentasi lengkap: lihat repositori GitHub pada README."
    )
