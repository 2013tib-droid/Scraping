"""Uji `inti/pajak.py` dan bagian Perpajakan di `alur/edisi.py`. Tanpa jaringan.

Judul-judul di sini diambil dari feed sungguhan 8–9 Sep 2026, bukan dikarang:
yang diuji adalah kasus yang memang muncul, termasuk jebakan kata rancunya.
"""

from datetime import date, datetime

import pytest

from alur import edisi
from inti import pajak, penyimpanan
from inti.penyimpanan import Artikel


@pytest.fixture
def con(tmp_path):
    c = penyimpanan.buka(tmp_path / "uji.duckdb")
    yield c
    c.close()


def peristiwa(judul, ringkasan=None, kategori="makro"):
    return edisi.Peristiwa(
        judul=judul, url="u1", domain="a.test", ringkasan=ringkasan,
        waktu_terbit=datetime(2026, 9, 8, 10, 0), kategori=kategori,
        jumlah_media=1, bobot=1.0,
    )


def periksa(judul, ringkasan=None) -> pajak.Klasifikasi:
    return pajak.periksa(peristiwa(judul, ringkasan))


def artikel(judul, domain, jam_utc, kategori="makro", bobot=1.0):
    return Artikel(
        artikel_id=f"{domain}:{judul}"[:60],
        url=f"https://{domain}/{abs(hash(judul)) % 99999}",
        domain=domain, judul=judul, ringkasan=None,
        waktu_terbit=datetime(2026, 9, 8, jam_utc, 0),
        waktu_fetch=datetime(2026, 9, 9, 0, 0),
        feed=domain, kategori=kategori, bobot=bobot,
    )


# --------------------------------------------------------------------------- #
# klasifikasi
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("judul", [
    "Soal Penahanan Restitusi Pajak, Purbaya Soroti Pergeseran Instruksi",
    "SPP-TDLN Berlaku Esok! Himbara Pungut PPN Netflix, Canva hingga PUBG",
    "DJP Klaim Coretax Tambah 2 Juta Basis Pajak, Apa Dampaknya?",
    "Restitusi Seret, Purbaya Duga Ada Pergeseran Pelaksanaan Perintah",
    "Bea Cukai Tindak 10 Juta Batang Rokok Ilegal yang Rugikan Negara Rp 8 M",
    "ESDM Targetkan Bensin E20 Meluncur 2028, Cukai Bioetanol Dihapus",
])
def uji_berita_pajak_dikenali(judul):
    assert periksa(judul).pajak


@pytest.mark.parametrize("judul", [
    # Restitusi korban pidana, bukan pengembalian pajak.
    "Korban Lumpuh Usai Dibacok, Pelaku Dibui 4 Tahun & Wajib Bayar Restitusi Rp29,5 Juta",
    # PPN = Pelabuhan Perikanan Nusantara.
    "Asisten II Berkoordinasi dengan Satwas SDKP Ternate di PPN Bastiong",
    "Purbaya Pertimbangkan Tarik Dana Pemda yang Terus Mengendap di Bank",
    # Kata di dalam kata lain tidak boleh cocok.
    "Pengusaha kapal sptn bertemu Menhub",
])
def uji_bukan_berita_pajak(judul):
    assert not periksa(judul).pajak


@pytest.mark.parametrize("judul", [
    "3.954 Kendaraan ASN Sumbar Tunggak Pajak, Bapenda: Banyak yang Sudah Menjual",
    "Pemkab Blitar Kejar Tunggakan Pajak Reklame, Tiga Papan Disegel",
    "Rp 1,09 Miliar PBB-P2 Polman Masuk Kas Daerah",
    "Bukan dari Pajak Kendaraan, PAD Batam Tembus Rp2,58 Triliun",
])
def uji_pajak_daerah_ditandai(judul):
    k = periksa(judul)
    assert k.pajak and k.daerah and k.topik == "Pajak daerah"


@pytest.mark.parametrize("judul, ringkasan", [
    ("Bappenas: Indonesia Harus Tinggalkan Model Pertumbuhan Berbasis Upah Murah",
     "Menteri PPN Rachmat Pambudy mengatakan Indonesia perlu meninggalkan ..."),
    ("94% SPBU Pertamina Sudah Salurkan B50, Sisanya Masih Transisi",
     "PT Pertamina Patra Niaga (PPN) mengungkapkan 94% SPBU telah menjual B50."),
    ("Setahun Jadi Menkeu, Purbaya Klaim Ekonomi Pulih, tapi Utang Menumpuk",
     "Kenaikan utang dan lemahnya penerimaan pajak masih jadi pekerjaan rumah."),
])
def uji_pajak_di_ringkasan_saja_tidak_cukup(judul, ringkasan):
    """Kasus nyata 9 Sep: ketiganya masuk Perpajakan hanya karena ringkasannya."""
    assert not periksa(judul, ringkasan).pajak


def uji_ringkasan_tetap_membatalkan_kata_rancu():
    k = periksa("Pelaku wajib bayar restitusi Rp29 juta",
                "Majelis hakim memvonis terdakwa dan menetapkan restitusi bagi korban.")
    assert not k.pajak


def uji_situs_asing_tidak_masuk():
    p = peristiwa("Menurunkan ambang batas bebas pajak untuk barang bernilai rendah")
    p.domain = "vietnam.vn"
    assert not pajak.periksa(p).pajak


def uji_situs_pemda_ditandai_daerah():
    p = peristiwa("Bayar Pajak Tanpa KTP Pemilik Pertama")
    p.domain = "bantenprov.go.id"
    assert pajak.periksa(p).daerah


def uji_pbb_polos_bukan_pajak_daerah():
    """PBB juga Perserikatan Bangsa-Bangsa — konvensi pajaknya berita pusat."""
    assert not periksa("PBB Rampungkan Draf Konvensi Pajak Internasional").daerah


@pytest.mark.parametrize("judul", [
    "Sudah Lulus Brevet Pajak AB, Saatnya Lanjut Brevet C untuk CV Lebih Kuat",
    "Segera Daftar! Early Bird Seminar SPT PPh Badan Berakhir Hari Ini",
    "Pajak Bertutur 2026, KPP Pratama Wonosari Kenalkan Peran Pajak kepada Pelajar",
    "Artikel dan berita dengan kata kunci Fisioterapis",
    "Cara Mengajukan Permohonan Pengurangan Angsuran PPh Pasal 25 melalui Coretax",
    "Pemenang Kompetisi Konten Manfaat Pajak",
])
def uji_promosi_dan_seremonial_dibuang(judul):
    assert periksa(judul).buang


@pytest.mark.parametrize("judul, topik", [
    ("KPK Panggil 6 Saksi Usut Gratifikasi di Ditjen Pajak", "Penegakan hukum"),
    ("Dikeluhkan Pengusaha, Purbaya Janji Selesaikan Hambatan Pencairan Restitusi Pajak",
     "Restitusi"),
    ("Pemberitahuan Waktu Henti (Downtime)", "Coretax & layanan"),
    ("DJP Sudah Tunjuk 230 Platform Digital Global sebagai Pemungut Pajak PMSE",
     "Pajak digital & internasional"),
    ("Kewenangan Menteri Keuangan Atur Kuasa Wajib Pajak Digugat ke MK",
     "Profesi & sengketa"),
    ("Emiten Sinar Mas Dapat Tax Holiday", "Tarif & insentif"),
    ("IKPI Sebut PMK 55/2026 Bangun Kepercayaan Profesi Konsultan Pajak",
     "Profesi & sengketa"),
])
def uji_subtopik(judul, topik):
    assert periksa(judul).topik == topik


def uji_penegakan_hukum_mengalahkan_restitusi():
    """Urutan TOPIK disengaja: yang paling spesifik menang."""
    assert periksa("KPK sita aset eks pejabat pajak terkait restitusi").topik == "Penegakan hukum"


# --------------------------------------------------------------------------- #
# edisi
# --------------------------------------------------------------------------- #


def uji_berita_pajak_pindah_dari_makro(con):
    penyimpanan.simpan_artikel(con, [
        artikel("Purbaya Janji Usut Hambatan Restitusi Pajak", "a.test", 10),
        artikel("Penjualan mobil domestik melambat kuartal lalu", "b.test", 11),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert [p.domain for p in bagian["pajak"]] == ["a.test"]
    assert [p.domain for p in bagian["makro"]] == ["b.test"]
    assert bagian["pajak"][0].alasan == "Restitusi"


def uji_pajak_global_dan_pasar_tidak_dipindah(con):
    """Bagian ini perpajakan Indonesia, dan analisis saham tetap milik Pasar."""
    penyimpanan.simpan_artikel(con, [
        artikel("Chancellor's attempts to boost vibes may limit tax rises",
                "bbc.co.uk", 10, kategori="global"),
        artikel("Menakar Prospek Saham FILM di Tengah Wacana Insentif Pajak Film",
                "kontan.test", 11, kategori="pasar"),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert not bagian["pajak"]
    assert [p.domain for p in bagian["global"]] == ["bbc.co.uk"]
    assert [p.domain for p in bagian["pasar"]] == ["kontan.test"]


def uji_feed_pajak_masuk_walau_judulnya_tidak_menyebut_pajak(con):
    """Pengumuman DJP sering tanpa kata pajak di judulnya."""
    penyimpanan.simpan_artikel(con, [
        artikel("Pemberitahuan Waktu Henti (Downtime)", "pajak.go.id", 10,
                kategori="pajak", bobot=2.0),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert [p.domain for p in bagian["pajak"]] == ["pajak.go.id"]


def uji_pajak_daerah_di_bawah_pajak_pusat(con):
    penyimpanan.simpan_artikel(con, [
        # Terbaru — tanpa aturan urutan, dia yang di atas.
        artikel("Pemutihan Pajak Kendaraan, Bupati Merangin Minta Warga Manfaatkan",
                "daerah.test", 20),
        artikel("DJP Kejar Tunggakan Pajak Global, Penagihan Lintas Negara Dimulai 2027",
                "pusat.test", 9),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert [p.domain for p in bagian["pajak"]] == ["pusat.test", "daerah.test"]


def uji_pajak_pusat_tanpa_kata_pajak_tidak_kalah_dari_pemda(con):
    penyimpanan.simpan_artikel(con, [
        artikel("SPP-TDLN Berlaku 10 September, DJP Incar Penerimaan Dua Kali Lipat",
                "pusat.test", 9),
        artikel("Optimalisasi Pajak Jadi Kunci, Sekda Bengkalis Hadiri Rakor",
                "daerah.test", 20),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert [p.domain for p in bagian["pajak"]] == ["pusat.test", "daerah.test"]
    assert bagian["pajak"][0].dampak == 2


def uji_promosi_pajak_tidak_tampil(con):
    penyimpanan.simpan_artikel(con, [
        artikel("Sudah Lulus Brevet Pajak AB, Saatnya Lanjut Brevet C", "iklan.test", 10),
        artikel("SPP-TDLN Siap Berlaku, DJP Matangkan Tahapan Akhir", "berita.test", 11),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    semua = [p.domain for v in bagian.values() for p in v]
    assert semua == ["berita.test"]


def uji_halaman_memuat_bagian_perpajakan(con):
    penyimpanan.simpan_artikel(con, [
        artikel("Purbaya Janji Usut Hambatan Restitusi Pajak", "a.test", 10),
    ])
    html, _, _ = edisi.bangun(con, date(2026, 9, 9))
    assert 'id="pajak"' in html and "Perpajakan" in html
    assert 'href="#pajak"' in html
