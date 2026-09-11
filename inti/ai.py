"""
ai.py — kenali berita kecerdasan buatan (AI) dan beri subtopiknya.

Bagian "AI" di halaman pagi disusun seperti Perpajakan (inti/pajak.py): dari
**isi**, bukan asal feed. Berita AI sudah mengalir lewat feed yang ada — pada
8–9 Sep 2026 ada ~45 judul AI tersebar di Makro, Politik, dan Global (Reuters,
CNBC, BBC) — ditambah lima feed khusus AI (sumber/feed.toml, kategori `ai`).

Bedanya dengan pajak: feed khusus AI **tidak** dipercaya utuh. DJP hanya
menerbitkan urusan pajak, tapi TechCrunch AI ikut memuat acara Apple, dan
Google News "AI" ikut memuat halaman profil "AI at Meta" dan sosialisasi polres.
Jadi item dari feed `ai` juga harus lolos pemeriksaan judul; yang tidak lolos
dibuang, tidak jatuh ke bagian lain.

Tiga hal yang dinilai, semuanya daftar frasa yang bisa dibaca dan diubah dalam
satu menit — tanpa jaringan, tanpa biaya:

1. **Apakah ini berita AI** — dari judul saja, dengan alasan yang sama seperti
   pajak.py: ringkasan menyebut AI sambil lalu jauh lebih sering daripada judul.
2. **Apakah ini tips, tren, atau seremonial** — prompt foto viral, "cara
   membuat", sosialisasi polres dan pemda, spesifikasi gawai. Dibuang.
3. **Subtopik** (Regulasi, Keamanan, Chip, Pendanaan, Model, Kerja) yang tampil
   sebagai `alasan`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Kategori feed yang isinya boleh dipindah ke bagian AI. `pasar` tidak ikut,
# sama seperti di pajak.py: "Boy Thohir Terafiliasi Emiten MGLV di Sektor Data
# Center dan AI, Saham Meroket" adalah berita saham, dan pembaca bagian Pasar
# yang kehilangan dia. Beda dengan pajak, `global` ikut: berita AI dunia justru
# isi utama bagian ini, dan tanpa Global yang tersisa hanya berita AI lokal.
DAPAT_PINDAH = {"makro", "politik", "global"}

# "AI" dicocokkan di judul **asli**, peka huruf besar: "Ai" juga nama orang
# (Sunda, Jepang), dan judul berita kriminal atau bencana dari feed Politik
# menyebutnya. Batasnya huruf, bukan kata, supaya "Ber-AI" dan "AI-nya" cocok
# tapi "OpenAI" dan "RAIN" tidak — OpenAI sudah punya penandanya sendiri.
AI_KAPITAL = re.compile(r"(?<![A-Za-z])A\.?I\.?(?![A-Za-z])")

# Penanda lain, dicocokkan per kata utuh setelah huruf kecil (lihat `_teks`).
PENANDA: tuple[str, ...] = (
    "kecerdasan buatan", "kecerdasan artifisial", "artificial intelligence",
    "generative ai", "genai", "chatgpt", "gpt", "openai", "anthropic",
    "deepseek", "google gemini", "copilot", "grok", "xai", "llm", "llms",
    "large language model", "machine learning", "deep learning", "chatbot",
    "superintelligence", "humanoid", "nvidia",
    # Tokoh yang namanya hampir selalu berarti berita AI.
    "sam altman", "jensen huang", "dario amodei", "demis hassabis",
)

# Nama produk yang juga nama lain: Claude Makelele, zodiak Gemini, bursa kripto
# Gemini, hewan llama. Dihitung hanya kalau judul atau ringkasannya juga
# menyebut salah satu pendampingnya.
PENANDA_RANCU: dict[str, tuple[str, ...]] = {
    "claude": ("anthropic", "ai", "chatbot", "model"),
    "gemini": ("google", "ai", "chatbot", "model"),
    "llama": ("meta", "ai", "model"),
}

# Tips, tren, promosi, seremonial, dan ulasan gawai. Khusus bagian ini — "harga"
# atau "pelatihan" di bagian lain bisa berita sungguhan.
PENANDA_BUANG: tuple[str, ...] = (
    # Tren dan panduan. Pada 11 Sep, tren "foto era 80-an di ChatGPT" mengisi
    # enam item Google News AI sendirian.
    "prompt", "tren foto", "foto jadul", "edit foto", "cara membuat",
    "cara pakai", "cara menggunakan", "cara bikin", "begini cara", "simak cara",
    "trik", "tutorial", "tips", "rekomendasi",
    # Sosialisasi, pelatihan, dan acara.
    "sosialisasi", "seminar", "webinar", "workshop", "pelatihan", "konferensi",
    "expo", "pameran", "lomba", "kompetisi", "melek", "bijak", "imbau",
    "polres", "polsek", "kapolres", "diskominfo",
    # Ulasan dan peluncuran gawai yang kebetulan "berfitur AI".
    "spesifikasi", "berapa harganya", "laptop", "tablet", "smartwatch",
    # Kolom pendapat.
    "opini", "opinion", "kolom",
)

# Situs yang isinya bukan berita: blog pengguna, ensiklopedia, situs asing yang
# menerjemahkan berita negaranya sendiri ke bahasa Indonesia, dan distributor
# siaran pers berbayar — "Averondale Capital Hadirkan Nusantara AI Capital
# Fund" dari einnews.com sempat memimpin bagian ini pada 11 Sep.
DOMAIN_BUANG = {
    "kompasiana.com", "vietnam.vn", "britannica.com",
    "einnews.com", "prnewswire.com", "globenewswire.com", "businesswire.com",
    # Halaman acara, bukan berita ("GTC - NVIDIA"). Blog-nya, blogs.nvidia.com,
    # domain lain dan tetap masuk.
    "nvidia.com",
}

# Siaran pers pemda, polisi, kampus, dan sekolah soal AI hampir selalu
# sosialisasi ("Gubernur: AI Tak Boleh Menggantikan Kecerdasan Budaya"). Sama
# seperti pajak.DOMAIN_PEMDA, tanpa titik di depan: "baliprov.go.id".
AKHIRAN_DOMAIN_BUANG = (
    "prov.go.id", "kab.go.id", "kota.go.id", "polri.go.id", ".ac.id", ".sch.id",
)

# Subtopik, diperiksa berurutan — yang pertama cocok menang, jadi yang paling
# spesifik di atas: "Nvidia shares fall" adalah berita chip sebelum berita
# saham, dan "OpenAI digugat soal hak cipta" berita hukum sebelum berita model.
TOPIK: dict[str, tuple[str, ...]] = {
    "Regulasi & hukum": (
        "regulasi", "aturan", "perpres", "uu", "ruu", "undang undang",
        "hak cipta", "gugatan", "digugat", "pengadilan", "komdigi",
        "regulation", "regulators", "law", "lawsuit", "sued", "court",
        "copyright", "congress", "senate", "white house", "gedung putih",
        "ai act", "ban", "larang",
    ),
    "Keamanan & risiko": (
        "keamanan", "risiko", "bahaya", "ancaman", "musnahkan", "kepunahan",
        "senjata", "penyalahgunaan", "deepfake", "hoaks", "siber", "kebocoran",
        "safety", "risk", "risks", "threat", "extinction", "bioweapon",
        "bioweapons", "weapons", "misuse", "cyber", "espionage", "distillation",
        "distilasi", "tiru", "kill", "doom",
    ),
    "Chip & infrastruktur": (
        "nvidia", "chip", "chips", "gpu", "gpus", "semikonduktor",
        "semiconductor", "tsmc", "data center", "data centers", "data centre",
        "pusat data", "infrastruktur", "infrastructure", "komputasi", "compute",
    ),
    "Pendanaan & bisnis": (
        "pendanaan", "valuasi", "investasi", "akuisisi", "merger", "ipo",
        "rights issue", "saham", "laba", "pendapatan", "kerja sama",
        "funding", "raises", "valuation", "invest", "investment", "acquire",
        "acquisition", "stock", "shares", "earnings", "revenue", "deal",
    ),
    "Model & produk": (
        "model", "rilis", "luncurkan", "meluncurkan", "fitur", "aplikasi",
        "agen ai", "agentic", "launch", "launches", "release", "releases",
        "unveils", "introducing", "agent", "agents", "app", "gpt", "chatgpt",
        "claude", "gemini",
    ),
    "Kerja & adopsi": (
        "pekerjaan", "karyawan", "phk", "tenaga kerja", "adopsi", "umkm",
        "pendidikan", "belajar", "jobs", "workers", "layoffs", "adoption",
    ),
}


@dataclass(slots=True, frozen=True)
class Klasifikasi:
    ai: bool            # berita AI menurut judulnya
    buang: bool         # tips/tren/seremonial/bukan berita — tidak ditampilkan
    topik: str | None   # label subtopik untuk `alasan`


def periksa(p) -> Klasifikasi:
    """Nilai satu peristiwa. Murni fungsi dari judul, ringkasan, dan domainnya.

    Masuk-tidaknya dan dibuang-tidaknya diputuskan dari judul, seperti di
    pajak.py. Ringkasan hanya dipakai untuk pendamping kata rancu dan label
    subtopik.
    """
    judul = _teks(p.judul)
    semua = _teks(f"{p.judul} {p.ringkasan or ''}")

    ai = bool(AI_KAPITAL.search(p.judul)) or _ada(judul, PENANDA) or any(
        f" {kata} " in judul and _ada(semua, pendamping)
        for kata, pendamping in PENANDA_RANCU.items()
    )
    buang = (
        _ada(judul, PENANDA_BUANG)
        or p.domain in DOMAIN_BUANG
        or p.domain.endswith(AKHIRAN_DOMAIN_BUANG)
        # Judul yang dipotong penerbitnya ("Startup AI China JoyIn tuduh
        # OpenAI tiru teknol...") — terjemahan mesin, dan tidak bisa dibaca.
        or p.judul.rstrip().endswith(("...", "…"))
    )
    topik = next((label for label, frasa in TOPIK.items() if _ada(semua, frasa)), None)
    return Klasifikasi(ai=ai, buang=buang, topik=topik)


def _ada(teks: str, frasa: tuple[str, ...]) -> bool:
    return any(f" {f} " in teks for f in frasa)


def _teks(mentah: str) -> str:
    """Sama dengan pajak._teks: huruf kecil, tanda baca jadi spasi, diapit
    spasi — supaya "GPT-6" cocok dengan "gpt" dan " ai " tidak cocok di dalam
    "rain"."""
    bersih = "".join(c if c.isalnum() else " " for c in mentah.lower())
    return f" {' '.join(bersih.split())} "
