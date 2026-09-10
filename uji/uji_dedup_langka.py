"""Uji jalan kedua di `inti/dedup.py`: irisan kecil tapi isinya langka.

Yang diuji di sini bukan "apakah mirip", melainkan **batasnya** — pasangan yang
harus tergabung lewat jalan kedua, dan pasangan yang justru tidak boleh
tergabung walaupun sekilas sepola. Yang kedua itu yang gampang rusak: aturan
apa pun yang cukup longgar untuk menangkap judul yang ditulis ulang total juga
cukup longgar untuk menangkap kebetulan.

Korpus tiap uji dibuat kecil dan disebutkan isinya, karena "langka" dihitung
relatif terhadap korpus — sebuah kata langka atau tidak tergantung apa lagi yang
terbit hari itu.
"""

from collections import Counter

from inti import dedup


def pengisi(n: int) -> list[str]:
    """Judul lain yang tidak berhubungan, supaya korpusnya masuk akal dan
    ambang kelangkaan (2,5% korpus, minimal 10) punya penyebut."""
    return [f"Berita lain nomor {i} tentang topik sendiri saja" for i in range(n)]


def segrup(judul: list[str], a: int, b: int) -> bool:
    for g in dedup.kelompokkan(judul):
        if a in g and b in g:
            return True
    return False


# --------------------------------------------------------------------------- #
# pemenggalan imbuhan
# --------------------------------------------------------------------------- #


def uji_akar_menyatukan_bentuk_berimbuhan():
    assert dedup.akar("pembukaan") == dedup.akar("buka") == "buka"
    assert dedup.akar("penggunaan") == dedup.akar("guna") == "guna"


def uji_akar_tidak_menggerus_kata_pendek():
    """Sisa kata dijaga minimal empat huruf; tanpa itu "kereta" jadi "eta" dan
    "sesuai" jadi "suai" — dua-duanya menautkan berita yang tidak berhubungan."""
    for k in ("kereta", "menteri", "dividen", "beras", "seluruh"):
        assert len(dedup.akar(k)) >= 4, k


def uji_akar_boleh_menghasilkan_bukan_kata():
    """Pemenggalnya kasar dengan sengaja. Yang dibutuhkan konsistensi, bukan
    kebenaran linguistik — asal dua judul dipenggal jadi bentuk yang sama."""
    assert dedup.akar("meningkat") == dedup.akar("peningkatan")


# --------------------------------------------------------------------------- #
# jalan kedua: yang harus tergabung
# --------------------------------------------------------------------------- #


def uji_judul_ditulis_ulang_total_tetap_tergabung():
    """Pasangan nyata dari edisi 10 Sep 2026 yang lolos dan memicu perbaikan
    ini. Jaccard-nya 0,29 — di bawah ambang 0,42 — karena dua redaksi menulis
    peristiwa yang sama dengan hampir semua kata berbeda."""
    a = "Purbaya Buka Peluang APBN Biayai Saldo Rekening Masyarakat Rp50 Ribu"
    b = "Menteri Keuangan Jelaskan Penggunaan APBN untuk Pembukaan Rekening Masyarakat"
    judul = [a, b] + pengisi(60)
    assert dedup.jaccard(dedup.token(a), dedup.token(b)) < dedup.AMBANG
    assert segrup(judul, 0, 1)


def uji_tumpang_tidak_menghukum_beda_panjang():
    """Inilah bedanya dari Jaccard: judul pendek yang seluruhnya termuat di
    judul panjang harus tetap terhitung mirip."""
    a = dedup.token("Bank Kasikorn BMAS Gelar Rights Issue")
    b = dedup.token(
        "Rights Issue Bank Kasikorn Indonesia BMAS Tawarkan 2,87 Miliar Saham "
        "Baru kepada Pemegang Saham Lama"
    )
    assert dedup.tumpang(a, b) > dedup.jaccard(a, b)


# --------------------------------------------------------------------------- #
# jalan kedua: yang TIDAK boleh tergabung
# --------------------------------------------------------------------------- #


def mirip(a: str, b: str, df: int) -> bool:
    """Jalankan aturannya langsung dengan kelangkaan yang ditentukan di sini.

    Lewat `kelompokkan` batas ini sulit diuji: judul pengisi yang membuat sebuah
    kata jadi umum ikut mirip dengan judul yang diuji, lalu keduanya tergabung
    lewat jalan pertama — dan ujinya lulus atau gagal karena alasan yang bukan
    yang dimaksud.
    """
    ta, tb = dedup.token(a), dedup.token(b)
    muncul = Counter({k: df for k in ta | tb})
    return dedup._mirip(ta, tb, dedup.AMBANG, muncul, batas_langka=10)


def uji_irisan_kata_umum_tidak_menggabungkan():
    """Empat kata bersama pun tidak cukup kalau kata-katanya ada di mana-mana.
    Inilah yang membedakan aturan kedua dari sekadar menurunkan ambang: yang
    dituntut bukan irisan yang besar, melainkan irisan yang **langka**."""
    a = "Pemerintah DPR bahas anggaran pendidikan tinggi vokasi"
    b = "Pemerintah DPR bahas anggaran kesehatan daerah terpencil"
    # Prasyarat: keduanya memang tidak lolos jalan pertama, dan tumpangnya
    # memenuhi syarat jalan kedua. Yang menahannya harus semata kelangkaan.
    assert dedup.jaccard(dedup.token(a), dedup.token(b)) < dedup.AMBANG
    assert dedup.tumpang(dedup.token(a), dedup.token(b)) >= dedup.MIN_TUMPANG

    assert not mirip(a, b, df=40)   # kata umum -> tidak cukup jadi bukti
    assert mirip(a, b, df=3)        # kata yang sama, tapi langka -> cukup


def uji_laporan_pasar_sepola_tidak_tergabung():
    """IHSG dan rupiah sama-sama dilaporkan tiap sore dengan pola kalimat yang
    sama. Kelangkaan tidak menyaringnya — pada data 9 Sep "anjak" dan "sore"
    masing-masing cuma muncul di 2 judul, lebih langka daripada kata yang benar.
    Yang menyaringnya STOPWORD: kata-kata itu menandai kapan dan berapa, bukan
    peristiwa apa."""
    a = "IHSG Menanjak 1,01 Persen ke Level 6.686 Sore Ini"
    b = "Rupiah Menanjak ke Level Rp17.632 per Dolar AS Sore Ini"
    judul = [a, b] + pengisi(60)
    assert not segrup(judul, 0, 1)


def uji_stopword_diperiksa_setelah_pemenggalan():
    """"menanjak" bukan stopword, akarnya "anjak" ada di daftar. Tanpa
    pemeriksaan kedua ia lolos dan uji di atas kembali gagal."""
    assert "anjak" not in dedup.token("Rupiah Menanjak Sore Ini di Pasar Spot")


# --------------------------------------------------------------------------- #
# kelangkaan dihitung dari korpus hari itu
# --------------------------------------------------------------------------- #


def uji_kata_berhenti_langka_saat_jadi_ramai():
    """"krakatau" langka di hari biasa dan jadi kata umum pada hari gunungnya
    meletus — dan justru pada hari itu ia berhenti membedakan satu berita dari
    yang lain. Karena itu kelangkaan dihitung dari korpusnya sendiri, bukan dari
    daftar tetap."""
    a = "Anak Krakatau erupsi lagi status siaga"
    b = "Anak Krakatau erupsi warga diminta waspada"
    assert dedup.jaccard(dedup.token(a), dedup.token(b)) < dedup.AMBANG

    # Sepi: cuma dua berita ini yang menyebut Krakatau, jadi tiga kata bersama
    # itu langka dan menjadi bukti.
    assert segrup([a, b] + pengisi(60), 0, 1)

    # Ramai: puluhan berita menyebutnya. Kata yang sama, korpus berbeda, dan
    # jawabannya berbalik — persis yang dimaksud "kelangkaan dihitung dari
    # korpus hari itu".
    ramai = [
        f"Anak Krakatau erupsi disebut di laporan nomor {i} soal urusan lain"
        for i in range(40)
    ]
    assert not segrup([a, b] + ramai + pengisi(40), 0, 1)


def uji_kelompok_tidak_meledak():
    """Union-find merantai: A~B dan B~C menyatukan ketiganya. Aturan kedua
    menambah tepi, jadi risikonya satu kelompok raksasa menelan halaman. Diukur
    ke data nyata 10 Sep, kelompok terbesar 27 dari 1.121 artikel — di sini
    dijaga jauh lebih longgar, yang ditolak cuma keruntuhan total."""
    judul = pengisi(200)
    kel = dedup.kelompokkan(judul)
    assert max(len(g) for g in kel) < len(judul) // 4
