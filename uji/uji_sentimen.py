"""Uji `inti/sentimen.py` dan integrasinya ke `alur/edisi.py`.

Penilai ini deterministik dan tanpa I/O, sama seperti penilai dampak, jadi uji
memanggil fungsi yang persis dipakai di CI — tidak ada yang dipalsukan.

Judul di sini sengaja ditulis seperti judul asli, bukan kalimat contoh: yang
diuji adalah apakah aturannya bertahan pada cara redaksi Indonesia menulis, dan
itu tidak kelihatan dari "harga naik".
"""

from datetime import datetime

from alur import edisi
from inti import render, sentimen


def label(judul, ringkasan=None) -> str:
    return sentimen.nilai_teks(judul, ringkasan).label


# --------------------------------------------------------------------------- #
# arah + pokok: kata arah yang sama, tanda berbeda menurut pokoknya
# --------------------------------------------------------------------------- #


def uji_naik_pada_pokok_baik_positif():
    for judul in [
        "Laba bersih BBRI naik 12 persen pada kuartal III",
        "Ekspor CPO meningkat tajam ke India",
        "Cadangan devisa bertambah jadi 152 miliar dolar AS",
        "IHSG menguat ke level 8.100",
    ]:
        assert label(judul) == sentimen.POSITIF, judul


def uji_naik_pada_pokok_buruk_negatif():
    """Ini alasan modul ini tidak memakai kamus kata rata: "naik" di sini
    kabar buruk, dan kamus positif/negatif biasa akan salah pada keempatnya."""
    for judul in [
        "Inflasi naik jadi 4,2 persen pada September",
        "Utang pemerintah bertambah Rp120 triliun",
        "Angka pengangguran meningkat di Jawa Barat",
        "Kredit macet perbankan melonjak",
    ]:
        assert label(judul) == sentimen.NEGATIF, judul


def uji_turun_membalik_tandanya():
    assert label("Laba emiten tambang anjlok 30 persen") == sentimen.NEGATIF
    assert label("Inflasi turun ke 2,1 persen") == sentimen.POSITIF
    assert label("Angka pengangguran menyusut") == sentimen.POSITIF


def uji_pokok_buruk_menang_pada_jarak_sama():
    """"harga" ada di POKOK_BAIK_NAIK dan "inflasi" di POKOK_BURUK_NAIK; yang
    kedua harus menang, kalau tidak berita inflasi pangan jadi kabar baik."""
    assert label("Inflasi harga pangan naik") == sentimen.NEGATIF


def uji_superlatif_ikut_pokoknya():
    """"tertinggi" bukan frasa positif: yang menentukan tetap pokoknya."""
    assert label("Keyakinan konsumen tertinggi dalam tiga tahun") == sentimen.POSITIF
    assert label("Inflasi tertinggi sejak 2015") == sentimen.NEGATIF


def uji_kata_penghambat_membalik_arah():
    """"Faktor penghambat pertumbuhan ekonomi" adalah kabar buruk, bukan kabar
    pertumbuhan — persis seperti negasi, dan ditangani lewat jalan yang sama."""
    assert label("Bappenas ungkap faktor penghambat pertumbuhan ekonomi") == sentimen.NEGATIF
    assert label("Kendala perizinan hambat investasi asing") == sentimen.NEGATIF


def uji_sisi_kanan_tidak_menyeberang_klausa():
    """Pokok di kanan hanya dipungut kalau menempel. Tanpa batas ini, "Jika
    Bunga The Fed Naik, Ini Efeknya ke IHSG" jadi positif gara-gara "ihsg"."""
    assert label("Jika bunga The Fed akhir tahun naik, ini efeknya ke IHSG") == sentimen.NETRAL
    # Yang dekat tetap kena — ini pola yang membuat sisi kanan ada.
    assert label("BI menaikkan suku bunga acuan") == sentimen.NEGATIF


def uji_arah_tanpa_pokok_diabaikan():
    """Tanpa pokok yang dikenal, tidak ada arah yang bisa disimpulkan — dan
    menebaknya berarti setiap "meningkat" jadi kabar baik."""
    assert label("Jumlah penonton konser melonjak") == sentimen.NETRAL


# --------------------------------------------------------------------------- #
# frasa bertanda tetap
# --------------------------------------------------------------------------- #


def uji_frasa_negatif():
    for judul in [
        "Emiten properti itu resmi gagal bayar obligasi",
        "Pemerintah AS umumkan perang dagang jilid dua",
        "Pengadilan menyatakan perusahaan itu pailit",
    ]:
        assert label(judul) == sentimen.NEGATIF, judul


def uji_frasa_positif():
    for judul in [
        "Pemerintah beri insentif untuk industri tekstil",
        "Indonesia dan UE teken kesepakatan dagang",
        "BI umumkan pemangkasan suku bunga acuan",
    ]:
        assert label(judul) == sentimen.POSITIF, judul


def uji_frasa_dicocokkan_per_kata_utuh():
    """"denda" tidak boleh menyala di "dendam", dan "tarif impor" tidak boleh
    menyala kalau kedua katanya tidak berurutan."""
    assert label("Dendam lama antartetangga berujung damai") == sentimen.NETRAL


# --------------------------------------------------------------------------- #
# negasi
# --------------------------------------------------------------------------- #


def uji_negasi_membalik_tanda():
    assert label("Rupiah tidak melemah meski dolar menguat") != sentimen.NEGATIF
    assert label("BI batal menaikkan suku bunga acuan") == sentimen.POSITIF
    assert label("Perusahaan itu belum gagal bayar") == sentimen.POSITIF


# --------------------------------------------------------------------------- #
# bobot, netral, dan bentuk hasil
# --------------------------------------------------------------------------- #


def uji_judul_mengalahkan_ringkasan():
    """Judul berbobot dua, ringkasan satu: satu pemicu di judul menang atas
    satu pemicu berlawanan di ringkasan."""
    s = sentimen.nilai_teks(
        "Laba bersih perseroan naik 40 persen",
        "Meski begitu, beban bunga ikut meningkat tahun ini.",
    )
    assert s.label == sentimen.POSITIF


def uji_pemicu_seimbang_jadi_netral():
    s = sentimen.nilai_teks("Laba naik, utang bertambah")
    assert s.label == sentimen.NETRAL
    # Netral berarti "tidak berarah"; menyebut satu pemicunya akan menyesatkan.
    assert s.pemicu is None


def uji_berita_tanpa_arah_netral():
    for judul in [
        "Rapat Dewan Gubernur BI dijadwalkan pekan depan",
        "Menteri Keuangan hadiri rapat kerja dengan Komisi XI",
        "BPS akan merilis data perdagangan Senin",
    ]:
        assert label(judul) == sentimen.NETRAL, judul


def uji_pemicu_menjelaskan_label():
    s = sentimen.nilai_teks("Inflasi naik jadi 4,2 persen")
    assert s.label == sentimen.NEGATIF
    assert s.skor < 0
    assert s.pemicu and "inflasi" in s.pemicu


def uji_ringkasan_kosong_aman():
    assert sentimen.nilai_teks("Judul saja", None).label == sentimen.NETRAL
    assert sentimen.nilai_teks("", "").label == sentimen.NETRAL


# --------------------------------------------------------------------------- #
# integrasi: peristiwa, penilaian massal, halaman
# --------------------------------------------------------------------------- #


def peristiwa(judul, url="u1", ringkasan="isi", kategori="makro"):
    return edisi.Peristiwa(
        judul=judul, url=url, domain="a.test", ringkasan=ringkasan,
        waktu_terbit=datetime(2026, 9, 8, 10, 0), kategori=kategori,
        jumlah_media=1, bobot=1.0,
    )


def uji_nilai_massal_per_url():
    daftar = [
        peristiwa("Laba bersih naik 12 persen", url="a"),
        peristiwa("Inflasi naik jadi 4,2 persen", url="b"),
        peristiwa("Rapat dijadwalkan pekan depan", url="c"),
    ]
    hasil = sentimen.nilai(daftar)
    assert hasil["a"].label == sentimen.POSITIF
    assert hasil["b"].label == sentimen.NEGATIF
    assert hasil["c"].label == sentimen.NETRAL


def uji_sentimen_tidak_membuang_atau_mengurutkan():
    """Berita buruk bukan berita yang kurang penting: status arah tidak boleh
    ikut menentukan urutan atau kelolosan — itu urusan inti/dampak.py."""
    buruk = peristiwa("Inflasi naik jadi 4,2 persen", url="a")
    buruk.dampak, buruk.sentimen = 3, sentimen.NEGATIF
    baik = peristiwa("Laba bersih naik 12 persen", url="b")
    baik.dampak, baik.sentimen = 1, sentimen.POSITIF
    assert edisi._urutan(buruk) < edisi._urutan(baik)
    assert edisi._lolos(buruk)


def uji_halaman_menampilkan_lencana():
    p = peristiwa("Inflasi naik jadi 4,2 persen")
    p.dampak, p.sentimen, p.pemicu = 2, sentimen.NEGATIF, "inflasi naik"
    html = render.halaman(
        datetime(2026, 9, 9, 5, 0), {"makro": [p]},
        jumlah_sumber=1, total_dipertimbangkan=1,
    )
    assert 'class="arah negatif"' in html
    assert "inflasi naik" in html  # pemicunya ikut sebagai title


def uji_netral_tidak_diberi_lencana():
    """Sebagian besar berita netral; menandai semuanya sama dengan tidak
    menandai apa pun."""
    p = peristiwa("Rapat dijadwalkan pekan depan")
    p.dampak, p.sentimen = 1, sentimen.NETRAL
    html = render.halaman(
        datetime(2026, 9, 9, 5, 0), {"makro": [p]},
        jumlah_sumber=1, total_dipertimbangkan=1,
    )
    assert 'class="arah' not in html
