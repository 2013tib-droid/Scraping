"""
terjemah.py — judul dan ringkasan berita Global ke bahasa Indonesia.

Hanya teks yang **tampil** yang diterjemahkan, dan hanya untuk dibaca: penilai
dampak, status arah, dan dedup tetap bekerja atas teks aslinya, dan tautannya
tetap ke artikel penerbit dalam bahasa Inggris. Satu edisi berarti belasan
kalimat pendek (maks ~250 karakter), bukan ratusan artikel.

Penyedianya endpoint publik Google Translate (`client=gtx`): gratis, tanpa kunci
API, tanpa akun penagihan — proyek ini tidak boleh punya komponen berbayar.
Harganya, endpoint ini tidak resmi. Ia bisa berubah bentuk atau mulai menolak
kapan saja, jadi seluruh modul disusun supaya kegagalannya **tidak pernah**
menggagalkan edisi: yang tidak berhasil diterjemahkan tampil dalam bahasa
aslinya, persis seperti sebelum modul ini ada.

Hasil disimpan di tabel `terjemahan`. Membangun ulang edisi lama tidak meminta
ulang, dan halaman di `docs/arsip/` sudah memuat terjemahannya sendiri, jadi
arsip tidak ikut rusak kalau endpoint-nya suatu hari mati.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

from inti.http import Klien

ENDPOINT = "https://translate.googleapis.com/translate_a/single"


def urai(isi: bytes) -> str:
    """Ambil teks terjemahan dari balasan gtx.

    Bentuknya `[[["kalimat 1", "asli 1", ...], ["kalimat 2", ...]], ...]` — satu
    potongan per kalimat, disambung kembali. Melempar ValueError kalau
    bentuknya lain, supaya perubahan format terlihat sebagai galat, bukan
    sebagai judul kosong di halaman.
    """
    try:
        potongan = json.loads(isi)[0]
        hasil = "".join(p[0] for p in potongan if p and isinstance(p[0], str))
    except (ValueError, IndexError, TypeError, KeyError) as e:
        raise ValueError(f"balasan terjemahan tidak dikenal: {isi[:80]!r}") from e
    if not hasil.strip():
        raise ValueError("balasan terjemahan kosong")
    return hasil.strip()


def _minta(klien: Klien, teks: str) -> str:
    kueri = urlencode({"client": "gtx", "sl": "en", "tl": "id", "dt": "t", "q": teks})
    r = klien.ambil(f"{ENDPOINT}?{kueri}")
    if not r.berhasil:
        raise httpx.HTTPError(f"HTTP {r.status}")
    return urai(r.isi)


def terjemahkan(
    con, teks: list[str], minta: Callable[[str], str] | None = None
) -> dict[str, str]:
    """asli -> terjemahan. Yang gagal tidak ada di hasil; pemanggil memakai aslinya.

    `minta` bisa diganti di uji supaya tidak menyentuh jaringan.
    """
    unik = list(dict.fromkeys(t for t in teks if t and t.strip()))
    if not unik:
        return {}

    hasil: dict[str, str] = dict(
        con.execute(
            "SELECT asli, hasil FROM terjemahan WHERE list_contains(?, asli)", [unik]
        ).fetchall()
    )
    kurang = [t for t in unik if t not in hasil]
    if not kurang:
        return hasil

    baru: dict[str, str] = {}
    klien = None
    if minta is None:
        klien = Klien()
        minta = lambda t: _minta(klien, t)  # noqa: E731
    try:
        for t in kurang:
            try:
                baru[t] = minta(t)
            except httpx.HTTPError as e:
                # Jaringan atau penolakan: sisanya hampir pasti bernasib sama.
                # Klien sudah mencoba ulang tiga kali; lanjut berarti menunggu
                # backoff yang sama untuk tiap kalimat tersisa.
                print(f"terjemahan berhenti: {e}")
                break
            except ValueError as e:
                # Satu balasan aneh bukan alasan membuang yang lain.
                print(f"terjemahan dilewati: {e}")
    finally:
        if klien is not None:
            klien.tutup()

    if baru:
        sekarang = datetime.now(timezone.utc).replace(tzinfo=None)
        con.executemany(
            """INSERT INTO terjemahan (asli, hasil, waktu) VALUES (?,?,?)
               ON CONFLICT (asli) DO NOTHING""",
            [(a, h, sekarang) for a, h in baru.items()],
        )
    return hasil | baru
