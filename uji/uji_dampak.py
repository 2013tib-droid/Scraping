"""Uji `inti/dampak.py` dan integrasinya ke `alur/edisi.py`.

Penilai ini deterministik dan tanpa I/O, jadi tidak ada yang perlu dipalsukan:
uji memanggil fungsi yang sama persis dengan yang jalan di CI.
"""

from datetime import date, datetime

import pytest

from alur import edisi
from inti import dampak, penyimpanan
from inti.penyimpanan import Artikel


@pytest.fixture
def con(tmp_path):
    c = penyimpanan.buka(tmp_path / "uji.duckdb")
    yield c
    c.close()


def peristiwa(judul, url="u1", *, ringkasan="isi", kategori="makro",
              jumlah_media=1, bobot=1.0, domain="a.test"):
    return edisi.Peristiwa(
        judul=judul, url=url, domain=domain, ringkasan=ringkasan,
        waktu_terbit=datetime(2026, 9, 8, 10, 0), kategori=kategori,
        jumlah_media=jumlah_media, bobot=bobot,
    )


def satu(p) -> dampak.Penilaian:
    return dampak.nilai([p])[p.url]


def artikel(judul, jam_utc, kategori="makro", domain="a.test", bobot=1.0,
            ringkasan="isi"):
    return Artikel(
        artikel_id=f"{domain}:{judul}"[:60], url=f"https://{domain}/{abs(hash(judul)) % 99999}",
        domain=domain, judul=judul, ringkasan=ringkasan,
        waktu_terbit=datetime(2026, 9, 8, jam_utc, 0),
        waktu_fetch=datetime(2026, 9, 9, 0, 0), feed=domain,
        kategori=kategori, bobot=bobot,
    )


def diliput(judul, jam_utc, n, **kw):
    """Peristiwa yang sama diliput `n` media — inilah yang menaikkan skor."""
    return [artikel(judul, jam_utc, domain=f"m{i}.test", **kw) for i in range(n)]


# --------------------------------------------------------------------------- #
# skala
# --------------------------------------------------------------------------- #


def uji_noise_dibuang():
    for judul in [
        "Bupati resmikan gerai Samsat baru di Cibeber",
        "Pembunuhan berencana di Banyuasin terungkap",
        "Timnas menang 2-0 atas Vietnam",
        "Tips hemat listrik ala ibu rumah tangga",
    ]:
        assert satu(peristiwa(judul)).dampak == 0, judul


def uji_frasa_besar_yang_ramai_jadi_utama():
    n = satu(peristiwa("BI Rate dipangkas 25 bps ke 5 persen", jumlah_media=6))
    assert n == dampak.Penilaian(3, "Kebijakan moneter")


def uji_siaran_pers_bank_sentral_lolos_sendirian():
    """Bobot 2.0 di feed.toml = BOBOT_PRIMER, jadi liputan tak perlu dihitung."""
    n = satu(peristiwa("FOMC statement on policy rate", jumlah_media=1, bobot=2.0))
    assert n == dampak.Penilaian(3, "Kebijakan moneter")


def uji_kolom_analis_bukan_keputusan():
    """FRASA_BESAR menyimpan "suku bunga acuan", bukan "suku bunga". Bedanya
    persis ini: kolom pengamat turun ke 2, keputusannya tetap 3."""
    assert satu(peristiwa("Ekonom: arah suku bunga masih akan datar")).dampak == 2
    assert satu(peristiwa("BI tahan suku bunga acuan di 5 persen")).dampak == 3


def uji_liputan_luas_cukup_tanpa_frasa():
    n = satu(peristiwa("Kabar yang diliput di mana-mana", jumlah_media=6))
    assert n == dampak.Penilaian(3, "Liputan luas")


def uji_frasa_sedang_jadi_dua():
    n = satu(peristiwa("Emiten X umumkan rights issue Rp2 triliun"))
    assert n == dampak.Penilaian(2, "Aksi korporasi")


def uji_sisanya_nice_to_know():
    n = satu(peristiwa("Perusahaan targetkan pabrik kedua tahun depan"))
    assert n == dampak.Penilaian(1, None)


def uji_frasa_besar_mengalahkan_saringan_buang():
    """"peresmian" itu noise, tapi tidak kalau BI Rate ikut diumumkan di sana."""
    assert satu(peristiwa("Peresmian gedung diwarnai pengumuman BI Rate")).dampak == 3
    # Tanpa frasa besarnya, judul serupa memang dibuang.
    assert satu(peristiwa("Peresmian gedung baru bank daerah")).dampak == 0


def uji_cocok_per_kata_bukan_substring():
    """" ecb " tidak boleh kena "necbot"; " ump " tidak boleh kena "kumpul"."""
    assert satu(peristiwa("Warga berkumpul di necbotan", ringkasan=None)).dampak == 1


def uji_ringkasan_kosong_tidak_meledak():
    assert satu(peristiwa("Judul saja", ringkasan=None)).dampak == 1


def uji_semua_peristiwa_dinilai():
    daftar = [peristiwa(f"Judul {i}", f"u{i}") for i in range(20)]
    hasil = dampak.nilai(daftar)
    assert len(hasil) == 20
    assert dampak.nilai(daftar) == hasil, "harus deterministik"


def uji_daftar_kosong():
    assert dampak.nilai([]) == {}


# --------------------------------------------------------------------------- #
# integrasi ke edisi
# --------------------------------------------------------------------------- #


def uji_edisi_memisahkan_utama_dan_membuang_noise(con):
    penyimpanan.simpan_artikel(con, [
        *diliput("BI Rate dipangkas 25 bps ke 5 persen", 10, 6),
        *diliput("Prabowo terbitkan inpres larang bakar lahan", 11, 9, kategori="politik"),
        artikel("Gerai Samsat baru diresmikan di Cibeber", 12),
        artikel("Perusahaan targetkan kredit tumbuh 8 persen", 13),
        artikel("Pemerkosaan dan pembunuhan di Banyuasin", 14, kategori="politik"),
    ])

    html, bagian, _ = edisi.bangun(con, date(2026, 9, 9))

    utama = [p.judul for p in bagian["utama"]]
    assert utama == [
        "Prabowo terbitkan inpres larang bakar lahan",  # 9 media -> liputan luas
        "BI Rate dipangkas 25 bps ke 5 persen",         # 6 media + frasa moneter
    ]
    # Yang sudah di blok utama tidak muncul lagi di bagiannya.
    assert not any("BI Rate" in p.judul for p in bagian["makro"])

    semua = [p.judul for v in bagian.values() for p in v]
    assert not any("Samsat" in j or "Banyuasin" in j for j in semua)
    assert any("kredit tumbuh" in j for j in semua)

    assert "Penting Pagi Ini" in html
    assert "Kebijakan moneter" in html


def uji_saringan_kata_politik_tetap_berlaku(con):
    """Daftar-tolak tidak bisa menebak apa yang *tidak* ekonomi. Berita umum
    yang tidak menyentuh kata apa pun harus tetap tersaring KATA_POLITIK."""
    penyimpanan.simpan_artikel(con, [
        artikel("Ratusan warga antre di posko pengungsian Ciamis", 10, kategori="politik"),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert not bagian["politik"]


def uji_obrolan_bank_sentral_tidak_menembus_blok_utama(con):
    """Nilai 3 tidak boleh jadi pintu belakang yang melewati DOMAIN_BANK_SENTRAL."""
    penyimpanan.simpan_artikel(con, [
        artikel("Fireside chat with the Chair", 10, kategori="global",
                domain="federalreserve.gov", bobot=2.0,
                ringkasan="Remarks at a Federal Reserve community event"),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert "utama" not in bagian
    assert not bagian["global"]
