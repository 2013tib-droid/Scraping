"""
reparse.py — urai ulang bronze yang sudah tersimpan, isi kolom yang masih kosong.

Ini janji ARSITEKTUR.md §5 yang ditagih: raw disimpan justru supaya parser yang
diperbaiki bulan depan bisa dijalankan ulang ke data lama. Tanpa bronze, satu-
satunya cara mengisi kolom `gambar` untuk artikel kemarin adalah mengambil ulang
feed-nya — dan feed hanya memuat ~100 item terakhir, jadi yang lewat hilang
selamanya.

Dipakai sekali setelah kolom baru ditambahkan. Bukan bagian dari cron: kalau ini
harus jalan tiap hari, yang salah parsernya, bukan datanya.

    python -m alur.reparse            # semua bronze
    python -m alur.reparse 2026/09    # batasi ke satu bulan

**Hanya mengisi yang NULL, tidak pernah menimpa.** `artikel` append-only (§5),
dan pengecualian di sini sempit dengan sengaja: mengisi lubang berbeda dari
menulis ulang sejarah. Kalau parsernya nanti salah, yang terisi salah tetap bisa
dikosongkan lalu diisi ulang dari bronze yang sama.
"""

from __future__ import annotations

import sys
from hashlib import sha256
from pathlib import Path

import feedparser

from alur.berita import gambar, kanonik
from inti.penyimpanan import AKAR, buka


def berkas_bronze(pola: str | None = None, akar: Path | None = None) -> list[Path]:
    """Semua XML bronze, terlama dulu supaya versi terbaru dari satu artikel
    yang menang — nama berkas diawali stempel waktu, jadi urutan leksikografis
    sudah urutan waktu."""
    akar = akar or AKAR
    return sorted((akar / "bronze").glob(f"*/{pola or '**'}/*.xml"))


def petakan(berkas: list[Path]) -> dict[str, str]:
    """artikel_id -> URL gambar, dari seluruh bronze yang diurai ulang."""
    peta: dict[str, str] = {}
    for f in berkas:
        try:
            terurai = feedparser.parse(f.read_bytes())
        except Exception:  # noqa: BLE001 — satu berkas rusak bukan alasan berhenti
            continue
        for e in terurai.entries:
            tautan = (e.get("link") or "").strip()
            if not tautan:
                continue
            if url := gambar(e):
                peta[sha256(kanonik(tautan).encode("utf-8")).hexdigest()] = url
    return peta


def isi(con, peta: dict[str, str]) -> int:
    """Isi `gambar` yang masih NULL. Mengembalikan jumlah baris yang berubah."""
    if not peta:
        return 0
    sebelum = con.execute(
        "SELECT count(*) FROM artikel WHERE gambar IS NOT NULL"
    ).fetchone()[0]
    con.executemany(
        "UPDATE artikel SET gambar = ? WHERE artikel_id = ? AND gambar IS NULL",
        [(url, aid) for aid, url in peta.items()],
    )
    return con.execute(
        "SELECT count(*) FROM artikel WHERE gambar IS NOT NULL"
    ).fetchone()[0] - sebelum


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    berkas = berkas_bronze(argv[0] if argv else None)
    if not berkas:
        print("tidak ada bronze yang cocok")
        return 1

    peta = petakan(berkas)
    con = buka()
    try:
        terisi = isi(con, peta)
        total, punya = con.execute(
            "SELECT count(*), count(gambar) FROM artikel"
        ).fetchone()
    finally:
        con.close()

    print(
        f"{len(berkas)} berkas bronze -> {len(peta)} artikel bergambar di feed; "
        f"{terisi} baris terisi.\n"
        f"tabel artikel: {punya}/{total} punya gambar "
        f"({100 * punya // max(total, 1)}%)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
