"""
sentimen.py — beri tiap peristiwa status: positif, negatif, atau netral.

Saudara kembar `inti/dampak.py`, dengan batasan yang sama: deterministik,
seluruhnya lokal, tanpa kunci API, tanpa kuota, tanpa biaya, dan tanpa jalur
gagal karena jaringan. Yang dinilai berbeda — `dampak` menjawab "seberapa perlu
tahu", `sentimen` menjawab "arahnya ke mana".

Kenapa bukan kamus kata positif/negatif biasa: di berita ekonomi, arah kata
tidak menentukan arah beritanya. "Naik" positif untuk laba dan ekspor, negatif
untuk inflasi, utang, dan pengangguran. Kamus rata akan menandai "Inflasi naik
jadi 4,2%" sebagai positif — salah, dan salahnya sistematis. Jadi penilaiannya
tiga lapis:

1. **Arah + pokok.** Kata arah (naik/turun/anjlok/menguat) dipasangkan dengan
   pokok di dekatnya — didahulukan yang di sebelah kiri, karena subjek
   mendahului predikat — dan tandanya ditentukan oleh pokok itu:
   `POKOK_BAIK_NAIK` (laba, ekspor, cadangan devisa) versus `POKOK_BURUK_NAIK`
   (inflasi, utang, pengangguran, kredit macet). Kata arah tanpa pokok yang
   dikenal diabaikan.
2. **Frasa bertanda tetap.** Yang tandanya tidak bergantung arah apa pun:
   "gagal bayar", "pailit", "resesi" selalu negatif; "insentif", "rekor
   tertinggi", "kesepakatan dagang" selalu positif.
3. **Negasi.** Dua kata sebelum pemicu diperiksa ("tidak", "belum", "batal",
   "urung", "tanpa"); kalau kena, tandanya dibalik. Ini yang menyelamatkan
   "Rupiah tidak melemah" dan "BI batal menaikkan suku bunga".

Judul berbobot dua kali ringkasan. Judul adalah pernyataan redaksi tentang
peristiwanya; ringkasan sering memuat latar dan kutipan yang arahnya lain.

Netral bukan tempat pembuangan, melainkan jawaban: peristiwa tanpa pemicu, atau
yang pemicunya seimbang, memang tidak berarah. Sebagian besar berita —
pengumuman jadwal, agenda rapat, pernyataan pejabat — memang begitu. Menebak
arah untuk keduanya lebih buruk daripada mengaku netral.

Batasnya jujur: ini pencocokan frasa, bukan pemahaman. Ironi, kutipan bantahan,
dan "positif bagi siapa" ada di luar jangkauannya. Kalau labelnya sering terasa
meleset setelah beberapa hari, daftar di bawah ini yang diubah — bukan diganti
model.
"""

from __future__ import annotations

from dataclasses import dataclass

POSITIF = "positif"
NEGATIF = "negatif"
NETRAL = "netral"

# Judul dihitung dua kali ringkasan — lihat docstring.
BOBOT_JUDUL = 2
BOBOT_RINGKASAN = 1

# Seberapa jauh pokok boleh dari kata arahnya, dalam kata. Empat menampung
# "harga minyak dunia turun" dan "laba bersih emiten itu melonjak", tapi belum
# menyeberang ke klausa berikutnya pada judul berita yang biasanya pendek.
JANGKAUAN = 4

# Dua kata sebelum pemicu. Cukup untuk "tidak jadi naik" dan "belum juga turun".
JANGKAUAN_NEGASI = 2

NEGASI: frozenset[str] = frozenset({
    "tidak", "tak", "bukan", "belum", "batal", "urung", "tanpa",
    "menolak", "tolak", "mencegah", "cegah", "not",
})

# Bentuk transitif ikut ("menaikkan", "memangkas"): judul kebijakan hampir
# selalu memakainya — "BI menaikkan suku bunga", bukan "suku bunga naik".
ARAH_NAIK: frozenset[str] = frozenset({
    "naik", "menaik", "menaikkan", "kenaikan", "meningkat", "meningkatkan",
    "peningkatan", "melonjak", "lonjakan", "meroket", "menguat", "penguatan",
    "tumbuh", "pertumbuhan", "melesat", "bertambah", "menambah", "menambahkan",
    "melambung", "rebound", "reli", "rally",
})

ARAH_TURUN: frozenset[str] = frozenset({
    "turun", "menurun", "menurunkan", "penurunan", "anjlok", "merosot",
    "melemah", "melemahkan", "pelemahan", "ambles", "ambruk", "jeblok",
    "terkoreksi", "koreksi", "menyusut", "susut", "tergerus", "berkurang",
    "mengurangi", "memangkas", "pangkas", "pemangkasan", "memotong",
    "longsor", "lesu", "loyo",
})

# Pokok yang **naiknya kabar baik**: arah naik jadi positif, arah turun negatif.
POKOK_BAIK_NAIK: frozenset[str] = frozenset({
    "laba", "untung", "keuntungan", "pendapatan", "penjualan", "omzet",
    "dividen", "ekspor", "investasi", "modal", "produksi", "kapasitas",
    "ekonomi", "pdb", "konsumsi", "cadangan", "devisa", "surplus", "ihsg",
    "indeks", "saham", "rupiah", "kurs", "obligasi", "sbn", "kredit",
    "pembiayaan", "likuiditas", "upah", "gaji", "ump", "umk", "daya",
    "lapangan", "wisatawan", "kunjungan", "panen", "pasokan",
    "produktivitas", "manufaktur", "pmi", "emas", "bara", "nikel", "cpo",
    "sawit", "minyak", "komoditas", "harga",
})

# Pokok yang **naiknya kabar buruk**. Menang atas daftar di atas di mana pun ia
# berada dalam jangkauan, bukan hanya kalau lebih dekat: "inflasi harga pangan
# naik" harus negatif walau "harga" berdiri lebih rapat ke kata arahnya.
#
# Ketimpangan itu disengaja. Dua jenis salah di sini tidak setara — menandai
# kabar buruk sebagai positif membuat halaman berbohong ke arah yang menenangkan,
# sedangkan sebaliknya hanya membuatnya terlalu waspada.
POKOK_BURUK_NAIK: frozenset[str] = frozenset({
    "inflasi", "utang", "defisit", "rugi", "kerugian", "pengangguran", "phk",
    "kemiskinan", "npl", "macet", "biaya", "beban", "ongkos", "cukai",
    "pajak", "tarif", "pungutan", "iuran", "impor", "korupsi", "risiko",
    "ketidakpastian", "tekanan", "volatilitas", "bunga", "suku", "yield",
    "premi", "denda", "sanksi", "bencana", "banjir", "kebakaran",
    "karhutla", "gempa", "wabah", "polusi", "kecelakaan", "konflik",
    "perang", "protes", "demo", "mogok",
})

# Frasa yang tandanya tidak bergantung arah. Dicocokkan sebagai urutan kata
# utuh, jadi frasa dua kata di sini aman dari kecocokan sebagian.
FRASA_POSITIF: tuple[str, ...] = (
    "rekor tertinggi", "level tertinggi", "all time high", "cetak rekor",
    "kesepakatan dagang", "kerja sama", "kerjasama", "kesepakatan",
    "insentif", "keringanan pajak", "relaksasi", "stimulus", "pelonggaran",
    "pelonggaran moneter", "bantuan", "hibah", "pemulihan", "membaik",
    "perbaikan", "optimisme", "optimistis", "pulih", "ekspansi", "peluang",
    "terobosan", "ipo", "right issue", "rights issue", "buyback",
    "bagi dividen", "tebar dividen", "melampaui target",
    "di atas ekspektasi", "lebih baik dari perkiraan", "peringkat naik",
    "arus masuk", "net buy", "capital inflow", "penurunan suku bunga",
    "pangkas suku bunga", "pemangkasan suku bunga", "bebas bea",
    "penghapusan tarif", "hilirisasi",
)

FRASA_NEGATIF: tuple[str, ...] = (
    "gagal bayar", "default", "pailit", "bangkrut", "pkpu", "delisting",
    "suspensi saham", "resesi", "krisis", "krisis keuangan", "devaluasi",
    "sanksi ekonomi", "embargo", "perang dagang", "perang tarif",
    "larangan ekspor", "larangan impor", "moratorium", "pembatasan",
    "kuota impor", "bea masuk", "tarif impor", "kenaikan cukai",
    "kenaikan tarif", "ppn naik", "pemutusan hubungan kerja", "phk massal",
    "rumahkan karyawan", "tutup pabrik", "hentikan operasi",
    "setop produksi", "kredit macet", "kredit bermasalah", "lilitan utang",
    "di bawah ekspektasi", "meleset dari target", "gagal memenuhi",
    "downgrade", "peringkat turun", "arus keluar", "net sell",
    "capital outflow", "aksi jual", "panic selling", "kenaikan suku bunga",
    "pengetatan moneter", "gejolak", "ketidakpastian", "kekhawatiran",
    # Bentuk yang benar-benar muncul di judul, bukan hanya kata dasarnya:
    # "Investor Khawatir...", "Bursa Asia Tertekan...", "Memanas, Kanada...".
    "khawatir", "mengkhawatirkan", "tertekan", "memanas", "eskalasi",
    "terancam", "ancaman", "waswas",
    "korupsi", "penyelewengan", "penggelapan", "tersangka", "gugatan",
    "denda", "kelangkaan", "gagal panen", "pemadaman", "mogok kerja",
    "unjuk rasa", "kerusuhan", "penipuan",
)


@dataclass(slots=True, frozen=True)
class Status:
    """`label` untuk ditampilkan, `skor` untuk mengurutkan atau menyetel ambang,
    `pemicu` untuk menjelaskan kenapa — kalau labelnya salah, `pemicu` menyebut
    baris mana di berkas ini yang harus diubah."""

    label: str
    skor: int
    pemicu: str | None

    @property
    def netral(self) -> bool:
        return self.label == NETRAL


def nilai(peristiwa: list) -> dict[str, Status]:
    """Status per URL wakil peristiwa. Murni fungsi dari isi `peristiwa` — tidak
    ada I/O, tidak ada cache, tidak ada jalur gagal. Bentuknya sengaja sama
    dengan `inti.dampak.nilai` supaya keduanya dipasang dengan cara yang sama."""
    return {p.url: nilai_teks(p.judul, getattr(p, "ringkasan", None)) for p in peristiwa}


def nilai_teks(judul: str, ringkasan: str | None = None) -> Status:
    """Inti penilaian, dipisah supaya bisa diuji dan dipakai tanpa objek
    peristiwa."""
    skor = 0
    # Pemicu yang dilaporkan adalah yang bobot mutlaknya terbesar — pada teks
    # dengan banyak pemicu, itu yang paling menjelaskan hasil akhirnya.
    terkuat: tuple[int, str] | None = None

    for teks, bobot in ((judul, BOBOT_JUDUL), (ringkasan or "", BOBOT_RINGKASAN)):
        for tanda, nama in _pemicu(_kata(teks)):
            skor += tanda * bobot
            berat = abs(tanda) * bobot
            if terkuat is None or berat > terkuat[0]:
                terkuat = (berat, nama)

    if skor > 0:
        label = POSITIF
    elif skor < 0:
        label = NEGATIF
    else:
        label = NETRAL
    # Peristiwa yang pemicunya saling meniadakan tetap netral, dan menyebut satu
    # pemicunya di situ akan menyesatkan — netral berarti "tidak berarah".
    return Status(label, skor, terkuat[1] if terkuat and label != NETRAL else None)


# --------------------------------------------------------------------------- #
# Internal
# --------------------------------------------------------------------------- #


def _kata(teks: str) -> list[str]:
    """Huruf kecil, tanda baca jadi pemisah. Daftar (bukan set) karena posisi
    kata itulah yang dipakai untuk kedekatan dan negasi."""
    return "".join(c if c.isalnum() else " " for c in teks.lower()).split()


def _dinegasikan(kata: list[str], posisi: int) -> bool:
    awal = max(0, posisi - JANGKAUAN_NEGASI)
    return any(k in NEGASI for k in kata[awal:posisi])


def _pemicu(kata: list[str]) -> list[tuple[int, str]]:
    """Semua pemicu di satu potong teks, sebagai (tanda, nama). Frasa tetap dan
    pasangan arah+pokok dikumpulkan sekaligus; keduanya bisa menyala pada teks
    yang sama dan memang boleh saling menambah."""
    hasil = _frasa_tetap(kata)
    hasil.extend(_arah_pokok(kata))
    return hasil


def _frasa_tetap(kata: list[str]) -> list[tuple[int, str]]:
    hasil: list[tuple[int, str]] = []
    for frasa in FRASA_POSITIF:
        hasil.extend(_cari_frasa(kata, frasa, 1))
    for frasa in FRASA_NEGATIF:
        hasil.extend(_cari_frasa(kata, frasa, -1))
    return hasil


def _cari_frasa(kata: list[str], frasa: str, tanda: int) -> list[tuple[int, str]]:
    """Cocokkan frasa sebagai urutan kata utuh — "denda" tidak cocok dengan
    "dendam", dan "tarif impor" hanya cocok kalau kedua katanya berurutan."""
    potong = frasa.split()
    n = len(potong)
    hasil: list[tuple[int, str]] = []
    for i in range(len(kata) - n + 1):
        if kata[i:i + n] == potong:
            hasil.append((-tanda if _dinegasikan(kata, i) else tanda, frasa))
    return hasil


def _arah_pokok(kata: list[str]) -> list[tuple[int, str]]:
    """Kata arah hanya berarti kalau ada pokoknya. Arah tanpa pokok yang dikenal
    diabaikan — "penonton konser melonjak" bukan kabar pasar."""
    hasil: list[tuple[int, str]] = []
    for i, k in enumerate(kata):
        if k in ARAH_NAIK:
            naik = True
        elif k in ARAH_TURUN:
            naik = False
        else:
            continue

        pokok = _pokok_terdekat(kata, i)
        if pokok is None:
            continue
        nama, baik_naik = pokok

        tanda = 1 if naik == baik_naik else -1
        if _dinegasikan(kata, i):
            tanda = -tanda
        hasil.append((tanda, f"{nama} {k}"))
    return hasil


def _pokok_terdekat(kata: list[str], posisi: int) -> tuple[str, bool] | None:
    """Pokok dari kata arah di `posisi`, beserta apakah naiknya baik.

    Dua aturan yang urutannya penting:

    **Kiri dulu, kanan sebagai cadangan.** Dalam bahasa Indonesia subjek
    mendahului predikat — "inflasi naik", bukan "naik inflasi" — jadi pokok yang
    benar hampir selalu ada di sebelah kiri kata arahnya. Tanpa ini, "Laba naik,
    utang bertambah" membuat "naik" menyeberang ke klausa berikutnya dan
    memungut "utang". Sisi kanan tetap dipakai kalau kiri kosong, untuk judul
    kebijakan seperti "BI menaikkan suku bunga acuan".

    **Di satu sisi, `POKOK_BURUK_NAIK` menang** walau letaknya lebih jauh, jadi
    "inflasi harga pangan naik" tidak jadi positif gara-gara "harga" berdiri
    lebih rapat ke "naik".
    """
    kiri = range(posisi - 1, max(-1, posisi - JANGKAUAN - 1), -1)
    kanan = range(posisi + 1, min(len(kata), posisi + JANGKAUAN + 1))
    for sisi in (kiri, kanan):
        for daftar, baik_naik in ((POKOK_BURUK_NAIK, False), (POKOK_BAIK_NAIK, True)):
            for j in sisi:
                if kata[j] in daftar:
                    return kata[j], baik_naik
    return None
