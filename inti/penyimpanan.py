"""
penyimpanan.py — bronze (mentah) di filesystem, sisanya di DuckDB.

ARSITEKTUR.md §5: menyimpan raw itu wajib, bukan opsional. Parser akan salah dan
situs akan berubah; kalau raw ada, memperbaiki parser berarti *re-parse* — murah
dan retroaktif. Kalau tidak, berarti *re-scrape*, dan itu sering mustahil.

Bersama tiap objek bronze disimpan: URL, waktu fetch (UTC), status HTTP, ETag,
Last-Modified, dan SHA-256 isi. Hash itu kunci dedup sekaligus deteksi perubahan.

Tabel di DuckDB (§7 — tanpa server, satu berkas yang bisa di-backup dengan copy):

    artikel     satu baris per URL kanonik, isinya tidak pernah di-UPDATE
    feed_state  ETag/Last-Modified terakhir per feed, untuk conditional request
    metrik_run  satu baris per feed per run (§12)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb

AKAR = Path("data")

SKEMA = """
CREATE TABLE IF NOT EXISTS artikel (
    artikel_id    VARCHAR PRIMARY KEY,   -- sha256(url kanonik)
    url           VARCHAR NOT NULL,
    domain        VARCHAR NOT NULL,
    judul         VARCHAR NOT NULL,
    ringkasan     VARCHAR,
    waktu_terbit  TIMESTAMP,             -- UTC polos; NULL kalau feed tidak memberi
    waktu_fetch   TIMESTAMP NOT NULL,    -- UTC polos
    feed          VARCHAR NOT NULL,
    kategori      VARCHAR NOT NULL,
    bobot         DOUBLE  NOT NULL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS feed_state (
    url             VARCHAR PRIMARY KEY,
    etag            VARCHAR,
    last_modified   VARCHAR,
    hash_isi        VARCHAR,
    terakhir_sukses TIMESTAMP
);

CREATE TABLE IF NOT EXISTS metrik_run (
    run_id       VARCHAR NOT NULL,
    feed         VARCHAR NOT NULL,
    waktu        TIMESTAMP NOT NULL,
    status       VARCHAR NOT NULL,      -- ok | 304 | galat
    jumlah_item  INTEGER NOT NULL DEFAULT 0,
    jumlah_baru  INTEGER NOT NULL DEFAULT 0,
    durasi       DOUBLE  NOT NULL DEFAULT 0,
    catatan      VARCHAR
);
"""


@dataclass(slots=True)
class Artikel:
    artikel_id: str
    url: str
    domain: str
    judul: str
    ringkasan: str | None
    waktu_terbit: datetime | None
    waktu_fetch: datetime
    feed: str
    kategori: str
    bobot: float = 1.0


def buka(berkas: Path | str | None = None) -> duckdb.DuckDBPyConnection:
    # Dibaca saat dipanggil, bukan saat def. Kalau AKAR jadi nilai default
    # argumen, ia terikat sejak import dan uji tidak bisa mengalihkannya ke
    # direktori sementara — uji akan menulis ke data/ sungguhan.
    berkas = Path(berkas) if berkas else AKAR / "makro.duckdb"
    berkas.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(berkas))
    con.execute(SKEMA)
    return con


def simpan_bronze(sumber: str, respons, akar: Path | None = None) -> Path:
    """Tulis isi mentah + metadata fetch. Nama berkas memakai hash isi.

    Kalau hash sudah ada, berkasnya tidak ditulis ulang — isi yang sama tidak
    perlu disimpan dua kali, dan ini yang membuat job idempoten (§9 #7).
    """
    akar = akar or AKAR  # lihat catatan di buka()
    waktu = respons.waktu
    folder = akar / "bronze" / _slug(sumber) / f"{waktu:%Y}" / f"{waktu:%m}"
    folder.mkdir(parents=True, exist_ok=True)

    nama = f"{waktu:%Y%m%dT%H%M%SZ}_{respons.hash_isi[:12]}"
    berkas = folder / f"{nama}.xml"
    if berkas.exists():
        return berkas

    berkas.write_bytes(respons.isi)
    (folder / f"{nama}.json").write_text(
        json.dumps(
            {
                "sumber": sumber,
                "url": respons.url,
                "status": respons.status,
                "waktu_fetch": waktu.isoformat(),
                "etag": respons.etag,
                "last_modified": respons.last_modified,
                "sha256": respons.hash_isi,
                "bytes": len(respons.isi),
                "durasi_detik": round(respons.durasi, 3),
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return berkas


def simpan_artikel(con: duckdb.DuckDBPyConnection, artikel: list[Artikel]) -> int:
    """Sisipkan artikel baru. Yang sudah ada dibiarkan — tabel ini append-only.

    Mengembalikan jumlah baris yang benar-benar baru.
    """
    if not artikel:
        return 0
    sebelum = con.execute("SELECT count(*) FROM artikel").fetchone()[0]
    con.executemany(
        """INSERT INTO artikel
           (artikel_id, url, domain, judul, ringkasan, waktu_terbit,
            waktu_fetch, feed, kategori, bobot)
           VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT (artikel_id) DO NOTHING""",
        # Kolomnya ditulis satu per satu, bukan asdict().values(), supaya
        # menambah field di dataclass tidak diam-diam menggeser urutan kolom.
        [
            (
                a.artikel_id, a.url, a.domain, a.judul, a.ringkasan,
                _utc_polos(a.waktu_terbit), _utc_polos(a.waktu_fetch),
                a.feed, a.kategori, a.bobot,
            )
            for a in artikel
        ],
    )
    return con.execute("SELECT count(*) FROM artikel").fetchone()[0] - sebelum


def ambil_state(con: duckdb.DuckDBPyConnection, url: str) -> tuple[str | None, str | None]:
    baris = con.execute(
        "SELECT etag, last_modified FROM feed_state WHERE url = ?", [url]
    ).fetchone()
    return (baris[0], baris[1]) if baris else (None, None)


def simpan_state(
    con: duckdb.DuckDBPyConnection,
    url: str,
    etag: str | None,
    last_modified: str | None,
    hash_isi: str | None,
) -> None:
    con.execute(
        """INSERT INTO feed_state (url, etag, last_modified, hash_isi, terakhir_sukses)
           VALUES (?,?,?,?,?)
           ON CONFLICT (url) DO UPDATE SET
             etag = excluded.etag,
             last_modified = excluded.last_modified,
             hash_isi = excluded.hash_isi,
             terakhir_sukses = excluded.terakhir_sukses""",
        [url, etag, last_modified, hash_isi, _sekarang()],
    )


def catat_run(
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    feed: str,
    status: str,
    *,
    jumlah_item: int = 0,
    jumlah_baru: int = 0,
    durasi: float = 0.0,
    catatan: str | None = None,
) -> None:
    """§12 — inilah yang membuat 'feed X pelan-pelan menghasilkan lebih sedikit
    data sejak Juli' bisa terlihat."""
    con.execute(
        """INSERT INTO metrik_run
           (run_id, feed, waktu, status, jumlah_item, jumlah_baru, durasi, catatan)
           VALUES (?,?,?,?,?,?,?,?)""",
        [run_id, feed, _sekarang(), status,
         jumlah_item, jumlah_baru, durasi, catatan],
    )


def _utc_polos(dt: datetime | None) -> datetime | None:
    """Datetime beroffset -> UTC polos (naive).

    §15 #9 memutuskan satu zona di semua lapisan — UTC — dan konversi ke WIB
    hanya saat tampil. Karena semuanya UTC, kolom TIMESTAMP polos tidak ambigu,
    dan itu menghindari `TIMESTAMPTZ` DuckDB yang menuntut `pytz` hanya untuk
    mengembalikan nilainya ke Python.
    """
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def _sekarang() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _slug(teks: str) -> str:
    aman = [c if c.isalnum() or c in "-_" else "-" for c in teks.lower()]
    return "".join(aman).strip("-") or "tanpa-nama"
