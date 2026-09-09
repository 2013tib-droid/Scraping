# Keputusan Tooling

Hasil evaluasi tiga referensi eksternal (2026-09-09). Dokumen ini **tunduk pada**
`ARSITEKTUR.md` — kalau ada yang bertabrakan, `ARSITEKTUR.md` yang menang.

Yang dievaluasi:

| Referensi | Lapisan | Putusan |
|---|---|---|
| [Scrapling](https://github.com/D4Vinci/Scrapling) — 79.4k ★, BSD-3 | fetch + parse | **Adopsi sebagian** |
| [ScrapeGraphAI](https://scrapegraphai.com/) — 30.7k ★, MIT + SaaS | ekstraksi via LLM | **Tolak** untuk pipeline |
| [agent-reach](https://github.com/Panniantong/agent-reach) — 78.9k ★, MIT | akses platform untuk agent | **Tolak**, ambil idenya |

---

## 1. Scrapling — yang diambil dan yang tidak

Scrapling menyelesaikan lapisan terbawah (`ARSITEKTUR.md` §4: HTML statis, SPA,
endpoint tersembunyi). Sebagian fiturnya mengotomasi prinsip yang sudah ditulis
di sini; sebagian lagi melanggarnya. Pemisahannya harus eksplisit, bukan
diserahkan ke kebiasaan saat coding.

### Yang diambil

| Fitur | Menggantikan / melengkapi | Ref |
|---|---|---|
| `capture_xhr` | Kerja manual DevTools → Network → XHR | §2 |
| Development Mode (cache respons ke disk, replay) | Harness fixture buatan sendiri | §13 |
| Adaptive selector (relokasi elemen setelah layout berubah) | Penawar selector rapuh | §15 #5 |
| `page.markdown()` — HTML → Markdown tanpa LLM | Pembersih teks berita fase 3 | §14 |
| `robots_txt_obey` (`Disallow`, `Crawl-delay`, `Request-rate`) | `urllib.robotparser` manual | §11 |
| AutoThrottle (melambat sendiri saat kena rate-limit / `Retry-After`) | Rate limit per domain | §9 #2 |

`capture_xhr` yang paling bernilai. §2 menyuruh cek tab Network sebelum menulis
parser HTML; fitur ini melakukannya secara terprogram — beri pola URL, semua
respons XHR yang dipanggil halaman dikumpulkan sebagai objek respons. Target
pindah dari kolom Playwright ke kolom httpx tanpa reverse-engineering manual.
Kandidat pertama: IDX dan portal Kemenkeu (`SUMBER-DATA.md` §A, keduanya ⚠️).

### Yang tidak diambil, dan kenapa

Jualan utama Scrapling adalah bypass Cloudflare Turnstile, impersonasi TLS
fingerprint, rotasi proxy, dan DNS-over-HTTPS untuk menyembunyikan proxy.
`ARSITEKTUR.md` §11 sudah memutuskan itu di luar batas:

> kalau perlu menyamarkan diri agar tidak ketahuan — proxy rotasi, pemalsuan
> fingerprint, penyelesaian CAPTCHA — itu tanda batas sudah dilewati.

Keputusan itu tidak berubah karena ada library yang memudahkannya.

### Batas pemasangan

Batas ini bisa ditegakkan di level dependensi, bukan sekadar disiplin diri.
Dependensi inti Scrapling ringan dan tidak memuat satu pun komponen stealth:

```
lxml, cssselect, orjson, tld, w3lib, typing_extensions
```

Browser dan anti-bot baru masuk lewat extra `[fetchers]`. Karena itu:

```toml
# pyproject.toml
dependencies = [
    "scrapling==<pin>",     # core parser + spider. TANPA extra.
]
# JANGAN: scrapling[fetchers] — menarik playwright, camoufox, curl_cffi
```

Konsekuensi yang harus diterima: `capture_xhr` dan Development Mode butuh
fetcher berbasis browser. Keduanya dipakai sebagai **alat eksplorasi sekali
jalan** saat menambah sumber baru — dipasang di environment lokal, tidak masuk
`pyproject.toml` produksi dan tidak pernah dijalankan di GitHub Actions. Hasilnya
(URL endpoint XHR yang ditemukan, fixture yang tersimpan) yang masuk repo, bukan
tool-nya.

### Yang tidak berubah karena ini

Benchmark di README Scrapling mengklaim `selectolax` ~99x lebih lambat dari lxml.
Angka itu tidak masuk akal untuk parser berbasis lexbor — hampir pasti artefak
cara traversal di skrip benchmark mereka. Terlepas dari itu, di volume
ratusan–ribuan dokumen/hari selisih parsing milidetik tenggelam oleh waktu
jaringan. **Pilihan `selectolax` di §1 tetap.** Scrapling masuk sebagai pelengkap
untuk kasus sulit, bukan pengganti jalur utama `httpx` + `selectolax`.

### Risiko

Proyek satu maintainer, dan README-nya dipenuhi sponsor penyedia proxy
residensial serta API bypass anti-bot — arah proyeknya jelas menjauh dari batas
di §11. Biaya keluar rendah karena core-nya lxml, tapi jangan sampai ada modul
`sumber/` yang bergantung pada API khas Scrapling di jalur produksi.

---

## 2. ScrapeGraphAI — ditolak untuk pipeline

Dicatat di sini supaya tidak dievaluasi ulang setiap kali muncul di timeline.

**Biaya.** Endpoint Extract 5 kredit; kredit termurah $3–4/1k, jadi ~$0,02 per
halaman. Di volume §0 (ratusan–ribuan dokumen/hari), 1.000 dok/hari ≈ **$600 per
bulan**. Paket Growth $100/bln hanya menutup ~667 ekstraksi/hari. Sumber utama
di `SUMBER-DATA.md` gratis dan ber-API. Ini anti-pattern #8, dibayar tunai.

**Nondeterminisme merusak §9 — ini alasan yang lebih penting daripada biaya.**
Seluruh bab "deteksi kerusakan diam-diam" bertumpu pada: parser gagal → 0 baris →
alarm. Ekstraktor LLM tidak pernah mengembalikan 0 baris. Saat BPS ganti layout,
dia mengembalikan angka yang bentuknya masuk akal tapi salah. Mode gagal pindah
dari "terlihat" ke "diam" — arah yang berlawanan persis dengan §9.

**Sudah ditutup §10.** Jalur bertingkat (saring → lexicon → IndoBERT → LLM hanya
untuk ekstraksi terstruktur yang sulit) sudah menempatkan LLM di posisi benar:
teks berita, bukan tabel angka yang punya API.

**Satu pengecualian:** versi OSS-nya, dijalankan lokal dengan Ollama, boleh
dipakai sebagai alat eksplorasi saat menghadapi sumber baru yang formatnya belum
dipahami. Tidak pernah di jalur produksi, tidak pernah versi SaaS-nya.

---

## 3. agent-reach — ditolak, dua idenya diambil

Ini capability layer untuk agent interaktif (Claude Code, Cursor), bukan library
untuk pipeline terjadwal. Platform yang dibukanya — Twitter, Reddit, Xiaohongshu,
Instagram — semuanya lewat cookie sesi login, wilayah yang §11 nyatakan jangan
disentuh ("jangan tembus paywall atau login"), dan `SUMBER-DATA.md` §C sudah
menunda media sosial. Cara pasangnya juga menyuruh agent mengeksekusi `install.md`
dari URL mentah; repo berumur ~7 bulan dengan 129 issue terbuka.

Tapi arsitekturnya konvergen dengan §4 dari arah berbeda, dan dua idenya layak
diambil tanpa memasang apa pun.

### 3.1 Backend berurut per sumber

Pola mereka: satu file per platform, isinya daftar backend berurut.

```
bilibili.py  → bili-cli ▸ OpenCLI ▸ search API   (yt-dlp pensiun, kena blokir)
```

Ganti metode akses = ubah urutan daftar, bukan tulis ulang modul. Ini §4 ("satu
modul per sumber, antarmuka sama") ditambah satu lapis.

Relevan langsung untuk BI, yang `SUMBER-DATA.md` §A catat tidak punya API
terpadu — kurs lewat web service, sisanya lewat XLSX rilis. Itu praktis sudah dua
backend untuk satu lembaga. Antarmuka `sumber/` diperluas jadi:

```python
class Sumber(Protocol):
    nama: str
    backends: list[Backend]      # berurut: utama dulu, cadangan sesudahnya
    def fetch(self) -> bytes: ...
    def parse(self, b: bytes) -> list[Record]: ...
```

Aturan yang mengikat: fallback **hanya** boleh antar-metode ke sumber resmi yang
sama (API → file rilis → halaman). Bukan jalan belakang untuk menembus blokir —
itu balik ke §11.

### 3.2 Perintah `doctor`

`agent-reach doctor` menguji tiap kanal secara nyata — bukan sekadar cek apakah
command-nya ada — lalu melaporkan mana yang jalan, backend mana yang sedang
dipakai, dan resep perbaikannya.

Padanannya di sini: `python -m alur.doctor`, menembak tiap sumber sekali dan
melaporkan status HTTP, backend yang menang, jumlah record, dan waktu sukses
terakhir dari tabel metrik §12. Dijalankan manual saat curiga, bukan terjadwal.

Ini melengkapi §12: dashboard menjawab "apa yang terjadi tiga minggu terakhir",
`doctor` menjawab "apa yang rusak sekarang, dan kenapa". Keduanya perlu — §9
sudah mencatat bahwa mode gagal paling mahal adalah yang diam.

Tambahan ke §13:

```
alur/
  harian.py  berita.py  backfill.py  doctor.py   <- baru
```

---

## 4. Yang tetap harus ditulis sendiri

Tidak ada dari ketiga referensi yang menyentuh bagian tersulit proyek ini:

- point-in-time / vintage tiga-tanggal (§5)
- parsing XLSX SEKI dan PDF OJK (`SUMBER-DATA.md` §A)
- `pandera` untuk assert nilai, `pydantic` untuk assert skema (§9)
- skema append-only, dedup via SHA-256 (§5, §6)

Ketiganya menyelesaikan masalah **"bagaimana mengambil halaman"** — sementara §2
menyatakan pengambilan halaman adalah pilihan terakhir, dan mayoritas sumber di
`SUMBER-DATA.md` (BPS WebAPI, CKAN, FRED, SDMX, RSS) tidak melewati jalur itu
sama sekali.

Kesimpulan operasionalnya: fase 1 tidak berubah sedikit pun karena evaluasi ini.
Scrapling baru relevan di fase 2–3, saat menghadapi IDX dan Kemenkeu.
