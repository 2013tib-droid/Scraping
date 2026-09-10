"""
dampak.py — nilai seberapa penting tiap peristiwa. Deterministik, tanpa jaringan.

Kenapa modul ini ada (ARSITEKTUR.md §16): "berapa banyak media meliput" hanya
membedakan puncaknya. Dari ~550 peristiwa sehari, 95% diliput satu media, jadi
di ekor panjang urutannya efektif "yang paling baru" — dan halaman pagi terisi
berita yang cuma enak diketahui, bukan yang mengubah keputusan.

Penilaian di sini memakai empat sinyal yang **sudah ada di basis data**. Tidak
memanggil layanan apa pun: tidak butuh kunci, tidak punya kuota, tidak berbiaya,
dan tidak bisa gagal karena jaringan.

1. **Frasa** di judul dan ringkasan — keputusan moneter, rilis data makro,
   APBN/pajak, nilai tukar, komoditas utama. Daftarnya di bawah, bisa dibaca
   dan diubah dalam satu menit; prinsip yang sama dengan KATA_POLITIK di
   alur/edisi.py, yaitu saringan kasar yang alasannya kelihatan.
2. **Luas liputan** — berapa redaksi meliput hal yang sama. Kalau delapan
   memilihnya dari ~1.000 artikel semalam, itu bukti empiris, bukan tebakan.
3. **Bobot sumber** — siaran pers bank sentral hampir tidak pernah diliput
   ulang media Indonesia, jadi menghitung liputan akan selalu salah untuknya.
4. **Saringan noise** — seremonial, promosi, olahraga, selebriti, kriminal
   biasa. Ini yang paling banyak membersihkan halaman.

Skala:

    3  harus tahu hari ini — menggerakkan pasar atau ekonomi luas
    2  penting — mengubah pandangan tentang sektor/emiten, arah kebijakan
    1  nice to know — menarik, tidak mengubah keputusan
    0  abaikan — seremonial, promosi, tips, selebriti, kriminal biasa

Halaman memisahkan yang 3 ke blok teratas, menampilkan alasan untuk 2 dan 3, dan
membuang 0 sama sekali.

**`alasan` di sini adalah label aturan yang menyala, bukan analisis.** "Kebijakan
moneter" berarti frasa moneter yang cocok, titik. Kalimat "kenapa penting bagi
investor" tidak bisa dihitung dari aturan, jadi tidak dikarang — menaruh tebakan
di slot itu lebih buruk daripada mengosongkannya.
"""

from __future__ import annotations

from dataclasses import dataclass

# Ambang liputan dikalibrasi ke sebaran yang **sebenarnya**, bukan ke intuisi.
#
# **Dihitung ulang 10 Sep 2026**, setelah dedup diberi jalan kedua (kata langka
# bersama) dan pemenggalan imbuhan. Baris ini memang menyuruh begitu, dan
# angkanya memang bergeser: pada 10 Sep, 1.121 artikel yang dulu jadi 962
# peristiwa kini jadi 818, dan liputan tertinggi naik dari 5 ke 11 media.
#
#   sebaran jumlah_media (818 peristiwa): 732 diliput 1, 52 diliput 2,
#   17 diliput 3, lalu ekor tipis sampai 11.
#   persentil: 2 media = p95,8 · 5 media = p99,1
#
# `jumlah_media` masih **kurang menghitung** — dedup mencocokkan kata judul,
# sementara dua redaksi bisa menulis peristiwa yang sama tanpa satu pun kata
# pembeda yang sama. Jadi liputan tetap bukan gerbang; ia bukti hanya kalau
# angkanya sudah ekstrem. Yang berubah cuma di mana "ekstrem" itu berada.
BATAS_RAMAI = 5    # ~99,8 persentil: seramai ini sudah bukti sendiri
BATAS_SEDANG = 2   # ~95 persentil: cukup untuk "penting"

# Sumber primer (feed.toml memberi bank sentral bobot 2.0). Siaran pers BI dan
# Fed hampir tidak pernah diliput ulang media Indonesia, jadi menghitung liputan
# akan selalu salah untuknya.
BOBOT_PRIMER = 2.0

# Frasa penanda dampak 3, dikelompokkan supaya labelnya bisa menyebut sebabnya.
#
# Sengaja **sempit**, dan setiap pelonggaran harus diukur ulang ke data asli.
# Yang pernah dicoba dan dibuang, semuanya karena membanjiri blok utama:
#
#   "ihsg", "rupiah", "nilai tukar"  -> 28 dari 51 kandidat sehari. Laporan
#       harian indeks dan kurs ditulis belasan redaksi dengan judul berbeda,
#       jadi dedup gagal menggabungkannya dan masing-masing masuk sendiri.
#       Ini wallpaper berita keuangan, bukan "harus tahu hari ini".
#   "pertumbuhan ekonomi", "daya beli" -> muncul di hampir setiap kutipan
#       pengamat dan pidato pejabat.
#   "bank indonesia", "suku bunga" (tanpa "acuan") -> kena sosialisasi kantor
#       perwakilan daerah dan kolom analis.
#
# Semuanya turun ke FRASA_SEDANG: tetap tampil di bagiannya, tidak menyandera
# blok teratas.
FRASA_BESAR: dict[str, tuple[str, ...]] = {
    "Kebijakan moneter": (
        "bi rate", "bi7drr", "suku bunga acuan", "rapat dewan gubernur",
        "bank sentral", "the fed", "fomc", "federal reserve",
        "pelonggaran moneter", "pengetatan moneter",
    ),
    "Data makro": (
        "inflasi", "deflasi", "produk domestik bruto", "neraca dagang",
        "neraca perdagangan", "cadangan devisa", "transaksi berjalan",
        "pmi manufaktur", "angka pengangguran",
    ),
    "Fiskal & pajak": (
        "apbn", "defisit anggaran", "utang negara", "tarif ppn", "ppn naik",
        "pph badan", "kenaikan cukai", "bea masuk", "tarif impor",
        "subsidi bbm", "subsidi energi",
    ),
    "Komoditas & energi": (
        "larangan ekspor", "opec", "harga acuan batu bara",
    ),
    "Risiko global": (
        "perang dagang", "resesi", "krisis keuangan", "devaluasi",
        "sanksi ekonomi", "gagal bayar utang",
    ),
}

# Frasa penanda dampak 2: menggeser pandangan atas satu sektor atau emiten.
FRASA_SEDANG: dict[str, tuple[str, ...]] = {
    "Aksi korporasi": (
        "emiten", "ipo", "rights issue", "right issue", "dividen",
        "laba bersih", "rugi bersih", "akuisisi", "merger", "buyback",
        "obligasi korporasi", "gagal bayar", "pailit", "pkpu", "delisting",
    ),
    "Pasar & nilai tukar": (
        "ihsg", "rupiah", "nilai tukar", "kurs", "yield sbn",
        "surat berharga negara", "obligasi negara", "modal asing",
        "suku bunga", "bank indonesia", "harga minyak", "harga emas",
        "harga batu bara", "harga nikel", "harga cpo",
    ),
    "Sektor & industri": (
        "phk", "pemutusan hubungan kerja", "kredit macet", "npl",
        "likuiditas", "investasi asing", "penanaman modal", "ekspor",
        "impor", "manufaktur", "properti", "otomotif", "perbankan",
        "kapasitas produksi", "upah minimum", "ump", "hilirisasi",
        "pertumbuhan ekonomi", "daya beli", "pdb",
    ),
    "Regulasi": (
        "ruu", "peraturan menteri", "perpres", "perppu", "inpres",
        "regulasi", "moratorium", "relaksasi", "kuota impor",
        "pajak", "cukai", "subsidi", "izin usaha", "insentif pajak",
    ),
}

# Frasa yang membuang peristiwa dari halaman. Ini bagian yang paling banyak
# bekerja: bagian politik ditarik dari feed berita umum, jadi isinya bercampur
# kriminal, selebriti, dan kecelakaan.
#
# Kena di sini tidak selalu berarti dibuang — lihat `_dibuang`: frasa besar
# menang, supaya "Peresmian diwarnai pengumuman BI Rate" tidak hilang gara-gara
# "peresmian".
FRASA_BUANG: tuple[str, ...] = (
    # seremonial & promosi
    "resmikan", "diresmikan", "peresmian", "groundbreaking", "seremoni",
    "hut ke", "ulang tahun", "santunan", "bakti sosial",
    "promo", "diskon", "giveaway", "undian berhadiah",
    # olahraga & hiburan
    "lomba", "juara", "pertandingan", "liga", "piala", "timnas", "klasemen",
    "prediksi skor", "artis", "selebriti", "sinetron", "drakor", "konser",
    # layanan & evergreen
    "tips", "cara mudah", "cara cek", "resep", "wisata", "kuliner",
    "zodiak", "horoskop", "ramalan", "link download", "jadwal sholat",
    # kriminal & kecelakaan biasa
    "begal", "pencurian", "pembunuhan", "pemerkosaan", "pelecehan",
    "narkoba", "sabu", "kecelakaan", "tabrakan", "laka lantas",
    "curanmor", "penganiayaan", "tawuran",
)


@dataclass(slots=True, frozen=True)
class Penilaian:
    dampak: int
    alasan: str | None


def nilai(peristiwa: list) -> dict[str, Penilaian]:
    """Penilaian per URL wakil peristiwa. Murni fungsi dari isi `peristiwa` —
    tidak ada I/O, tidak ada cache, tidak ada jalur gagal."""
    hasil: dict[str, Penilaian] = {}
    for p in peristiwa:
        teks = _teks(p)
        besar = _cocok(teks, FRASA_BESAR)
        sedang = _cocok(teks, FRASA_SEDANG)
        primer = p.bobot >= BOBOT_PRIMER

        if _dibuang(teks, besar):
            d, label = 0, None
        elif besar or p.jumlah_media >= BATAS_RAMAI:
            d, label = 3, besar or "Liputan luas"
        elif sedang:
            d, label = 2, sedang
        elif p.jumlah_media >= BATAS_SEDANG or primer:
            d, label = 2, "Liputan meluas" if not primer else "Sumber primer"
        else:
            d, label = 1, None

        hasil[p.url] = Penilaian(d, label)
    return hasil


# --------------------------------------------------------------------------- #
# Internal
# --------------------------------------------------------------------------- #


def _teks(p) -> str:
    """Judul dan ringkasan jadi satu, huruf kecil, tanda baca jadi spasi, lalu
    diapit spasi. Pengapit itu yang membuat pencocokan `in` tetap per kata:
    " ecb " tidak cocok dengan "necbot", " ump " tidak cocok dengan "kumpul"."""
    mentah = f"{p.judul} {p.ringkasan or ''}".lower()
    bersih = "".join(c if c.isalnum() else " " for c in mentah)
    return f" {' '.join(bersih.split())} "


def _cocok(teks: str, kelompok: dict[str, tuple[str, ...]]) -> str | None:
    """Label kelompok pertama yang salah satu frasanya ada di teks."""
    for label, frasa in kelompok.items():
        if any(f" {f} " in teks for f in frasa):
            return label
    return None


def _dibuang(teks: str, besar: str | None) -> bool:
    """Noise dibuang kecuali peristiwanya juga menyentuh frasa besar — peresmian
    pabrik tetap seremonial, tapi "Prabowo teken inpres di sela peresmian"
    bukan."""
    if besar:
        return False
    return any(f" {f} " in teks for f in FRASA_BUANG)
