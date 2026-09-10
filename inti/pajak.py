"""
pajak.py — kenali berita perpajakan Indonesia dan beri subtopiknya.

Bagian "Perpajakan" di halaman pagi tidak bisa disusun dari feed saja: berita
pajak tersebar di Kontan, CNBC, Detik, dan feed Google News "fiskal", semuanya
berlabel `makro`. Jadi bagian ini ditentukan **isi**, bukan asal feed —
dengan satu pengecualian: feed yang semua isinya pajak (pengumuman DJP) diberi
kategori `pajak` langsung di feed.toml, karena judulnya sering tidak menyebut
pajak sama sekali ("Pemberitahuan Waktu Henti (Downtime)").

Prinsipnya sama dengan inti/dampak.py: daftar frasa yang bisa dibaca dan diubah
dalam satu menit, tanpa jaringan, tanpa biaya. Tiga hal yang dinilai:

1. **Apakah ini berita pajak** — pajak pusat, bea cukai, dan aturan/sengketa di
   sekitarnya. Perpajakan di sini mengikuti pengertian APBN: penerimaan
   perpajakan = pajak + kepabeanan dan cukai.
2. **Apakah ini pajak daerah** — PKB, PBB-P2, Samsat, pemutihan. Tetap tampil,
   tapi di bawah pajak pusat. Pada data 9 Sep 2026 sekitar sepertiga berita
   pajak adalah siaran pers pemda soal pajak kendaraan; tanpa ini merekalah
   yang mengisi bagiannya.
3. **Apakah ini promosi atau seremonial** — brevet, seminar, "Pajak Bertutur",
   halaman tag situs. Dibuang.

Plus satu label subtopik (Restitusi, Coretax, Penegakan hukum, ...) yang tampil
sebagai `alasan` — di bagian yang semua isinya pajak, label "Regulasi" dari
penilai dampak tidak menerangkan apa pun.
"""

from __future__ import annotations

from dataclasses import dataclass

# Kategori feed yang isinya boleh dipindah ke bagian Perpajakan. `pasar` tidak
# ikut: "Prospek saham FILM di tengah insentif pajak film" adalah analisis
# saham, dan pembaca bagian Pasar yang kehilangan dia. `global` tidak ikut
# karena bagian ini perpajakan Indonesia — "Chancellor tax rises" bukan urusannya.
DAPAT_PINDAH = {"makro", "politik"}

# Kata yang langsung menandai berita pajak. Dicocokkan per kata utuh (lihat
# `_teks`), jadi "pph" tidak cocok di tengah kata lain.
PENANDA: tuple[str, ...] = (
    "pajak", "perpajakan", "ditjen pajak", "djp", "coretax", "fiskus",
    "pph", "ppnbm", "npwp", "spt", "wajib pajak", "tax amnesty", "tax holiday",
    "tax allowance", "tax ratio", "bea cukai", "cukai", "kepabeanan",
    "bea masuk", "bea keluar", "pmse", "spp tdln",
    # Nama jenis pajak daerah yang tidak punya arti lain. "PKB" sengaja tidak:
    # itu juga Partai Kebangkitan Bangsa.
    "pbb p2", "pbjt", "bbnkb", "opsen",
    # Penindakan cukai yang judulnya jarang menyebut "cukai".
    "rokok ilegal",
)

# Situs luar negeri yang menerjemahkan berita pajak negaranya sendiri ke
# bahasa Indonesia dan ikut terjaring Google News. Bagian ini perpajakan
# Indonesia.
DOMAIN_ASING = {"vietnam.vn"}

# Kata pajak yang juga dipakai untuk hal lain. Dihitung sebagai penanda kecuali
# salah satu kata pembatalnya ikut muncul. Kasus nyata dari feed Google News:
# "Pelaku dibui 4 tahun & wajib bayar restitusi Rp29,5 juta" (restitusi korban
# pidana) dan "Satwas SDKP di PPN Bastiong" (Pelabuhan Perikanan Nusantara).
PENANDA_RANCU: dict[str, tuple[str, ...]] = {
    "restitusi": ("korban", "pelaku", "lpsk", "terdakwa", "vonis", "dibui",
                  "penjara", "pidana penjara"),
    "ppn": ("pelabuhan", "perikanan", "nelayan", "rumpon", "sdkp"),
}

# Pajak daerah. Diturunkan ke bawah bagiannya, tidak dibuang: kalau pemda
# menaikkan tarif PBJT hotel secara besar-besaran, itu tetap berita.
PENANDA_DAERAH: tuple[str, ...] = (
    "pajak daerah", "pajak kendaraan", "bbnkb", "samsat", "opsen",
    # Bukan "pbb" polos: itu juga Perserikatan Bangsa-Bangsa, dan konvensi
    # pajak internasional PBB justru berita pajak pusat.
    "pbb p2", "pajak pbb", "pajak bumi dan bangunan", "pajak reklame", "pajak hotel",
    "pajak restoran", "pajak hiburan", "pbjt", "pajak air tanah", "retribusi",
    "bapenda", "bpkad", "pendapatan asli daerah", "pad", "pemutihan",
    "pemkab", "pemkot", "pemprov", "bupati", "wali kota", "walikota",
    "gubernur", "dprd", "dprk", "sekda", "fiskal daerah", "kas daerah",
)

# Situs pemda sendiri. Siaran persnya jarang menyebut "pemprov" di judul —
# "Bayar Pajak Tanpa KTP Pemilik Pertama" dari bantenprov.go.id — tapi
# domainnya sudah mengatakan semuanya.
DOMAIN_PEMDA = ("prov.go.id", "kab.go.id", "kota.go.id")

# Promosi, pelatihan, seremonial kampanye, dan halaman yang bukan berita.
# Khusus bagian ini — "seminar" di bagian lain bisa jadi paparan Gubernur BI,
# jadi daftar ini tidak dipindah ke dampak.FRASA_BUANG.
PENANDA_BUANG: tuple[str, ...] = (
    "brevet", "early bird", "webinar", "seminar", "segera daftar",
    "gabung sekarang", "belajar di sini", "unduh di sini", "kelas pajak",
    "pelatihan", "pajak bertutur", "bincang pajak", "gebyar", "kompetisi",
    "pemenang", "penghargaan", "edukasi",
    # Panduan evergreen dari situs konsultan — bukan kejadian.
    "cara lapor", "cara mengajukan", "cara menghitung", "cara bayar",
    "cara daftar", "cara membuat", "begini cara", "simak cara",
    # Halaman tag DDTCNews yang ikut terindeks Google News: "Artikel dan
    # berita dengan kata kunci ..." dan "Artikel dan berita tentang ...".
    "artikel dan berita",
)

# Subtopik, diperiksa berurutan — yang pertama cocok menang. Urutannya dari
# yang paling spesifik: "KPK sita aset eks pejabat pajak terkait restitusi"
# adalah berita penegakan hukum, bukan berita restitusi.
TOPIK: dict[str, tuple[str, ...]] = {
    "Penegakan hukum": (
        "kpk", "gratifikasi", "suap", "korupsi", "pidana pajak", "penyidikan",
        "tersangka", "penyitaan", "sita", "gijzeling", "perampasan aset",
        "dirampas", "penagihan", "tunggakan", "rokok ilegal", "penyelundupan",
    ),
    "Restitusi": ("restitusi", "pengembalian pendahuluan"),
    "Coretax & layanan": (
        "coretax", "downtime", "waktu henti", "djp online", "e faktur",
        "efaktur", "e bupot", "aplikasi", "layanan",
    ),
    "Pajak digital & internasional": (
        "pmse", "transaksi digital", "platform digital", "kripto",
        "spp tdln", "pajak minimum global",
        "global minimum tax", "pilar dua", "p3b", "tax treaty", "oecd",
        "lintas negara", "luar negeri",
    ),
    "Kepabeanan & cukai": (
        "bea cukai", "cukai", "bea masuk", "bea keluar", "kepabeanan",
    ),
    "Profesi & sengketa": (
        "konsultan pajak", "kuasa wajib pajak", "pengadilan pajak",
        "sengketa pajak", "banding", "keberatan", "ikpi",
    ),
    "Penerimaan & target": (
        "penerimaan pajak", "penerimaan negara", "penerimaan perpajakan",
        "target penerimaan", "shortfall", "tax ratio", "rasio pajak",
        "realisasi", "basis pajak", "potensi pajak", "ekstensifikasi",
    ),
    "Tarif & insentif": (
        "tarif", "insentif", "tax holiday", "tax allowance", "dtp",
        "ditanggung pemerintah", "pembebasan", "fasilitas", "diskon pajak",
    ),
    "Aturan baru": (
        "pmk", "peraturan menteri keuangan", "pp", "peraturan pemerintah",
        "perdirjen", "peraturan dirjen", "surat edaran", "ruu", "uu",
        "aturan baru", "sop",
    ),
}


@dataclass(slots=True, frozen=True)
class Klasifikasi:
    pajak: bool         # berita perpajakan menurut isinya
    daerah: bool        # pajak daerah — diurutkan setelah pajak pusat
    buang: bool         # promosi/seremonial — tidak ditampilkan
    topik: str | None   # label subtopik untuk `alasan`


def periksa(p) -> Klasifikasi:
    """Nilai satu peristiwa. Murni fungsi dari judul, ringkasan, dan domainnya.

    **Masuk-tidaknya dan dibuang-tidaknya diputuskan dari judul saja.**
    Ringkasan menyebut pajak sambil lalu jauh lebih sering daripada judul:
    pada 9 Sep, "Bappenas: Tinggalkan Model Upah Murah" masuk hanya karena
    ringkasannya menyebut "Menteri PPN", dan "94% SPBU Salurkan B50" karena
    "Pertamina Patra Niaga (PPN)". Judul yang tidak menyebut pajak jarang
    berita pajak. Ringkasan tetap dipakai untuk pembatal kata rancu, penanda
    daerah (penurunan, bukan pembuangan), dan label subtopik.
    """
    judul = _teks(p.judul)
    semua = _teks(f"{p.judul} {p.ringkasan or ''}")

    pajak = p.domain not in DOMAIN_ASING and (
        _ada(judul, PENANDA)
        or any(
            f" {kata} " in judul and not _ada(semua, pembatal)
            for kata, pembatal in PENANDA_RANCU.items()
        )
    )
    daerah = _ada(semua, PENANDA_DAERAH) or p.domain.endswith(DOMAIN_PEMDA)
    topik = "Pajak daerah" if daerah else next(
        (label for label, frasa in TOPIK.items() if _ada(semua, frasa)), None
    )
    return Klasifikasi(
        pajak=pajak, daerah=daerah, buang=_ada(judul, PENANDA_BUANG), topik=topik
    )


def _ada(teks: str, frasa: tuple[str, ...]) -> bool:
    return any(f" {f} " in teks for f in frasa)


def _teks(mentah: str) -> str:
    """Sama dengan dampak._teks: huruf kecil, tanda baca jadi spasi, diapit
    spasi — supaya "PBB-P2" cocok dengan "pbb p2" dan " pp " tidak cocok di
    dalam "kapPPa"."""
    bersih = "".join(c if c.isalnum() else " " for c in mentah.lower())
    return f" {' '.join(bersih.split())} "
