"""Uji `inti/dedup.py`, `inti/render.py`, dan `alur/edisi.py`. Tanpa jaringan."""

from datetime import date, datetime, timedelta

import pytest

from alur import edisi
from inti import dedup, penyimpanan
from inti.penyimpanan import Artikel


@pytest.fixture
def con(tmp_path):
    c = penyimpanan.buka(tmp_path / "uji.duckdb")
    yield c
    c.close()


def artikel(judul, domain, jam_utc, kategori="makro", ringkasan="isi", bobot=1.0):
    return Artikel(
        artikel_id=f"{domain}-{judul}"[:60],
        url=f"https://{domain}/x/{abs(hash(judul)) % 9999}",
        domain=domain,
        judul=judul,
        ringkasan=ringkasan,
        waktu_terbit=datetime(2026, 9, 8, jam_utc, 0),
        waktu_fetch=datetime(2026, 9, 9, 0, 0),
        feed=domain,
        kategori=kategori,
        bobot=bobot,
    )


# --------------------------------------------------------------------------- #
# dedup
# --------------------------------------------------------------------------- #


def uji_judul_ditulis_ulang_tetap_satu_peristiwa():
    """Kasus nyata: media menulis ulang headline, jadi pencocokan string gagal."""
    judul = [
        "Survei BI: Keyakinan Konsumen Meningkat pada Agustus 2026",
        "Keyakinan Konsumen RI Agustus Meningkat, Tertinggi dalam Tiga Bulan",
        "Keyakinan Konsumen RI Naik, Tertinggi dalam 3 Bulan",
        "Harga emas Antam hari ini naik Rp10 ribu",
    ]
    kelompok = dedup.kelompokkan(judul)
    terbesar = max(kelompok, key=len)
    assert len(terbesar) == 3 and 3 not in terbesar


def uji_berita_berbeda_tidak_digabung():
    judul = [
        "IHSG ditutup menguat 1 persen ke level 6.686",
        "Rupiah melemah ke Rp17.700 per dolar AS",
        "Harga minyak dunia turun tipis",
    ]
    assert all(len(k) == 1 for k in dedup.kelompokkan(judul))


def uji_kelompok_transitif():
    """A~B dan B~C harus menyatukan ketiganya, walau A dan C sendiri tak cukup mirip."""
    judul = [
        "Pemerintah naikkan cukai rokok tahun depan",
        "Pemerintah naikkan cukai rokok mulai Januari",
        "Cukai rokok naik mulai Januari tahun depan",
    ]
    assert len(max(dedup.kelompokkan(judul), key=len)) == 3


def uji_judul_terlalu_pendek_tidak_digabung():
    """Dua judul tiga kata bisa mirip 0,67 hanya karena kebetulan."""
    assert all(len(k) == 1 for k in dedup.kelompokkan(["Rupiah menguat", "Rupiah melemah"]))


def uji_masukan_kosong():
    assert dedup.kelompokkan([]) == []


# --------------------------------------------------------------------------- #
# jendela waktu
# --------------------------------------------------------------------------- #


def uji_jendela_edisi_dalam_utc():
    mulai, akhir = edisi.jendela(date(2026, 9, 9))
    # 05:00 WIB 9 Sep = 22:00 UTC 8 Sep; mulai 24 jam sebelumnya.
    assert akhir == datetime(2026, 9, 8, 22, 0)
    assert mulai == datetime(2026, 9, 7, 22, 0)
    assert akhir - mulai == timedelta(days=1)
    assert mulai.tzinfo is None and akhir.tzinfo is None


def uji_jendela_tidak_bergantung_pada_sekarang():
    """Edisi lama harus bisa dibangun ulang persis (§16)."""
    assert edisi.jendela(date(2020, 1, 1)) == (
        datetime(2019, 12, 30, 22, 0),
        datetime(2019, 12, 31, 22, 0),
    )


# --------------------------------------------------------------------------- #
# penyusunan edisi
# --------------------------------------------------------------------------- #


def uji_hanya_artikel_dalam_jendela(con):
    penyimpanan.simpan_artikel(con, [
        artikel("Berita di dalam jendela soal APBN", "a.test", 23),   # 8 Sep 23:00 -> luar
        artikel("Berita lain soal anggaran negara", "b.test", 12),    # 8 Sep 12:00 -> dalam
    ])
    _, bagian, total = edisi.bangun(con, date(2026, 9, 9))
    assert total == 1
    assert bagian["makro"][0].domain == "b.test"


def uji_diurutkan_menurut_jumlah_media(con):
    penyimpanan.simpan_artikel(con, [
        artikel("Sendirian tapi terbaru soal pajak", "solo.test", 20),
        artikel("Bank Indonesia tahan suku bunga acuan", "a.test", 10),
        artikel("BI tahan suku bunga acuan bulan ini", "b.test", 10),
        artikel("Bank Indonesia menahan suku bunga acuannya", "c.test", 10),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    teratas = bagian["makro"][0]
    assert teratas.jumlah_media == 3, "peristiwa liputan terbanyak harus di atas"
    assert len(teratas.juga) == 2


def uji_batas_per_bagian_ditegakkan(con):
    # Judulnya harus benar-benar berbeda. Kalau hanya berbeda angka, dedup akan
    # menggabungkannya jadi satu peristiwa — dan itu perilaku yang benar.
    topik = [
        "Cadangan devisa naik pada akhir Agustus",
        "Harga batu bara acuan turun bulan ini",
        "Penjualan mobil domestik melambat kuartal lalu",
        "Produksi padi nasional diperkirakan meningkat",
        "Investasi asing langsung tumbuh dua digit",
        "Defisit transaksi berjalan menyempit",
        "Belanja infrastruktur diserap 60 persen",
        "Tarif listrik industri tidak berubah",
        "Ekspor nikel olahan mencetak rekor",
        "Kredit perbankan tumbuh melambat",
        "Utang luar negeri swasta menurun",
        "Setoran dividen BUMN melampaui target",
        "Impor barang modal meningkat tajam",
        "Okupansi hotel membaik jelang libur",
        "Harga gabah petani terkoreksi",
    ]
    penyimpanan.simpan_artikel(con, [
        artikel(t, f"d{i}.test", 10) for i, t in enumerate(topik)
    ])
    _, bagian, total = edisi.bangun(con, date(2026, 9, 9))
    assert total == len(topik) > edisi.BATAS["makro"]
    assert len(bagian["makro"]) == edisi.BATAS["makro"]


def uji_politik_disaring_kata_kunci(con):
    penyimpanan.simpan_artikel(con, [
        artikel("Guru di Jombang dipolisikan usai diduga mencabuli siswinya",
                "a.test", 10, kategori="politik"),
        artikel("DPR setujui RUU Perampasan Aset dibahas tahun ini",
                "b.test", 11, kategori="politik"),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    judul = [p.judul for p in bagian["politik"]]
    assert any("DPR" in j for j in judul)
    assert not any("Jombang" in j for j in judul), "berita kriminal tidak relevan (§16)"


def uji_wakil_memilih_yang_punya_ringkasan(con):
    penyimpanan.simpan_artikel(con, [
        artikel("Pemerintah pangkas subsidi energi tahun depan", "kecil.test", 10,
                ringkasan=None),
        artikel("Pemerintah pangkas subsidi energi mulai tahun depan", "besar.test", 10,
                ringkasan="Alokasi subsidi energi dipangkas dalam RAPBN."),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert bagian["makro"][0].domain == "besar.test"


def uji_bobot_mengangkat_sumber_jarang(con):
    penyimpanan.simpan_artikel(con, [
        artikel("Federal Reserve issues FOMC statement", "federalreserve.gov", 10,
                kategori="global", bobot=2.0),
        artikel("Some company reports quarterly earnings", "x.test", 11,
                kategori="global"),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert bagian["global"][0].domain == "federalreserve.gov"


def uji_pidato_bank_sentral_disaring(con):
    """Kasus nyata: 'Frank Elderson: Fireside chat' memuncaki bagian Global."""
    penyimpanan.simpan_artikel(con, [
        artikel("Frank Elderson: Fireside chat", "ecb.europa.eu", 10,
                kategori="global", bobot=2.0, ringkasan=None),
        artikel("Monetary policy decisions", "ecb.europa.eu", 11,
                kategori="global", bobot=2.0, ringkasan=None),
        artikel("Oil prices slip on demand worries", "x.test", 12, kategori="global"),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    judul = [p.judul for p in bagian["global"]]
    assert "Monetary policy decisions" in judul
    assert "Frank Elderson: Fireside chat" not in judul


def uji_kata_sosial_penggerak_pasar_lolos(con):
    penyimpanan.simpan_artikel(con, [
        artikel("Karhutla meluas di Riau, jarak pandang bandara turun",
                "a.test", 10, kategori="politik"),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert len(bagian["politik"]) == 1


# --------------------------------------------------------------------------- #
# halaman
# --------------------------------------------------------------------------- #


def uji_halaman_aman_dan_lengkap(con, tmp_path):
    penyimpanan.simpan_artikel(con, [
        artikel('Judul dengan <script>alert("x")</script> & tanda', "a.test", 10),
    ])
    html, _, _ = edisi.bangun(con, date(2026, 9, 9))

    assert "<script>alert" not in html, "judul harus di-escape"
    assert "&lt;script&gt;" in html
    assert "Ringkas Pagi" in html and "9 September 2026" in html
    assert 'lang="id"' in html and "prefers-color-scheme" in html

    berkas = edisi.tulis(html, date(2026, 9, 9), tmp_path)
    assert berkas.exists()
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == html


def uji_waktu_ditampilkan_dalam_wib(con):
    penyimpanan.simpan_artikel(con, [artikel("Rilis data inflasi bulan lalu", "a.test", 10)])
    html, _, _ = edisi.bangun(con, date(2026, 9, 9))
    assert "17:00 WIB" in html  # 10:00 UTC + 7


def uji_edisi_kosong_tidak_meledak(con):
    html, bagian, total = edisi.bangun(con, date(2026, 9, 9))
    assert total == 0 and not any(bagian.values())
    assert "Tidak ada berita" in html
