"""Uji `inti/ai.py` dan bagian AI di `alur/edisi.py`. Tanpa jaringan.

Judul-judul di sini diambil dari feed sungguhan 8–11 Sep 2026, bukan dikarang:
yang diuji adalah kasus yang memang muncul, termasuk sampah yang ikut terjaring.
"""

from datetime import date, datetime

import pytest

from alur import berita, edisi
from inti import ai, penyimpanan
from inti.penyimpanan import Artikel


@pytest.fixture
def con(tmp_path):
    c = penyimpanan.buka(tmp_path / "uji.duckdb")
    yield c
    c.close()


def peristiwa(judul, ringkasan=None, kategori="makro", domain="a.test"):
    return edisi.Peristiwa(
        judul=judul, url="u1", domain=domain, ringkasan=ringkasan,
        waktu_terbit=datetime(2026, 9, 8, 10, 0), kategori=kategori,
        jumlah_media=1, bobot=1.0,
    )


def periksa(judul, ringkasan=None, domain="a.test") -> ai.Klasifikasi:
    return ai.periksa(peristiwa(judul, ringkasan, domain=domain))


def artikel(judul, domain, jam_utc, kategori="makro", bahasa=None):
    return Artikel(
        artikel_id=f"{domain}:{judul}"[:60],
        url=f"https://{domain}/{abs(hash(judul)) % 99999}",
        domain=domain, judul=judul, ringkasan=None,
        waktu_terbit=datetime(2026, 9, 8, jam_utc, 0),
        waktu_fetch=datetime(2026, 9, 9, 0, 0),
        feed=domain, kategori=kategori, bahasa=bahasa,
    )


def palsu(teks):
    return {t: f"[id] {t}" for t in teks}


# --------------------------------------------------------------------------- #
# klasifikasi
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("judul", [
    "OpenAI Klaim Pecahkan Masalah Matematika yang tidak Terpecahkan Selama 90 Tahun dalam 88 Jam",
    "MGLV Resmi Jadi Pemain AI Data Center",
    "AS Menuduh Alibaba dan DeepSeek Mengekstraksi Model AI Miliknya",
    "Web Asisten Belajar Ber-AI Buatan Peneliti UPI",
    "Perkembangan Kecerdasan Buatan Mengubah Kebutuhan Pengguna Laptop Gaming",
    "Anthropic Says It Blocked Possible Efforts to Build Biological Weapons",
    "A.I. Could Possibly End Humanity. How Are Humans Supposed to Process That?",
    "Jensen Huang explains why Nvidia will grow an astounding 70% next year",
    "GPT-6 Astra: A new generation of intelligence",
])
def uji_berita_ai_dikenali(judul):
    assert periksa(judul).ai


@pytest.mark.parametrize("judul", [
    # "Ai" nama orang, bukan AI — pencocokannya peka huruf besar.
    "Nenek Ai Hanyut Terbawa Arus Sungai Cimanuk",
    # "chip" bukan penanda: saham blue chip dan perang dagang semikonduktor.
    "Saham Blue Chip Mulai Bagi Dividen Interim Tahun Buku 2026, Cek yang Layak Beli",
    "Perang Dagang Memanas, China Gebuk Tarif Antidumping Bahan Semikonduktor Jepang",
    # Dari feed AI, tapi bukan berita AI.
    "Mark Wahlberg is coming to TechCrunch Disrupt 2026, and he wants to talk about your work",
    "World's largest contract chipmaker TSMC sees August revenue surge over 53% to record high",
    # Halaman profil "AI at Meta" — nama penerbitnya sudah dipotong dari judul.
    "Peta Ruang Aktivitas",
    # Kata di dalam kata lain tidak boleh cocok.
    "RAIN Harga Emas Hari Ini",
])
def uji_bukan_berita_ai(judul):
    assert not periksa(judul).ai


def uji_nama_rancu_butuh_pendamping():
    assert not periksa("Claude Makelele Ditunjuk Jadi Pelatih Baru").ai
    assert not periksa("Ramalan Gemini Hari Ini").ai
    assert periksa("Governments are turning to Claude to automate spying",
                   "Anthropic's AI model is being used by agencies ...").ai


@pytest.mark.parametrize("judul, domain", [
    ("Prompt Tren Foto Era 80-an di ChatGPT Viral di Medsos, Bisa Dicoba", "a.test"),
    ("Cara Membuat Foto 80-an di ChatGPT Tanpa Prompt", "a.test"),
    ("10 contoh prompt AI untuk buat poster bertema HUT ke-81 RI", "a.test"),
    ("Polres Karanganyar Ajak 310 Pelajar Kebakkramat Melek AI dan Bijak Bermedia Digital", "a.test"),
    ("Diskominfo SP Kota Cilegon Imbau Masyarakat Bijak Gunakan AI", "a.test"),
    ("Huawei Luncurkan MatePad Air Tablet Tipis Berfitur AI", "a.test"),
    ("Opinion | Pause AI for Humanity's Sake", "wsj.com"),
    # Situs yang isinya bukan berita.
    ("Gubernur Koster: AI Tak Boleh Menggantikan Kecerdasan Budaya", "baliprov.go.id"),
    ("Kapolres Demak Ingatkan Pelajar Kritis Hadapi Konten AI", "demakkab.go.id"),
    ("Guru Besar UMS Soroti Etika Penggunaan AI dalam Penalaran Hukum", "news.ums.ac.id"),
    ("Kebocoran Data Perusahaan Bisa Berasal dari Tools AI yang Digunakan?", "kompasiana.com"),
    ("Averondale Capital Hadirkan Nusantara AI Capital Fund", "einnews.com"),
    # Judul yang dipotong penerbitnya.
    ("Startup AI China JoyIn tuduh OpenAI tiru teknol...", "pluang.com"),
])
def uji_tips_seremonial_dan_bukan_berita_dibuang(judul, domain):
    k = periksa(judul, domain=domain)
    assert k.ai and k.buang


@pytest.mark.parametrize("judul, topik", [
    ("Wamenkomdigi jelaskan alasan regulasi AI dituangkan dalam perpres", "Regulasi & hukum"),
    ("Pemerintah kaji aturan konten buatan AI dalam revisi UU Hak Cipta", "Regulasi & hukum"),
    ("Anthropic says it blocked possible attempts to use AI to develop bioweapons",
     "Keamanan & risiko"),
    ("Qualcomm strikes AI chip deal with Amazon, offers right to buy about $4 billion in stock",
     "Chip & infrastruktur"),
    ("Cognition AI raises $2 billion at $48 billion valuation", "Pendanaan & bisnis"),
    ("Meta Rilis AI Agent Muse, Bisa Belanja dan Isi Form Sendiri", "Model & produk"),
    ("Meta dan Kemendag Latih 200 UMKM Manfaatkan AI untuk Tembus Pasar Ekspor",
     "Kerja & adopsi"),
])
def uji_subtopik(judul, topik):
    assert periksa(judul).topik == topik


# --------------------------------------------------------------------------- #
# edisi
# --------------------------------------------------------------------------- #


def uji_berita_ai_pindah_dari_makro_politik_global(con):
    penyimpanan.simpan_artikel(con, [
        artikel("Meta rilis Muse, agen AI yang bisa kirim email hingga berbelanja",
                "makro.test", 10),
        artikel("AI Mengubah Wajah Industri, Apakah Kita Siap?", "politik.test", 11,
                kategori="politik"),
        artikel("Cognition AI raises $2 billion at $48 billion valuation", "global.test", 12,
                kategori="global"),
        artikel("Penjualan mobil domestik melambat kuartal lalu", "mobil.test", 13),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert sorted(p.domain for p in bagian["ai"]) == ["global.test", "makro.test", "politik.test"]
    assert [p.domain for p in bagian["makro"]] == ["mobil.test"]


def uji_berita_saham_ai_tetap_di_pasar(con):
    """Analisis saham milik Pasar, sama seperti di bagian Perpajakan."""
    penyimpanan.simpan_artikel(con, [
        artikel("Boy Thohir Terafiliasi Emiten MGLV di Sektor Data Center dan AI, Saham Meroket",
                "pasar.test", 10, kategori="pasar"),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert not bagian["ai"]
    assert [p.domain for p in bagian["pasar"]] == ["pasar.test"]


def uji_berita_pajak_ai_tetap_di_perpajakan(con):
    penyimpanan.simpan_artikel(con, [
        artikel("DJP Kenakan PPN atas Langganan Layanan AI Luar Negeri", "a.test", 10),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert [p.domain for p in bagian["pajak"]] == ["a.test"]
    assert not bagian["ai"]


def uji_feed_ai_yang_bukan_ai_dibuang_bukan_pindah(con):
    """TechCrunch AI ikut memuat acara Apple; itu tidak boleh jatuh ke bagian
    lain, apalagi ke Makro."""
    penyimpanan.simpan_artikel(con, [
        artikel("Everything Apple announced at its fall iPhone event", "techcrunch.com", 10,
                kategori="ai", bahasa="en"),
        artikel("OpenAI puts Pro subscriptions on hold due to Astra demand", "techcrunch.com",
                11, kategori="ai", bahasa="en"),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    semua = [p.judul for v in bagian.values() for p in v]
    assert semua == ["OpenAI puts Pro subscriptions on hold due to Astra demand"]


def uji_prompt_foto_tidak_tampil(con):
    penyimpanan.simpan_artikel(con, [
        artikel("Prompt Tren Foto Era 80-an di ChatGPT Viral di Medsos, Bisa Dicoba",
                "tribun.test", 10, kategori="ai"),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert not any(bagian.values())


def uji_liputan_luas_ai_tidak_mengambil_blok_utama(con):
    """Feed Google News AI menumpuk puluhan redaksi di satu cerita AI. Liputan
    seluas itu bukti perhatian media AI, bukan dampak ke pasar."""
    penyimpanan.simpan_artikel(con, [
        artikel("Anthropic researcher quits, calls AI an existential threat to humanity",
                f"media{i}.test", 10, kategori="ai", bahasa="en")
        for i in range(6)
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert "utama" not in bagian
    p = bagian["ai"][0]
    assert p.jumlah_media == 6 and p.dampak == 2


def uji_judul_inggris_berbeda_redaksi_digabung(con):
    """Kasus nyata 11 Sep: dua judul satu peristiwa, Jaccard 0,27 — lolos
    dedup umum, tampil berdampingan di bagian AI."""
    penyimpanan.simpan_artikel(con, [
        artikel("Anthropic Says It Blocked Possible Efforts to Build Biological Weapons",
                "nytimes.com", 10, kategori="ai", bahasa="en"),
        artikel("Anthropic says it blocked possible attempts to use AI to develop bioweapons",
                "cnn.com", 11, kategori="ai", bahasa="en"),
        artikel("Anthropic details distillation campaigns from Alibaba, Moonshot AI, and DeepSeek",
                "techcrunch.com", 12, kategori="ai", bahasa="en"),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert len(bagian["ai"]) == 2
    gabungan = next(p for p in bagian["ai"] if p.jumlah_media == 2)
    assert {gabungan.domain, *(d for d, _ in gabungan.juga)} == {"nytimes.com", "cnn.com"}


def uji_gabung_ai_tidak_menyentuh_bagian_lain(con):
    """Ambang longgar hanya aman di kumpulan kecil satu tema."""
    penyimpanan.simpan_artikel(con, [
        artikel("AI chip startup Positron's valuation skyrockets in latest funding round",
                "reuters.com", 10, kategori="ai", bahasa="en"),
        artikel("AI research startup Listen Labs scrubbed a $1.5B funding round for Salesforce talks",
                "techcrunch.com", 11, kategori="ai", bahasa="en"),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9))
    assert len(bagian["ai"]) == 2


def uji_yang_diterjemahkan_menurut_bahasa_bukan_bagian(con):
    penyimpanan.simpan_artikel(con, [
        artikel("OpenAI puts Pro subscriptions on hold due to Astra demand", "techcrunch.com",
                10, kategori="ai", bahasa="en"),
        artikel("OpenAI Klaim Pecahkan Teka-teki Matematika Berusia 90 Tahun", "detik.test",
                11, kategori="ai"),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9), penerjemah=palsu)
    judul = sorted(p.judul for p in bagian["ai"])
    assert judul == [
        "OpenAI Klaim Pecahkan Teka-teki Matematika Berusia 90 Tahun",
        "[id] OpenAI puts Pro subscriptions on hold due to Astra demand",
    ]


def uji_baris_lama_tanpa_bahasa_global_tetap_diterjemahkan(con):
    """Basis data di cache Actions berisi ribuan baris dari sebelum kolom
    `bahasa` ada. Global di antaranya harus tetap diterjemahkan."""
    penyimpanan.simpan_artikel(con, [
        artikel("Oil prices slip on demand worries", "cnbc.com", 10, kategori="global"),
    ])
    con.execute("UPDATE artikel SET bahasa = NULL")
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9), penerjemah=palsu)
    assert bagian["global"][0].judul == "[id] Oil prices slip on demand worries"


def uji_bahasa_bawaan_dari_kategori_feed():
    entri = {"link": "https://x.test/a", "title": "Oil falls"}
    bawaan = berita.ke_artikel(entri, {"nama": "x", "kategori": "global"}, datetime(2026, 9, 9))
    ai_id = berita.ke_artikel(entri, {"nama": "x", "kategori": "ai"}, datetime(2026, 9, 9))
    ai_en = berita.ke_artikel(entri, {"nama": "x", "kategori": "ai", "bahasa": "en"},
                              datetime(2026, 9, 9))
    assert (bawaan.bahasa, ai_id.bahasa, ai_en.bahasa) == ("en", "id", "en")


def uji_halaman_memuat_bagian_ai(con):
    penyimpanan.simpan_artikel(con, [
        artikel("Meta rilis Muse, agen AI yang bisa kirim email", "a.test", 10),
    ])
    html, _, _ = edisi.bangun(con, date(2026, 9, 9))
    assert 'id="ai"' in html and 'href="#ai"' in html
    assert "var(--ai)" in html
