"""
terjemah.py — judul dan ringkasan berita Global ke bahasa Indonesia.

Hanya teks yang **tampil** yang diterjemahkan, dan hanya untuk dibaca: penilai
dampak, status arah, dan dedup tetap bekerja atas teks aslinya, dan tautannya
tetap ke artikel penerbit dalam bahasa Inggris. Satu edisi berarti belasan
kalimat pendek (maks ~250 karakter), bukan ratusan artikel.

Semua penyedianya gratis dan tanpa kunci API — proyek ini tidak boleh punya
komponen berbayar. Harganya, tidak ada yang resmi atau dijamin, jadi mereka
dicoba berurutan (`PENYEDIA`) dan yang menolak dilewati untuk sisa edisi itu.

Urutan itu lahir dari kegagalan nyata, 10 Sep 2026: endpoint Google `gtx`
lancar dari jaringan Indonesia tapi membalas 429 ke runner GitHub Actions —
IP pusat data diperlakukan lain. Uji lokal tidak akan pernah menangkap ini.

Seluruh modul disusun supaya kegagalannya **tidak pernah** menggagalkan edisi:
kalau semua penyedia menolak, halaman terbit dalam bahasa aslinya, persis
seperti sebelum modul ini ada.

Hasil disimpan di tabel `terjemahan`. Membangun ulang edisi lama tidak meminta
ulang, dan halaman di `docs/arsip/` sudah memuat terjemahannya sendiri, jadi
arsip tidak ikut rusak kalau penyedianya suatu hari mati.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urlencode

import httpx

from inti.http import Klien

# (nama, fungsi teks -> terjemahan). Fungsi melempar httpx.HTTPError kalau
# penyedianya menolak (pindah ke penyedia berikutnya) dan ValueError kalau satu
# balasan tidak bisa dibaca (lewati kalimat itu saja).
Penyedia = tuple[str, Callable[[str], str]]


def urai(isi: bytes) -> str:
    """Ambil teks terjemahan dari balasan Google `gtx`.

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
    return _tidak_kosong(hasil)


def urai_c5(isi: bytes) -> str:
    """Balasan endpoint Google `dict-chrome-ex`: `["terjemahan"]`, atau
    `[["terjemahan", "en"]]` kalau bahasa sumbernya dideteksi."""
    try:
        pertama = json.loads(isi)[0]
        hasil = pertama if isinstance(pertama, str) else pertama[0]
        if not isinstance(hasil, str):
            raise TypeError(type(hasil))
    except (ValueError, IndexError, TypeError, KeyError) as e:
        raise ValueError(f"balasan terjemahan tidak dikenal: {isi[:80]!r}") from e
    return _tidak_kosong(hasil)


def urai_mymemory(isi: bytes) -> str:
    """Balasan MyMemory. Kuota harian habis (5.000 karakter tanpa akun; satu
    edisi ~1.500) datang sebagai HTTP 200 berisi kalimat peringatan di tempat
    terjemahannya — kalau tidak dicegat, peringatan itu jadi judul berita dan
    tersimpan permanen di cache."""
    try:
        data = json.loads(isi)
        status = int(data.get("responseStatus", 0))
        hasil = unescape(data["responseData"]["translatedText"] or "")
    except (ValueError, TypeError, KeyError, AttributeError) as e:
        raise ValueError(f"balasan terjemahan tidak dikenal: {isi[:80]!r}") from e
    if status != 200 or "MYMEMORY WARNING" in hasil.upper():
        raise httpx.HTTPError(f"MyMemory menolak ({status}): {hasil[:80]}")
    return _tidak_kosong(hasil)


def _tidak_kosong(hasil: str) -> str:
    if not hasil.strip():
        raise ValueError("balasan terjemahan kosong")
    return hasil.strip()


def _penyedia_bawaan(klien: Klien) -> list[Penyedia]:
    def minta(url: str, pengurai: Callable[[bytes], str]) -> str:
        r = klien.ambil(url)
        if not r.berhasil:
            raise httpx.HTTPError(f"HTTP {r.status}")
        return pengurai(r.isi)

    def google(t: str) -> str:
        kueri = urlencode({"client": "gtx", "sl": "en", "tl": "id", "dt": "t", "q": t})
        return minta(f"https://translate.googleapis.com/translate_a/single?{kueri}", urai)

    def google_c5(t: str) -> str:
        kueri = urlencode({"client": "dict-chrome-ex", "sl": "en", "tl": "id", "q": t})
        return minta(f"https://clients5.google.com/translate_a/t?{kueri}", urai_c5)

    def mymemory(t: str) -> str:
        kueri = urlencode({"q": t, "langpair": "en|id"})
        return minta(f"https://api.mymemory.translated.net/get?{kueri}", urai_mymemory)

    # Google dulu karena terjemahannya paling luwes; MyMemory terakhir karena
    # kuotanya berbatas dan tanda bacanya kadang janggal ("$ 100").
    return [("google", google), ("google-c5", google_c5), ("mymemory", mymemory)]


def terjemahkan(
    con, teks: list[str], penyedia: Sequence[Penyedia] | None = None
) -> dict[str, str]:
    """asli -> terjemahan. Yang gagal tidak ada di hasil; pemanggil memakai aslinya.

    `penyedia` bisa diganti di uji supaya tidak menyentuh jaringan.
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
    dipakai: Counter[str] = Counter()
    klien = None
    if penyedia is None:
        klien = Klien()
        penyedia = _penyedia_bawaan(klien)
    try:
        i = 0
        for t in kurang:
            while i < len(penyedia):
                nama, minta = penyedia[i]
                try:
                    baru[t] = minta(t)
                    dipakai[nama] += 1
                    break
                except httpx.HTTPError as e:
                    # Penolakan atau jaringan: kalimat berikutnya hampir pasti
                    # bernasib sama. Klien sudah mencoba ulang tiga kali, jadi
                    # penyedia ini dilewati untuk sisa edisi.
                    print(f"terjemahan: {nama} menolak ({e})")
                    i += 1
                except ValueError as e:
                    # Satu balasan aneh bukan alasan membuang penyedianya.
                    print(f"terjemahan: {nama} melewati satu kalimat ({e})")
                    break
            if i >= len(penyedia):
                break
    finally:
        if klien is not None:
            klien.tutup()

    if dipakai:
        print("terjemahan: " + ", ".join(f"{n} {k}" for n, k in dipakai.items()))
    if baru:
        sekarang = datetime.now(timezone.utc).replace(tzinfo=None)
        con.executemany(
            """INSERT INTO terjemahan (asli, hasil, waktu) VALUES (?,?,?)
               ON CONFLICT (asli) DO NOTHING""",
            [(a, h, sekarang) for a, h in baru.items()],
        )
    return hasil | baru
