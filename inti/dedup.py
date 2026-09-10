"""
dedup.py — kelompokkan artikel yang menceritakan peristiwa yang sama.

Ini bagian yang menentukan halaman pagi berhasil atau tidak (ARSITEKTUR.md §16).
Dari 1.571 artikel nyata, hanya **satu** judul yang identik di lebih dari satu
media: media menulis ulang headline. Jadi pencocokan string tidak berguna, dan
yang dipakai kemiripan token.

Metodenya sengaja sederhana — token judul yang dipenggal imbuhannya, lalu
union-find. Dua judul dianggap satu peristiwa lewat **dua jalan yang berbeda**:

1. **Jaccard >= 0,42** — irisannya besar secara proporsi.
2. **Tiga kata langka yang sama, menutup separuh judul terpendek** — irisannya
   kecil, tapi isinya kata yang jarang muncul hari itu.

Jalan kedua bukan pelonggaran jalan pertama; menurunkan ambang tidak bisa
menirunya. Alasannya panjang dan diukur, ada di dekat MIN_LANGKA di bawah.

- Tanpa dependensi baru, tanpa model, tanpa embedding. Untuk ~1.000 judul pendek
  per hari, ini cukup dan bisa dijelaskan saat hasilnya aneh.
- MinHash/LSH baru masuk akal kalau jumlahnya naik ordo besaran. Sampai itu,
  perbandingan langsung lewat indeks terbalik sudah jauh lebih cepat dari yang
  dibutuhkan.

Hasil sampingnya justru yang paling berharga: **berapa banyak media meliput satu
peristiwa** — dipakai langsung sebagai urutan prioritas, tanpa NLP.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

# Kata yang muncul di mana-mana dan tidak membedakan satu berita dari yang lain.
# Termasuk kata khas judul berita Indonesia ("resmi", "simak", "begini").
STOPWORD = {
    "yang", "dan", "di", "ke", "dari", "untuk", "pada", "dengan", "ini", "itu",
    "akan", "ada", "tidak", "bisa", "dalam", "juga", "sudah", "atau", "karena",
    "oleh", "saat", "hingga", "usai", "jadi", "lebih", "masih", "para", "agar",
    "soal", "buat", "kata", "ujar", "sebut", "menjadi", "adalah", "telah",
    "resmi", "simak", "begini", "berikut", "terbaru", "terkini", "video",
    "foto", "live", "update", "hari", "kini", "baru", "usai", "jelang",
    # Boilerplate laporan pasar harian. Kata-kata ini menandai *kapan* dan
    # *berapa*, bukan peristiwa apa, jadi ia menautkan laporan IHSG sore dengan
    # laporan rupiah sore — dua hal berbeda yang kebetulan ditulis sepola.
    # Kelangkaan tidak menyaringnya: pada 9 Sep "anjak" dan "sore" masing-masing
    # muncul di 2 judul, lebih langka daripada kata yang justru benar.
    "pagi", "siang", "sore", "malam", "dini", "kemarin", "besok", "sesi",
    "level", "posisi", "poin", "persen", "anjak", "tutup", "dibuka",
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "is", "as", "at",
    "by", "with", "from", "its", "it", "be", "are", "was", "will", "has",
    "after", "over", "amid", "says", "say", "new",
}

BUKAN_KATA = re.compile(r"[^0-9a-zA-ZÀ-ɏ]+")

# Imbuhan Indonesia yang dipenggal sebelum membandingkan. Ini yang membuat
# "Purbaya **Buka** Peluang APBN..." dan "...untuk **Pembukaan** Rekening..."
# berbagi satu kata, bukan nol.
#
# Pemenggalnya kasar dan sengaja begitu: ia menghasilkan potongan yang sering
# bukan kata ("meningkat" -> "ingkat"), dan itu tidak apa-apa. Yang dibutuhkan
# di sini **konsistensi**, bukan kebenaran linguistik — asal dua judul yang
# menulis hal sama dipenggal jadi bentuk sama, pencocokannya bekerja. Stemmer
# Sastrawi yang benar butuh kamus dan dependensi baru untuk keuntungan yang
# belum terbukti perlu.
#
# Urutannya panjang-dulu supaya "peng" tidak kalah oleh "pe", dan sisa kata
# dijaga minimal empat huruf supaya "kereta" tidak jadi "eta".
AWALAN = ("memper", "menper", "diper", "keter", "peng", "peny", "pem", "pen",
          "per", "mem", "men", "meng", "meny", "ter", "ber", "me", "di", "ke",
          "se", "pe")
AKHIRAN = ("kannya", "annya", "inya", "nya", "kan", "lah", "kah", "an", "i")
MIN_SISA = 4

# Di bawah ini judulnya terlalu pendek untuk dinilai lewat Jaccard — dua judul
# tiga kata bisa mirip 0,67 hanya karena kebetulan.
MIN_TOKEN = 3

AMBANG = 0.42

# --- aturan kedua: sedikit kata, tapi kata-kata langka ---------------------- #
#
# Jaccard menghukum judul yang panjangnya berbeda dan yang kata pembedanya
# ditulis lain. Dua redaksi menulis peristiwa yang sama begini:
#
#     "Purbaya Buka Peluang APBN Biayai Saldo Rekening Masyarakat Rp50 Ribu"
#     "Menteri Keuangan Jelaskan Penggunaan APBN untuk Pembukaan Rekening
#      Masyarakat"
#
# Jaccard-nya 0,29 — jauh di bawah ambang. Menurunkan ambang bukan jawabannya:
# diukur ke data 10 Sep, ambang 0,20 menghasilkan satu kelompok berisi 280
# artikel. Cosine berbobot IDF juga tidak menolong; pasangan itu skornya 0,27
# sementara persentil 99 pasangan yang **tidak** berhubungan sudah 0,37.
#
# Yang membedakannya bukan seberapa besar irisannya, melainkan seberapa langka
# isi irisan itu. "apbn" muncul di 6 judul dari 1.121, "masyarakat" di 8,
# "rekening" di 20. Tiga kata selangka itu muncul bersama karena peristiwanya
# sama, bukan karena kebetulan.
#
# Yang dihitung **berapa kata langka yang dibagi**, bukan menuntut semua kata
# bersama langka — rumusan kedua itu pernah dicoba dan gagal justru pada contoh
# di atas, karena "buka" jadi kata umum setelah imbuhannya dipenggal.
MIN_LANGKA = 3      # sedikitnya tiga kata langka yang sama
MIN_TUMPANG = 0.5   # dan separuh judul terpendek harus tertutup irisannya
FRAKSI_LANGKA = 0.025  # "langka" = muncul di <=2,5% judul, minimal 10


def akar(kata: str) -> str:
    """Penggal satu akhiran lalu satu awalan. Lihat catatan di AWALAN — hasilnya
    tidak harus kata yang benar, cukup konsisten."""
    asli = kata
    for a in AKHIRAN:
        if kata.endswith(a) and len(kata) - len(a) >= MIN_SISA:
            kata = kata[: -len(a)]
            break
    for a in AWALAN:
        if kata.startswith(a) and len(kata) - len(a) >= MIN_SISA:
            kata = kata[len(a):]
            break
    return kata if len(kata) >= 3 else asli


def token(teks: str) -> frozenset[str]:
    """Kata judul yang membedakan, sudah dipenggal imbuhannya.

    STOPWORD diperiksa dua kali — sebelum dan sesudah pemenggalan. "menanjak"
    bukan stopword, tapi akarnya "anjak" ada di daftar; tanpa pemeriksaan kedua
    ia lolos dan kembali menautkan laporan pasar yang sepola.
    """
    hasil = set()
    for k in BUKAN_KATA.split(teks.lower()):
        if len(k) <= 2 or k in STOPWORD:
            continue
        a = akar(k)
        if a not in STOPWORD:
            hasil.add(a)
    return frozenset(hasil)


def tumpang(a: frozenset[str], b: frozenset[str]) -> float:
    """Koefisien tumpang tindih: irisan dibagi judul terpendek. Berbeda dari
    Jaccard justru pada yang penting di sini — ia tidak menghukum judul yang
    satu jauh lebih panjang dari yang lain."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    irisan = len(a & b)
    return irisan / (len(a) + len(b) - irisan)


def _mirip(
    a: frozenset[str],
    b: frozenset[str],
    ambang: float,
    muncul: Counter[str],
    batas_langka: int,
) -> bool:
    """Dua jalan menuju "peristiwa yang sama", dan yang kedua bukan pelonggaran
    yang pertama — ia menuntut hal yang berbeda.

    Jalan pertama: irisannya besar secara proporsi (Jaccard).
    Jalan kedua: irisannya kecil tapi isinya langka, dan menutup separuh judul
    terpendek. Menurunkan `ambang` tidak bisa meniru ini; ia melonggarkan semua
    pasangan sekaligus, termasuk yang irisannya hanya kata umum.
    """
    if jaccard(a, b) >= ambang:
        return True
    langka = sum(1 for k in a & b if muncul[k] <= batas_langka)
    return langka >= MIN_LANGKA and tumpang(a, b) >= MIN_TUMPANG


class _Union:
    """Union-find. Dipakai supaya A~B dan B~C menyatukan A, B, C jadi satu
    peristiwa walaupun A dan C sendiri tidak cukup mirip."""

    def __init__(self, n: int) -> None:
        self.induk = list(range(n))

    def cari(self, x: int) -> int:
        while self.induk[x] != x:
            self.induk[x] = self.induk[self.induk[x]]
            x = self.induk[x]
        return x

    def gabung(self, a: int, b: int) -> None:
        ra, rb = self.cari(a), self.cari(b)
        if ra != rb:
            self.induk[rb] = ra


def kelompokkan(judul: list[str], ambang: float = AMBANG) -> list[list[int]]:
    """Kembalikan indeks yang dikelompokkan per peristiwa.

    Kelompok diurutkan dari yang anggotanya terbanyak — itu proxy kepentingan.
    """
    token_per_item = [token(j) for j in judul]
    n = len(judul)
    uf = _Union(n)

    # Berapa judul memuat tiap kata. Dihitung dari korpus hari itu sendiri, bukan
    # dari daftar tetap: "krakatau" langka di hari biasa dan jadi kata umum pada
    # hari gunungnya meletus, dan justru pada hari itu ia berhenti membedakan
    # satu berita dari yang lain.
    muncul: Counter[str] = Counter()
    for t in token_per_item:
        muncul.update(t)
    batas_langka = max(10, int(n * FRAKSI_LANGKA))

    # Indeks terbalik: hanya bandingkan pasangan yang berbagi minimal satu token.
    # Tanpa ini semua pasangan dibandingkan; dengan ini sebagian besar pasangan
    # yang jelas tidak mirip tidak pernah disentuh.
    posting: dict[str, list[int]] = defaultdict(list)
    for i, t in enumerate(token_per_item):
        for k in t:
            posting[k].append(i)

    diperiksa: set[tuple[int, int]] = set()
    for indeks in posting.values():
        # Token yang muncul di mana-mana tidak membantu menyaring kandidat dan
        # justru membuat perbandingannya meledak.
        if len(indeks) > 60:
            continue
        for a_pos, i in enumerate(indeks):
            if len(token_per_item[i]) < MIN_TOKEN:
                continue
            for j in indeks[a_pos + 1:]:
                if len(token_per_item[j]) < MIN_TOKEN:
                    continue
                pasangan = (i, j)
                if pasangan in diperiksa:
                    continue
                diperiksa.add(pasangan)
                if _mirip(
                    token_per_item[i], token_per_item[j], ambang, muncul, batas_langka
                ):
                    uf.gabung(i, j)

    kelompok: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        kelompok[uf.cari(i)].append(i)

    return sorted(kelompok.values(), key=len, reverse=True)
