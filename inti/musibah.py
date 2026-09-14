"""
musibah.py — kecelakaan transportasi berskala besar.

Ditambahkan 14 Sep 2026, setelah satu kasus yang tidak bisa dibela: **KM Virgo
Transport 8 terbalik di Laut Jawa membawa 243 penumpang**, dan tidak satu pun
beritanya masuk halaman pagi. Bukan kalah bersaing di pemeringkatan — tidak
pernah sampai ke sana. Dua pintu menutupnya sekaligus:

1. `relevan()` di alur/edisi.py menyaring bagian Politik dengan daftar kata
   ekonomi. "Kapal", "terbalik", "tenggelam", "penumpang" tidak ada di sana,
   jadi judul seperti "Kapal Virgo Transport 8 terbalik di Laut Jawa, bawa 243
   penumpang" dibuang utuh.
2. `FRASA_BUANG` di inti/dampak.py memuat "kecelakaan" dan "tabrakan" — dibuat
   untuk tabrakan motor di feed berita umum, tapi tidak bisa membedakan satu
   motor dari satu kapal penumpang.

Yang membuat penutupan itu terasa salah bukan cuma kapalnya. Di edisi yang sama
(14 Sep), bagian Politik memuat "Kakak Beradik Tewas Saat Rumahnya Terbakar di
Surabaya" — lolos karena ringkasannya menyebut **korsleting listrik**, dan
"listrik" ada di daftar kata ekonomi untuk urusan tarif. Jadi saringannya
meloloskan kebakaran satu rumah dan membuang feri berisi 243 penumpang. Itu
bukan pertimbangan editorial, itu kecelakaan kata kunci.

**Aturannya menuntut dua syarat sekaligus**, dan itu inti berkas ini: satu kata
peristiwa (kapal, terbalik, pesawat, kereta) **dan** satu kata skala (penumpang,
evakuasi, Basarnas, pelabuhan). Satu syarat saja tidak cukup, karena masing-
masing sendirian terlalu sering muncul:

    "Kapal" saja        -> kapal pesiar, kapal perang, ekspor lewat kapal
    "Kecelakaan" saja   -> tabrakan motor, yang memang seharusnya tertahan
    "Penumpang" saja    -> tarif, mudik, okupansi bandara

Dipasangkan, keduanya berarti hal yang spesifik: kendaraan pengangkut orang
sedang celaka, dan ada operasi penyelamatan. Tabrakan motor tidak punya sisi
skala, jadi tetap tertahan seperti sebelumnya — daftar-buang di dampak.py tidak
dilonggarkan sedikit pun untuknya.

Ruang lingkupnya sengaja hanya **transportasi**. Bencana alam sudah punya jalan
sendiri di KATA_POLITIK (banjir, gempa, erupsi, karhutla, bencana), dan
menggabungkan keduanya di sini hanya akan membuat dua daftar yang saling
menimpa.
"""

from __future__ import annotations

# Kendaraan pengangkut orang, dan hal yang terjadi padanya. Sendirian, tiap
# kata di sini tidak berarti apa-apa — lihat docstring.
KATA_PERISTIWA = frozenset({
    # laut
    "kapal", "kmp", "feri", "ferry", "perahu", "speedboat", "tongkang",
    "tenggelam", "terbalik", "karam", "kandas",
    # udara, darat, rel
    "pesawat", "helikopter", "kereta", "krl", "lrt", "bus", "truk",
    # peristiwanya
    "kecelakaan", "tabrakan", "terguling",
    # "terbakar" dan "meledak" sengaja tidak masuk: kapal dan pesawat yang
    # terbakar sudah tertangkap lewat kendaraannya, sementara keduanya sendiri
    # menarik kebakaran rumah — persis berita yang bocor lewat "listrik" dan
    # jadi alasan berkas ini ditulis.
    # "anjlok" sengaja tidak masuk: "kereta anjlok" memang istilahnya, tapi
    # "harga anjlok" jauh lebih sering, dan berpasangan dengan "ratusan" di
    # kata skala ia meloloskan berita pasar sebagai musibah.
})

# Yang membedakan musibah besar dari kecelakaan harian: banyak orang di dalamnya
# dan ada operasi penyelamatan. Bukan sekadar ada korban — "tabrakan maut, 1
# tewas" punya korban dan memang tidak dimaksudkan lolos.
KATA_SKALA = frozenset({
    "penumpang", "awak", "nakhoda", "kru",
    # "hilang" ikut karena begitulah berita SAR ditulis — "lima jurnalis hilang
    # setelah perahu terbalik", "8 penumpang hilang". Harganya diketahui dan
    # diterima: "bus hilang kendali" ikut lolos, satu kendaraan tanpa skala.
    # Berita seperti itu mendarat di dasar bagiannya karena cuma diliput satu
    # media; kehilangan berita orang hilang di laut jauh lebih mahal.
    "hilang",
    # "korban" sengaja tidak masuk: ia menandai ada yang celaka, bukan
    # seberapa besar. Dengan "korban" di sini, "tabrakan maut, 1 tewas" lolos —
    # dan itu justru berita yang daftar-buang dampak.py memang dibuat menahan.
    "evakuasi", "dievakuasi", "basarnas", "sar", "pencarian",
    "puluhan", "ratusan", "massal",
    # Pelabuhan, dermaga, bandara, stasiun sempat ada di sini lalu dibuang:
    # itu **tempat**, bukan skala. "Kapal pesiar mewah bersandar di Pelabuhan
    # Benoa" lolos karenanya — persis kesalahan yang aturan dua syarat ini
    # dibuat untuk mencegah.
})


def _kata(teks: str) -> set[str]:
    """Sama dengan `_kata` di alur/edisi.py: per kata, bukan per substring.
    " sar " tidak boleh cocok dengan "besar", dan "bus" tidak dengan "bushel"."""
    return set("".join(c if c.isalnum() else " " for c in teks.lower()).split())


def periksa(teks: str) -> bool:
    """Benar kalau teks menyentuh kata peristiwa **dan** kata skala.

    Menerima teks mentah maupun yang sudah dinormalkan (inti/dampak.py
    memberinya yang kedua) — keduanya dipotong per kata dengan cara yang sama.
    """
    k = _kata(teks)
    return bool(k & KATA_PERISTIWA) and bool(k & KATA_SKALA)
