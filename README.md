# Seismisitas Indonesia 2008–2023: Multi-DBMS Data Pipeline & Web Visualization

Tugas Mandiri Terstruktur – Visualisasi Data dan Informasi (Informatika)

- **Nama / NIM**: `Ristanto` / `230660121089`
- **Live app**: `https://seismisitas-indonesia.streamlit.app`
- **Repositori**: `https://github.com/RistantoInformatika3B/gempa-multidbms-dashboard`

Dashboard interaktif yang menggabungkan **PostgreSQL** (data master kejadian gempa) dan
**SQLite** (metadata referensi + mekanisme fokal) pada level aplikasi menggunakan **Pandas**,
lalu menyajikannya dengan **Streamlit + Plotly**.

## 1. Skenario & alasan pemisahan DBMS

| | DBMS 1: PostgreSQL | DBMS 2: SQLite |
|---|---|---|
| **Host** | Cloud (Neon/Supabase, gratis) | File embedded `data/referensi.sqlite` (ikut di repositori, read-only) |
| **Fungsi** | Data master/transaksi: tabel `gempa` (92.887 kejadian: waktu, koordinat, kedalaman, magnitudo, wilayah) | Metadata & data analitik pendukung: `ref_wilayah`, `ref_kategori_magnitudo`, `ref_kategori_kedalaman`, `mekanisme_fokal` (2.735 baris strike/dip/rake) |
| **Alasan** | Volume besar, perlu indeks & filter server-side, data terus bertambah | Data kecil, hampir statis, dipakai sebagai lookup/dimensi; tidak perlu server terpisah |
| **Kunci relasi** | `gempa.event_id`, `gempa.remark` | `mekanisme_fokal.event_id`, `ref_wilayah.remark` |

## 2. Alur integrasi (data pipeline)

```
katalog_gempa.csv ──seed_data.py──┬─► PostgreSQL: gempa
                                  └─► SQLite: ref_*, mekanisme_fokal

Aplikasi (setiap perubahan filter):
 1. SQLite     : kelompok wilayah  ──► daftar `remark`
 2. PostgreSQL : SELECT ... WHERE waktu/magnitudo/kedalaman
                 AND remark = ANY(:remarks)        (predicate pushdown)
 3. Pandas     : events.merge(ref_wilayah,  on="remark")
                       .merge(mekanisme_fokal, on="event_id")
                 + pd.cut() untuk kategori magnitudo/kedalaman (dari tabel referensi SQLite)
 4. Plotly     : peta, time series, distribusi, Gutenberg–Richter, rose diagram
```

Kode terkait: `db.py` (koneksi, query, `build_dataset()`) dan `app.py` (UI & visualisasi).

## 3. Fitur interaktivitas

- Filter rentang tanggal, magnitudo, kedalaman, dan kelompok wilayah (sidebar).
- Peta titik (gempa terbesar) dan peta kepadatan, dengan hover detail.
- Grafik jumlah gempa per bulan, per wilayah, distribusi magnitudo/kedalaman.
- Hubungan frekuensi–magnitudo (Gutenberg–Richter) dengan estimasi Mc dan b-value.
- Analisis mekanisme fokal: komposisi jenis sesar, rose diagram strike, peta per jenis sesar.
- Tabel hasil penggabungan dan tombol unduh CSV.

## 4. Struktur repositori

```
app.py                       # UI Streamlit + visualisasi
db.py                        # koneksi PostgreSQL & SQLite + penggabungan Pandas
requirements.txt
database/
  schema_postgres.sql        # DDL DBMS 1
  schema_sqlite.sql          # DDL DBMS 2
  seed_data.py               # memuat CSV ke kedua DBMS
data/
  katalog_gempa.csv          # data mentah
  referensi.sqlite           # hasil seed SQLite (di-commit agar app cloud bisa membacanya)
.streamlit/secrets.toml.example
```

## 5. Menjalankan secara lokal

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# URL PostgreSQL (jangan di-commit). Neon/Supabase memakai sslmode=require
export DATABASE_URL="postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"

python database/seed_data.py --target all     # isi PostgreSQL + buat data/referensi.sqlite
streamlit run app.py
```

Alternatifnya, salin `.streamlit/secrets.toml.example` menjadi `.streamlit/secrets.toml`.
Kredensial **tidak pernah di-hardcode**: dibaca dari `DATABASE_URL` atau `st.secrets`.

## 6. Deploy (Streamlit Community Cloud)

1. Buat database gratis di Neon atau Supabase, salin connection string-nya.
2. Jalankan `seed_data.py` dari komputer Anda dengan `DATABASE_URL` tersebut.
3. Push repositori ke GitHub (pastikan `data/referensi.sqlite` ikut ter-commit).
4. Di Streamlit Community Cloud pilih repositori → file utama `app.py`.
5. Pada *App settings → Secrets* isi:
   ```toml
   [postgres]
   url = "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
   ```

## 7. Sumber data (primer)

- Dataset katalog gempa: [Earthquakes in Indonesia (Kaggle, kekavigi)](https://www.kaggle.com/datasets/kekavigi/earthquakes-in-indonesia), file `katalog_gempa.csv`.
- Rentang data: 2008-11-01 s.d. 2023-01-26, 92.887 kejadian; 2.735 di antaranya memiliki solusi mekanisme fokal.
- Pengelompokan wilayah (`ref_wilayah`) dan kelas magnitudo/kedalaman dibuat penulis berdasarkan nama region pada katalog dan klasifikasi umum (bersifat pendekatan).

## 8. Referensi kode / inspirasi

- Streamlit – Connect to PostgreSQL: https://docs.streamlit.io/develop/tutorials/databases/postgresql
- Streamlit – Connect to Neon: https://docs.streamlit.io/develop/tutorials/databases/neon
- Plotly – Density heatmaps / map layers: https://plotly.com/python/density-heatmaps/

## 9. Catatan & keterbatasan

- Waktu kejadian (`ot`) diperlakukan sebagai UTC sebagaimana katalog sumber.
- Jenis sesar diturunkan dari sudut *rake* bidang 1 (klasifikasi sederhana).
- Mc (magnitude of completeness) memakai metode *maximum curvature* dan b-value memakai estimator Aki–Utsu; hasilnya indikatif.
