-- ============================================================
-- DBMS 2: SQLite (embedded, file: data/referensi.sqlite)
-- Peran : metadata referensi + data analitik pendukung
--         (wilayah, kategori, mekanisme fokal)
-- ============================================================

CREATE TABLE IF NOT EXISTS ref_wilayah (
    remark           TEXT PRIMARY KEY,      -- sama dengan gempa.remark di PostgreSQL
    kelompok_wilayah TEXT NOT NULL,         -- Sumatra, Jawa, Sulawesi, ...
    negara           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ref_kategori_magnitudo (
    urutan   INTEGER PRIMARY KEY,
    label    TEXT NOT NULL,
    min_mag  REAL NOT NULL,                 -- inklusif
    max_mag  REAL NOT NULL                  -- eksklusif
);

CREATE TABLE IF NOT EXISTS ref_kategori_kedalaman (
    urutan   INTEGER PRIMARY KEY,
    label    TEXT NOT NULL,
    min_km   REAL NOT NULL,                 -- inklusif
    max_km   REAL NOT NULL                  -- eksklusif
);

CREATE TABLE IF NOT EXISTS mekanisme_fokal (
    event_id    INTEGER PRIMARY KEY,        -- merujuk gempa.event_id di PostgreSQL
    strike1     REAL, dip1 REAL, rake1 REAL,
    strike2     REAL, dip2 REAL, rake2 REAL,
    jenis_sesar TEXT NOT NULL               -- turunan dari rake1
);
