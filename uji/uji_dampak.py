"""Uji `inti/dampak.py` dan integrasinya ke `alur/edisi.py`. Tanpa jaringan:
pemanggil Claude diganti fungsi palsu lewat parameter `panggil`."""

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


def peristiwa(judul, url, kategori="makro", jumlah_media=1):
    return edisi.Peristiwa(
        judul=judul, url=url, domain="a.test", ringkasan="isi",
        waktu_terbit=datetime(2026, 9, 8, 10, 0), kategori=kategori,
        jumlah_media=jumlah_media, bobot=1.0,
    )


def artikel(judul, jam_utc, kategori="makro"):
    return Artikel(
        artikel_id=judul[:60], url=f"https://a.test/{abs(hash(judul)) % 99999}",
        domain="a.test", judul=judul, ringkasan="isi",
        waktu_terbit=datetime(2026, 9, 8, jam_utc, 0),
        waktu_fetch=datetime(2026, 9, 9, 0, 0), feed="a.test",
        kategori=kategori, bobot=1.0,
    )


# --------------------------------------------------------------------------- #
# dampak.nilai
# --------------------------------------------------------------------------- #


def uji_tanpa_kunci_tidak_menilai(con, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert dampak.nilai(con, [peristiwa("BI Rate turun", "u1")]) == {}


def uji_masukan_bernomor_dan_ringkas():
    p = peristiwa("Judul", "u1", kategori="pasar", jumlah_media=3)
    p.ringkasan = "x" * 500
    teks = dampak._susun_masukan([p])
    assert teks.startswith("1 | pasar | 3 media | a.test | Judul — ")
    assert len(teks) < 200, "ringkasan harus dipotong"


def uji_jawaban_ditafsirkan_dan_dicache(con):
    panggilan = []

    def palsu(teks):
        panggilan.append(teks)
        return {"nilai": [
            {"i": 1, "d": 3, "k": "Arah suku bunga menentukan valuasi seluruh pasar."},
            {"i": 2, "d": 0, "k": ""},
            {"i": 3, "d": 1, "k": "alasan ini harus dibuang karena d<2"},
            {"i": 99, "d": 3, "k": "nomor tak dikenal"},
        ]}

    daftar = [
        peristiwa("BI Rate turun 25 bps", "u1"),
        peristiwa("Gerai Samsat baru di Cibeber", "u2"),
        peristiwa("Ekonom proyeksikan ekonomi resilien", "u3"),
    ]
    hasil = dampak.nilai(con, daftar, panggil=palsu)
    assert hasil["u1"] == dampak.Penilaian(3, "Arah suku bunga menentukan valuasi seluruh pasar.")
    assert hasil["u2"] == dampak.Penilaian(0, None)
    assert hasil["u3"] == dampak.Penilaian(1, None)
    assert "u99" not in hasil and len(panggilan) == 1

    # Kedua kali: semua sudah di cache, pemanggil tidak disentuh.
    assert dampak.nilai(con, daftar, panggil=palsu) == hasil
    assert len(panggilan) == 1


def uji_pemanggil_gagal_tidak_menjatuhkan(con, capsys):
    def rusak(teks):
        raise RuntimeError("jaringan putus")

    assert dampak.nilai(con, [peristiwa("Apa saja", "u1")], panggil=rusak) == {}
    assert "penilaian gagal" in capsys.readouterr().err


def uji_dipecah_per_kelompok(con, monkeypatch):
    monkeypatch.setattr(dampak, "UKURAN_KELOMPOK", 2)
    ukuran = []

    def palsu(teks):
        n = len(teks.splitlines())
        ukuran.append(n)
        return {"nilai": [{"i": i, "d": 1, "k": ""} for i in range(1, n + 1)]}

    daftar = [peristiwa(f"Judul {i}", f"u{i}") for i in range(5)]
    assert len(dampak.nilai(con, daftar, panggil=palsu)) == 5
    assert ukuran == [2, 2, 1]


# --------------------------------------------------------------------------- #
# integrasi ke edisi
# --------------------------------------------------------------------------- #


def uji_edisi_memisahkan_utama_dan_membuang_noise(con, monkeypatch, tmp_path):
    penyimpanan.simpan_artikel(con, [
        artikel("BI Rate dipangkas 25 bps ke 5 persen", 10),
        artikel("Gerai Samsat baru diresmikan di Cibeber", 11),
        artikel("Emiten X targetkan kredit tumbuh 8 persen", 12),
        artikel("Pemerkosaan dan pembunuhan di Banyuasin", 13, kategori="politik"),
        artikel("Prabowo terbitkan Inpres larang bakar lahan", 14, kategori="politik"),
    ])

    def palsu_nilai(con_, peristiwa, **_):
        skor = {
            "BI Rate": (3, "Suku bunga acuan menggeser valuasi bank dan obligasi."),
            "Samsat": (0, None),
            "Emiten X": (1, None),
            "Banyuasin": (0, None),
            "Inpres": (3, "Larangan bakar lahan menekan biaya sawit dan HTI."),
        }
        hasil = {}
        for p in peristiwa:
            for kunci, (d, k) in skor.items():
                if kunci in p.judul:
                    hasil[p.url] = dampak.Penilaian(d, k)
        return hasil

    monkeypatch.setattr(edisi.dampak, "nilai", palsu_nilai)
    html, bagian, _ = edisi.bangun(con, date(2026, 9, 9))

    utama = [p.judul for p in bagian["utama"]]
    assert utama == [
        "Prabowo terbitkan Inpres larang bakar lahan",  # lebih baru, skor sama
        "BI Rate dipangkas 25 bps ke 5 persen",
    ]
    # Yang sudah di blok utama tidak muncul lagi di bagiannya.
    assert not any("BI Rate" in p.judul for p in bagian["makro"])
    assert not bagian["politik"]
    # Noise dibuang; nice-to-know tetap ada di bagiannya.
    semua = [p.judul for v in bagian.values() for p in v]
    assert not any("Samsat" in j or "Banyuasin" in j for j in semua)
    assert any("Emiten X" in j for j in semua)
    # Politik yang bernilai tinggi lolos tanpa saringan kata kunci.
    assert "Penting Pagi Ini" in html
    assert "Larangan bakar lahan menekan biaya sawit" in html


def uji_tanpa_penilaian_perilaku_lama(con, monkeypatch):
    penyimpanan.simpan_artikel(con, [artikel("Gerai Samsat baru di Cibeber", 10)])
    monkeypatch.setattr(edisi.dampak, "nilai", lambda con_, p, **_: {})
    html, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert "utama" not in bagian
    assert [p.judul for p in bagian["makro"]] == ["Gerai Samsat baru di Cibeber"]
    assert "Penting Pagi Ini" not in html
