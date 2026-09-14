"""Uji `inti/musibah.py` dan dua tempat yang memakainya.

Uji regresi dari kasus nyata: KM Virgo Transport 8 terbalik di Laut Jawa
membawa 243 penumpang pada 13 Sep 2026, dan tidak satu pun beritanya masuk
halaman pagi — dibuang `relevan()` di alur/edisi.py sekaligus dinilai 0 oleh
inti/dampak.py karena beritanya menyebut "kecelakaan".
"""

from datetime import date, datetime

import pytest

from alur import edisi
from inti import dampak, musibah, penyimpanan
from inti.penyimpanan import Artikel


@pytest.fixture
def con(tmp_path):
    c = penyimpanan.buka(tmp_path / "uji.duckdb")
    yield c
    c.close()


def peristiwa(judul, url="u1", *, ringkasan="isi", jumlah_media=1):
    return edisi.Peristiwa(
        judul=judul, url=url, domain="a.test", ringkasan=ringkasan,
        waktu_terbit=datetime(2026, 9, 8, 10, 0), kategori="politik",
        jumlah_media=jumlah_media, bobot=1.0,
    )


def artikel(judul, domain, jam_utc, ringkasan="isi"):
    return Artikel(
        artikel_id=f"{domain}:{judul}"[:60],
        url=f"https://{domain}/{abs(hash(judul)) % 99999}",
        domain=domain, judul=judul, ringkasan=ringkasan,
        waktu_terbit=datetime(2026, 9, 8, jam_utc, 0),
        waktu_fetch=datetime(2026, 9, 9, 0, 0), feed=domain,
        kategori="politik", bobot=1.0,
    )


# --------------------------------------------------------------------------- #
# aturan dua syarat
# --------------------------------------------------------------------------- #

LOLOS = [
    "Kapal Virgo Transport 8 terbalik di Laut Jawa, bawa 243 penumpang",
    "Cerita Penumpang Selamat KM Virgo 8: Saya Bertahan, Naik ke Kapal Terbalik",
    "Lima Jurnalis Hilang Setelah Perahu Terbalik di Selat Sunda",
    "Hari Kedua, Tim SAR Perluas Pencarian Jurnalis dan Awak Kapal di Selat Sunda",
    "Pesawat latih jatuh, tiga awak dievakuasi",
]

DITAHAN = [
    # kecelakaan harian — inilah yang daftar-buang dampak.py memang tahan
    "Tabrakan maut di Tol Cipali, 1 orang tewas",
    "Kakak Beradik Tewas Saat Rumahnya Terbakar di Surabaya",
    # satu syarat saja tidak pernah cukup
    "Kapal pesiar mewah bersandar di Pelabuhan Benoa",       # peristiwa, tanpa skala
    "Jumlah penumpang bandara naik 8 persen pada Agustus",   # skala, tanpa peristiwa
    "Kereta cepat Whoosh tambah jadwal perjalanan",
    "Harga saham anjlok, ratusan investor ritel merugi",
]


@pytest.mark.parametrize("judul", LOLOS)
def uji_musibah_besar_dikenali(judul):
    assert musibah.periksa(judul)


@pytest.mark.parametrize("judul", DITAHAN)
def uji_bukan_musibah_besar_ditahan(judul):
    assert not musibah.periksa(judul)


def uji_pencocokan_per_kata_bukan_substring():
    """" sar " tidak boleh cocok dengan "besar", "bus" tidak dengan "bushel"."""
    assert not musibah.periksa("Pasar besar kebakaran, ratusan kios hangus")


# --------------------------------------------------------------------------- #
# penilai dampak
# --------------------------------------------------------------------------- #


def uji_musibah_besar_tidak_lagi_dinilai_nol():
    """Kasus nyata: ringkasan menyebut "kecelakaan", dan itu dulu cukup untuk
    membuangnya dari halaman sama sekali."""
    p = peristiwa(
        "Kapal Virgo Transport 8 terbalik di Laut Jawa, bawa 243 penumpang",
        ringkasan="Basarnas menyelidiki kecelakaan kapal yang membawa 243 penumpang.",
    )
    n = dampak.nilai([p])[p.url]
    assert n.dampak == 2 and n.alasan == "Kecelakaan transportasi"


def uji_kecelakaan_biasa_tetap_dibuang():
    p = peristiwa("Kecelakaan maut di Tol Cipali, satu orang tewas",
                  ringkasan="Tabrakan terjadi pada dini hari.")
    assert dampak.nilai([p])[p.url].dampak == 0


def uji_musibah_yang_ramai_naik_ke_dampak_tinggi():
    """Yang mengangkatnya ke blok utama tetap bukti yang sama seperti berita
    lain — liputan lintas redaksi, bukan karena ia musibah."""
    p = peristiwa("Kapal terbalik di Laut Jawa, 243 penumpang dievakuasi",
                  jumlah_media=dampak.BATAS_RAMAI)
    assert dampak.nilai([p])[p.url].dampak == 3


def uji_musibah_bukan_pintu_belakang_untuk_noise():
    """Pengecualiannya hanya untuk kata kecelakaan, bukan untuk seluruh
    daftar-buang."""
    p = peristiwa("Lomba perahu naga diikuti ratusan peserta",
                  ringkasan="Acara tahunan di tepi sungai.")
    assert dampak.nilai([p])[p.url].dampak == 0


# --------------------------------------------------------------------------- #
# saringan bagian politik
# --------------------------------------------------------------------------- #


def uji_relevan_meloloskan_musibah_tanpa_kata_ekonomi():
    p = peristiwa("KM Virgo terbalik di Laut Jawa, 243 penumpang dievakuasi",
                  ringkasan="Tim SAR gabungan mencari korban.")
    assert edisi.relevan(p), "tidak satu pun kata ekonomi di sini — itu intinya"


def uji_relevan_tetap_menahan_kriminal():
    p = peristiwa("Guru di Jombang dipolisikan usai diduga mencabuli siswinya",
                  ringkasan="Polisi memeriksa saksi.")
    assert not edisi.relevan(p)


def uji_musibah_muncul_di_halaman(con):
    """Ujung ke ujung: dari artikel tersimpan sampai terpilih di edisi."""
    penyimpanan.simpan_artikel(con, [
        artikel("Kapal Virgo Transport 8 terbalik di Laut Jawa, bawa 243 penumpang",
                "detik.test", 10,
                ringkasan="Basarnas mengevakuasi penumpang KM Virgo Transport 8."),
        artikel("Tabrakan maut di Tol Cipali, satu orang tewas", "b.test", 11,
                ringkasan="Kecelakaan terjadi dini hari."),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    judul = [p.judul for v in bagian.values() for p in v]
    assert any("Virgo" in j for j in judul), "musibah besar harus masuk halaman"
    assert not any("Cipali" in j for j in judul), "kecelakaan harian tetap ditahan"
