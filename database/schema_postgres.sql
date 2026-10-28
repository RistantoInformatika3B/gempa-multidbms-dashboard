-- ============================================================
-- DBMS 1: PostgreSQL (Neon / Supabase)
-- Peran : data master / transaksi utama -> katalog kejadian gempa
-- ============================================================

CREATE TABLE IF NOT EXISTS gempa (
    event_id        INTEGER          PRIMARY KEY,          -- kunci yang dipakai DBMS 2 (SQLite)
    waktu_kejadian  TIMESTAMP        NOT NULL,             -- origin time (UTC)
    lat             DOUBLE PRECISION NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    kedalaman_km    INTEGER          NOT NULL,
    magnitudo       DOUBLE PRECISION NOT NULL,
    remark          VARCHAR(80)      NOT NULL              -- nama wilayah -> ref_wilayah (SQLite)
);

CREATE INDEX IF NOT EXISTS idx_gempa_waktu    ON gempa (waktu_kejadian);
CREATE INDEX IF NOT EXISTS idx_gempa_magnitud ON gempa (magnitudo);
CREATE INDEX IF NOT EXISTS idx_gempa_remark   ON gempa (remark);
