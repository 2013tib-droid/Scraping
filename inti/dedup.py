"""
dedup.py — kelompokkan artikel yang menceritakan peristiwa yang sama.

Ini bagian yang menentukan halaman pagi berhasil atau tidak (ARSITEKTUR.md §16).
Dari 1.571 artikel nyata, hanya **satu** judul yang identik di lebih dari satu
media: media menulis ulang headline. Jadi pencocokan string tidak berguna, dan
yang dipakai kemiripan token.

Metodenya sengaja sederhana — Jaccard atas token judul, lalu union-find:

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
from collections import defaultdict

# Kata yang muncul di mana-mana dan tidak membedakan satu berita dari yang lain.
# Termasuk kata khas judul berita Indonesia ("resmi", "simak", "begini").
STOPWORD = {
    "yang", "dan", "di", "ke", "dari", "untuk", "pada", "dengan", "ini", "itu",
    "akan", "ada", "tidak", "bisa", "dalam", "juga", "sudah", "atau", "karena",
    "oleh", "saat", "hingga", "usai", "jadi", "lebih", "masih", "para", "agar",
    "soal", "buat", "kata", "ujar", "sebut", "menjadi", "adalah", "telah",
    "resmi", "simak", "begini", "berikut", "terbaru", "terkini", "video",
    "foto", "live", "update", "hari", "kini", "baru", "usai", "jelang",
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "is", "as", "at",
    "by", "with", "from", "its", "it", "be", "are", "was", "will", "has",
    "after", "over", "amid", "says", "say", "new",
}

BUKAN_KATA = re.compile(r"[^0-9a-zA-ZÀ-ɏ]+")

# Di bawah ini judulnya terlalu pendek untuk dinilai lewat Jaccard — dua judul
# tiga kata bisa mirip 0,67 hanya karena kebetulan.
MIN_TOKEN = 3

AMBANG = 0.42


def token(teks: str) -> frozenset[str]:
    kata = BUKAN_KATA.split(teks.lower())
    return frozenset(k for k in kata if len(k) > 2 and k not in STOPWORD)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    irisan = len(a & b)
    return irisan / (len(a) + len(b) - irisan)


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
                if jaccard(token_per_item[i], token_per_item[j]) >= ambang:
                    uf.gabung(i, j)

    kelompok: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        kelompok[uf.cari(i)].append(i)

    return sorted(kelompok.values(), key=len, reverse=True)
