# Sistem Intelijen Data Makro–Mikro Indonesia

Dokumen keputusan arsitektur. Ditulis sebelum baris kode pertama supaya pilihan
teknis punya alasan, bukan warisan kebiasaan.

## 0. Asumsi

Sistem ini dipakai satu orang, untuk memberi **konteks makro/politik/sosial pada
keputusan pasar** (nyambung ke `Screening-Saham`, `IDX Screener`, `GOLD EA`).
Bukan produk multi-user, bukan platform berita. Konsekuensinya di seluruh dokumen:
pilih yang sederhana dan tahan ditinggal, bukan yang bisa di-scale ke 100 engineer.

Volume realistis: **ratusan–ribuan dokumen per hari**, bukan jutaan. Ini angka
yang menentukan hampir semua keputusan teknis di bawah.

Kalau asumsi ini salah (misal ternyata mau dijual sebagai layanan, atau butuh
data realtime tick-level), bagian 4, 7, dan 8 harus ditinjau ulang.

## 1. Ringkasan keputusan

| Aspek | Pilihan | Alasan singkat |
|---|---|---|
| Bahasa | **Python 3.12+** | Ekosistem data + sudah dipakai di repo lain se-Cowork OS |
| HTTP | `httpx` (async) | HTTP/2, timeout benar, async tanpa ganti library |
| Parsing HTML | `selectolax`, fallback `lxml` | Cepat; BS4 hanya kalau butuh selector aneh |
| Browser | `Playwright` — **pilihan terakhir** | ~20x lebih lambat, rapuh, mahal dirawat |
| Framework crawl | `Scrapy` hanya untuk crawl luas | Untuk ~50 sumber terjadwal, overkill |
| Penjadwalan | GitHub Actions cron → Prefect kalau ribet | Gratis, sudah familiar, log tersimpan |
| Penyimpanan | **Parquet + DuckDB** | Tanpa server, analitik cepat, satu file |
| Validasi | `pydantic` (bentuk) + `pandera` (nilai) | Gagal keras di batas, bukan di hilir |
| NLP berita | Lexicon → IndoBERT → LLM bertingkat | Biaya terkontrol, akurasi di tempat yang perlu |
| Notifikasi | Telegram bot (pola `IDX Screener`) | Sudah ada, tidak menambah stack |
| Keluaran harian | Halaman HTML statis; Telegram kirim link | Dibaca pagi hari — bukan PDF, alasannya di §16 |

## 2. Prinsip utama: scraping adalah pilihan terakhir

Ini bagian terpenting dari dokumen ini. Urutan yang benar:

```
API resmi  →  SDMX / open-data catalog  →  file rilis (xlsx/csv)
           →  RSS/Atom  →  endpoint JSON internal  →  parsing HTML  →  browser
```

Setiap langkah ke kanan berarti: lebih rapuh, lebih lambat, lebih sering rusak,
lebih berat secara hukum. Sebagian besar data makro Indonesia **sudah tersedia
tanpa scraping** — lihat `SUMBER-DATA.md`. Menulis scraper HTML untuk data yang
punya API adalah utang teknis yang dibayar ulang setiap kali situsnya ganti tema.

Trik operasional yang menghemat paling banyak waktu: sebelum menulis parser HTML,
buka DevTools → tab Network → filter XHR. Sebagian besar situs "dinamis" ternyata
memanggil endpoint JSON internal yang bisa dipanggil langsung. Itu memindahkan
target dari kolom "Playwright" ke kolom "httpx" — selisih besar dalam kecepatan
dan kerapuhan.

## 3. Bahasa pemrograman

**Python.** Alasan konkret, bukan preferensi:

1. Hilir sistem ini adalah analisis (pandas/polars, statsmodels, backtest). Kalau
   scraper ditulis di bahasa lain, ada batas serialisasi yang tidak perlu.
2. Repo lain di Cowork OS sudah Python. Satu bahasa = satu cara debug, tidak ada
   konteks-switch.
3. Library untuk kasus sulit (PDF bertabel, SDMX, feed) hampir semuanya matang di
   Python dan setengah jadi di tempat lain.

**Kapan Python salah:** kalau kebutuhannya berubah jadi crawl luas ribuan
halaman/menit dengan ribuan koneksi bersamaan — di situ Go (`colly`) menang telak
soal memori dan konkurensi. Itu bukan kasus di sini. Node/TypeScript hanya menang
kalau mayoritas target butuh browser sungguhan; sekali lagi, bukan kasus di sini.

Pakai `uv` untuk manajemen environment (jauh lebih cepat dari pip/venv) dan
**pin semua versi** — pelajaran yang sudah mahal dibayar di `Screening-Saham`:
dependensi `>=` bikin "jalan di lokal, rusak di CI" tidak bisa dibedakan dari
perubahan perilaku sumber.

## 4. Pohon keputusan metode per target

| Bentuk target | Alat | Catatan |
|---|---|---|
| REST/JSON resmi | `httpx` + `pydantic` | Selalu validasi respons; API pun berubah |
| SDMX (IMF, BIS, Eurostat) | `pandasdmx` | Format statistik standar, jangan parse manual |
| CKAN (data.go.id) | `httpx` → `package_search` | Katalog terstandar, cari dulu sebelum scrape |
| RSS/Atom | `feedparser` | Termurah untuk berita. Mulai dari sini |
| HTML statis | `httpx` + `selectolax` | Selector via atribut stabil, bukan posisi |
| Endpoint XHR tersembunyi | `httpx` | Cek DevTools dulu — sering ada |
| SPA sungguhan | `Playwright` | Isolasi di modul terpisah; anggap mahal |
| XLSX rilis (BI, Kemenkeu) | `pandas` + `openpyxl` | Cek `sheet_name` & baris header tiap rilis |
| PDF bertabel | `pdfplumber`, `camelot` | Rawan; selalu validasi total kolom |
| Crawl luas tak terstruktur | `Scrapy` | Baru relevan kalau target > ~100 domain |

Aturan yang mengikat: **satu modul per sumber**, dengan antarmuka sama
(`fetch() -> bytes`, `parse(bytes) -> list[Record]`). Kalau BPS ganti format,
yang rusak hanya satu file dan test-nya, bukan seluruh pipeline.

## 5. Arsitektur data: tiga lapis, dan kenapa

```
bronze/   raw persis seperti diterima (html, json, xlsx) + metadata fetch
silver/   sudah di-parse, typed, dinormalisasi, satu skema
gold/     siap analisis: time series, indeks sentimen, tabel peristiwa
```

**Kenapa menyimpan raw itu wajib, bukan opsional:** parser akan salah, dan situs
akan berubah. Kalau raw disimpan, memperbaiki parser berarti *re-parse* — murah,
instan, retroaktif. Kalau tidak, berarti *re-scrape* — dan re-scrape sering
mustahil, karena halaman rilis lama sudah dihapus atau arsipnya berbayar. Ini
kesalahan yang paling mahal untuk disadari belakangan.

Simpan bersama tiap objek bronze: URL, waktu fetch (UTC), status HTTP, ETag,
`Last-Modified`, dan **SHA-256 isi**. Hash itu jadi kunci dedup sekaligus deteksi
perubahan: isi sama = tidak usah diproses ulang.

### Point-in-time (vintage) — bagian yang paling sering dilewatkan

Data makro **direvisi**. Angka PDB kuartal I yang dirilis Mei berbeda dengan
angka periode yang sama saat dilihat November. Kalau backtest strategi memakai
angka final, hasilnya bias ke atas secara sistematis — strateginya "tahu" angka
yang belum diketahui siapa pun saat itu. Ini look-ahead bias, dan efeknya paling
besar justru pada strategi yang kelihatan paling menarik.

Solusinya bukan kolom tambahan seadanya, tapi skema yang sejak awal menyimpan
tiga tanggal per observasi (pola ALFRED/FRED):

- `periode` — periode yang diukur (mis. 2026-Q1)
- `tanggal_rilis` — kapan angka ini pertama diketahui publik
- `valid_sampai` — kapan angka ini digantikan revisi

Konsekuensinya: tabel bersifat **append-only**. Revisi = baris baru, bukan
`UPDATE`. Query "apa yang diketahui pasar pada tanggal X" jadi sekadar filter.
Kalau ini tidak dipasang sejak awal, memperbaikinya nanti berarti membuang
seluruh riwayat yang sudah dikumpulkan.

## 6. Skema inti

Format **long/tidy** ala SDMX, bukan wide. Satu tabel menampung inflasi, kurs,
dan PDB sekaligus — menambah indikator baru tidak mengubah skema.

```
seri_makro (append-only)
  seri_id        str   'bps.ihk.umum.yoy'   -- <sumber>.<domain>.<indikator>.<transformasi>
  periode        date
  nilai          float
  satuan         str   'persen' | 'idr' | 'indeks'
  frekuensi      str   'H' | 'M' | 'Q' | 'T'
  tanggal_rilis  date  -- vintage
  valid_sampai   date  -- NULL = angka yang berlaku sekarang
  sumber_url     str
  hash_sumber    str

artikel (berita / politik / sosial)
  artikel_id     str   -- sha256(url_kanonik)
  url, domain, judul, penulis, waktu_terbit, waktu_fetch
  teks           str
  bahasa         str
  hash_isi       str

anotasi_artikel  -- dipisah dari artikel: model berubah, teks tidak
  artikel_id, model, versi_model, waktu_anotasi
  sentimen       float
  topik          list[str]
  entitas        list[str]
  peristiwa      list[str]
```

`anotasi_artikel` sengaja terpisah. Model NLP akan diganti; kalau anotasi
menempel di tabel artikel, setiap penggantian model berarti menulis ulang tabel
utama dan kehilangan kemampuan membandingkan model lama vs baru.

## 7. Penyimpanan

**Mulai dari Parquet + DuckDB.** Bukan Postgres, bukan MongoDB, bukan Elastic.

- DuckDB membaca Parquet langsung, agregasi kolumnar cepat, nol server, satu file
  yang bisa di-backup dengan sekadar `copy`.
- Partisi bronze per `sumber/tahun/bulan/` — supaya query hanya menyentuh yang perlu.
- Kompresi zstd.

**Kapan naik ke Postgres/TimescaleDB:** saat ada penulis bersamaan (beberapa job
paralel menulis tabel yang sama), atau saat dashboard perlu query dari mesin lain.
DuckDB satu-penulis; itu batas nyatanya, bukan performanya.

Untuk pencarian semantik berita nanti: `sqlite-vec` atau LanceDB. Jangan pasang
Elasticsearch untuk beban satu orang — biaya rawatnya tidak sebanding.

## 8. Penjadwalan

Mulai dengan **GitHub Actions cron**, seperti `Screening-Saham`. Gratis, log
tersimpan, tidak ada mesin yang harus hidup. Batasnya nyata dan perlu diketahui
sejak awal: cron GH Actions bisa telat belasan menit saat runner sibuk, job
dibatasi 6 jam, dan jadwal berhenti sendiri kalau repo tidak aktif 60 hari.

Frekuensi disesuaikan sifat data — bukan disamaratakan:

| Kelompok | Jadwal | Alasan |
|---|---|---|
| Berita / RSS | tiap 15–30 menit | Nilainya ada di kecepatan |
| Kurs, yield, komoditas | harian sore | Setelah pasar tutup |
| Rilis BPS/BI | harian pagi + polling di tanggal rilis | Jadwal rilis diketahui di muka |
| Data tahunan (World Bank) | mingguan | Jarang berubah |

Naik ke **Prefect** (bukan Airflow) kalau sudah butuh dependensi antar-job,
backfill terkontrol, dan retry per-task. Airflow butuh infrastruktur yang tidak
sepadan untuk skala ini.

Satu hal yang harus ada sejak hari pertama: **backfill terpisah dari incremental**.
Job harian dan job "tarik ulang 2015–2026" harus jalur kode yang sama dengan
parameter berbeda, bukan dua skrip yang perlahan berbeda perilaku.

## 9. Reliabilitas

Yang membedakan scraper mainan dari sistem yang bertahan setahun:

1. **Retry + exponential backoff + jitter** (`tenacity`). Tanpa jitter, semua
   target di-retry serempak dan pola bebannya justru terlihat seperti serangan.
2. **Rate limit per domain**, bukan global. Situs pemerintah sering di server
   lemah; 1–2 request/detik sudah sopan dan cukup.
3. **Conditional request**: kirim `If-None-Match` / `If-Modified-Since`. Respons
   304 berarti hemat bandwidth di kedua sisi dan lebih cepat. Ini yang membedakan
   klien sopan dari klien serakah.
4. **User-Agent jujur** dengan alamat kontak. Kalau ada masalah, admin akan email,
   bukan langsung blokir IP.
5. **Circuit breaker**: setelah N gagal beruntun pada satu domain, hentikan sumber
   itu untuk siklus berjalan. Jangan biarkan satu situs down menghabiskan seluruh
   jendela job.
6. **Timeout eksplisit di semua request.** Default sebagian library tidak terbatas;
   satu koneksi menggantung bisa membekukan job sampai batas 6 jam.
7. **Idempoten**: hash isi jadi kunci. Jalan dua kali harus menghasilkan keadaan
   yang sama.

### Deteksi kerusakan diam-diam

Mode gagal paling berbahaya bukan exception — itu terlihat. Yang berbahaya adalah
parser yang **sukses tapi menghasilkan sampah** setelah situs ganti layout:
0 baris, atau semua field kosong, dan tidak ada yang tahu selama tiga minggu.

Penangkalnya, jalan tiap run:

- Assert jumlah minimum: rilis BPS bulanan < 5 baris = gagal, bukan sukses.
- Assert skema: field wajib ada dan bertipe benar (`pydantic`).
- Assert nilai (`pandera`): inflasi bulanan di luar −5%..+5% = tandai, jangan tulis.
- Assert kesinambungan: ada gap tanggal yang tidak dijelaskan hari libur?
- Rekonsiliasi lintas sumber: inflasi BPS vs World Bank harus cocok dalam toleransi.

Semua kegagalan → notifikasi Telegram. Diam bukan tanda sehat; diam biasanya tanda
cron-nya mati.

## 10. Lapisan NLP untuk politik & sosial

Data ekonomi itu angka; politik dan sosial itu teks. Butuh jalur berbeda.

Pendekatan **bertingkat**, karena mengirim semua artikel ke LLM itu mahal dan
tidak perlu:

1. **Saring dulu** — dedup (hash + near-dup via MinHash), filter relevansi dengan
   kata kunci atau klasifikasi murah. Sebagian besar artikel tidak relevan.
2. **Lexicon/aturan** untuk sinyal kasar dan cepat.
3. **IndoBERT** (fine-tune sentimen) untuk volume menengah berbahasa Indonesia —
   lokal, gratis per-inferensi, cukup akurat.
4. **LLM (Claude API)** hanya untuk **ekstraksi terstruktur** yang sulit: siapa
   aktornya, kebijakan apa, sektor terdampak, arah dampak. Pakai output
   terstruktur + prompt caching untuk instruksi yang berulang.

Keluaran yang berguna untuk hilir, bukan sekadar "skor sentimen":

- **Tabel peristiwa**: tanggal, aktor, jenis kebijakan, sektor, arah dampak.
- **Indeks agregat harian** per tema (fiskal, moneter, stabilitas politik) — bisa
  jadi kolom fitur bersama data makro.
- **Volume liputan**: lonjakan jumlah artikel per topik sering jadi sinyal lebih
  awal daripada nada beritanya.

Untuk baseline global murah, GDELT sudah menyediakan tone dan tema terhitung tanpa
perlu NLP sendiri — pakai itu sebagai pembanding sebelum membangun model.

## 11. Legal & etika

Bukan formalitas; ini yang menentukan sistemnya bertahan atau diblokir.

- **Hormati `robots.txt`** dan `Crawl-delay`. Pakai `urllib.robotparser`; jangan
  putuskan manual per situs.
- **Konten berita berhak cipta.** Menyimpan untuk analisis pribadi berbeda dengan
  mempublikasikan ulang teks penuh. Kalau ada output yang dibagikan, keluarkan
  **link + kutipan pendek + metadata**, bukan artikel utuh.
- **UU PDP (No. 27/2022).** Hindari mengumpulkan data pribadi. Media sosial adalah
  area paling berisiko di sini — kalau masuk ke sana, simpan agregat, bukan
  identitas.
- **Jangan tembus paywall atau login.** Selain melanggar ToS, itu memindahkan
  masalah dari ranah teknis ke ranah hukum.
- **Beban server.** Situs pemerintah dibiayai publik dan sering rapuh. Scraping
  yang membuatnya lambat merugikan orang lain, bukan cuma menyalahi aturan.

Aturan praktis: kalau perlu menyamarkan diri agar tidak ketahuan — proxy rotasi,
pemalsuan fingerprint, penyelesaian CAPTCHA — itu tanda batas sudah dilewati.
Berhenti, cari sumber alternatif, atau minta akses resmi. Hampir semua data di
`SUMBER-DATA.md` tersedia tanpa perlu itu.

## 12. Observability

- **Log terstruktur** (`structlog`, JSON): satu baris per fetch berisi sumber, URL,
  status, bytes, durasi, jumlah record.
- **Tabel metrik per run**: `run_id, sumber, waktu, jumlah_item, jumlah_error,
  durasi`. Ini yang membuat "sumber X pelan-pelan menghasilkan lebih sedikit data
  sejak Juli" bisa terlihat.
- **Notifikasi Telegram** untuk kegagalan dan anomali — pakai pola bot yang sudah
  ada di `IDX Screener`, jangan tambah stack baru.
- **Dashboard status sederhana**: satu halaman per sumber (terakhir sukses, jumlah
  record, status). Cukup Streamlit atau HTML statis yang di-generate dari DuckDB.

## 13. Struktur folder

```
Scraping/
  ARSITEKTUR.md          <- dokumen ini
  SUMBER-DATA.md         <- inventaris sumber
  pyproject.toml
  sumber/                <- satu modul per sumber, antarmuka seragam
    bps.py  bi.py  worldbank.py  fred.py  gdelt.py  rss_media.py  idx.py
  inti/
    http.py              <- klien httpx: retry, rate limit, cache kondisional
    penyimpanan.py       <- tulis bronze/silver, partisi, hash
    skema.py             <- model pydantic + aturan pandera
    kualitas.py          <- assert jumlah / nilai / kesinambungan
    notifikasi.py        <- telegram
  alur/
    berita.py              <- ambil & simpan feed, beberapa kali sehari
    edisi.py               <- susun halaman untuk satu tanggal
    harian.py  backfill.py  doctor.py
  situs/
    templat/               <- templat halaman
    _site/                 <- keluaran, dilayani GitHub Pages
  nlp/
    saring.py  sentimen.py  ekstraksi_llm.py
  data/
    bronze/  silver/  gold/  makro.duckdb
  uji/
    fixtures/            <- HTML/JSON tersimpan per sumber
    uji_parser_*.py      <- parser diuji terhadap fixture, tanpa jaringan
  .github/workflows/
```

Catatan soal `uji/fixtures/`: uji parser **tidak boleh** menyentuh jaringan.
Simpan satu respons asli per sumber sebagai fixture, lalu uji parser terhadap itu.
Tes yang butuh internet akan gagal karena alasan yang salah dan lama-lama
diabaikan — dan tes yang diabaikan sama saja dengan tidak ada.

## 14. Roadmap bertahap

Jangan bangun semuanya sekaligus. Urutan ini memberi nilai paling awal:

> **Direvisi 2026-09-09.** Urutan lama menaruh berita di fase 3 sebagai bahan
> baku NLP, dan menaruh seri makro untuk backtest di depan. Itu menunda
> satu-satunya bagian yang dipakai setiap hari. Pemakaian sebenarnya adalah
> **halaman baca pagi** (§16), jadi berita naik ke fase 1 dan NLP keluar dari
> jalur kritis. Prinsip di §2–§13 tidak berubah sedikit pun — hanya urutannya.

**Fase 1 — halaman pagi, end-to-end.** RSS media Indonesia → bronze → dedup →
halaman HTML statis → Telegram kirim link, cron harian. Sempit tapi lengkap:
retry, uji tanpa jaringan, notifikasi kegagalan. Ini cetakan untuk semua sumber
berikutnya, sekaligus satu-satunya fase yang wajib ada supaya sistem ini berguna.

**Fase 2 — kualitas bacaan.** Tambah sumber, perbaiki dedup, saring noise, atur
pembatasan per bagian. Ukurannya sederhana dan jujur: apakah halamannya masih
dibuka di minggu ketiga. Kalau tidak, masalahnya di sini, bukan di fase 3.

**Fase 3 — makro.** BPS via WebAPI, lalu BI (kurs, BI-Rate), FRED, World Bank —
dengan vintage (§5) sejak baris pertama. Angka rilis terbaru muncul di halaman
pagi; riwayatnya mengendap di `seri_makro` untuk dipakai belakangan.

**Fase 4 — NLP, kalau terbukti perlu.** Sentimen dan indeks harian. Hanya masuk
akal setelah beberapa bulan teks terkumpul, dan hanya kalau membaca halaman pagi
ternyata tidak cukup. Fase ini boleh tidak pernah dikerjakan.

**Fase 5 — integrasi.** Sambungkan `seri_makro` ke `Screening-Saham` sebagai
fitur tambahan.

Catatan yang tidak berubah karena pengurutan ulang ini: teks yang tidak
dikumpulkan hari ini tidak bisa dikumpulkan retroaktif, dan vintage tidak bisa
dipasang belakangan. Keduanya kini justru lebih awal, bukan lebih akhir.

## 15. Anti-pattern

Kesalahan yang paling sering dan paling mahal:

1. **Langsung pakai Playwright** karena "situsnya dinamis", tanpa cek tab Network.
2. **Tidak menyimpan raw.** Parser salah = data hilang permanen.
3. **Tabel wide**, satu kolom per indikator. Tiap indikator baru = migrasi skema.
4. **`UPDATE` pada data makro.** Menghapus riwayat revisi, merusak backtest.
5. **Selector rapuh**: `div > div:nth-child(3) > span`. Pakai atribut semantik.
6. **Diam saat gagal.** `try/except: pass` di scraper adalah bug tersembunyi.
7. **Menyamaratakan frekuensi.** Menarik data tahunan tiap 5 menit = beban percuma
   dan risiko diblokir tanpa manfaat apa pun.
8. **Semua artikel dikirim ke LLM.** Biaya naik linear, nilai tambahnya tidak.
9. **Timezone campur.** Simpan UTC di semua lapisan, konversi ke WIB hanya saat
   tampil. Data pasar + rilis pemerintah + berita global bercampur — ini akan
   menggigit.
10. **Satu file raksasa** `scraper.py`. Satu sumber rusak = semua ikut mati.

## 16. Keluaran

Bab ini ditambahkan belakangan karena §12 hanya mengatur setengah dari kebutuhan.
Ada dua hal berbeda yang mudah tertukar:

| | Menjawab | Diatur di |
|---|---|---|
| **Notifikasi operasional** | Cron jalan? Parser rusak? BPS cuma keluar 2 baris? | §9, §12 |
| **Edisi harian** | Apa yang perlu kubaca pagi ini? | Bab ini |

Yang pertama soal kesehatan pipeline, yang kedua soal isi datanya. Keduanya lewat
Telegram, tapi jangan digabung dalam satu pesan — kegagalan teknis harus tetap
terbaca pada hari ketika halaman paginya kosong karena memang tidak ada berita.
Dan pesan kegagalan tidak boleh menumpang di pemberitahuan edisi: kalau edisinya
gagal terbit, justru pesan itu yang tidak akan terkirim.

### Format: halaman HTML untuk dibaca, Telegram untuk memanggil

Pemakaian yang dituju konkret: **dibaca pagi hari sambil minum kopi**, berisi
berita sejak pagi kemarin sampai dini hari, cukup untuk tidak ketinggalan
peristiwa mikro/makro. Itu mengubah peran kedua kanal dibanding rancangan awal
bab ini:

- **Halaman HTML statis = kanal utama.** Pesan Telegram tidak bisa dibuat enak
  dibaca — tidak ada tipografi, hierarki, atau pengelompokan, dan pesan panjang
  terpotong tiap 4096 karakter. Halaman bisa. Di-generate ke GitHub Pages, pola
  `_site/` yang sudah dipakai di `Screening-Saham`. Nol server, dan riwayat
  tiap edisi otomatis tersimpan di git.
- **Telegram = pemberitahuan.** Satu baris ringkas + link, supaya tidak perlu
  ingat membuka apa pun. Pakai `inti/notifikasi.py` yang sudah ada.

**Bukan PDF.** Empat alasan, semuanya konkret:

1. Dibaca di HP. PDF harus diunduh, dibuka di aplikasi lain, di-zoom. Pesan
   Telegram terbaca di notifikasi.
2. Link praktis mati rasa di PDF — padahal §11 memutuskan keluaran berisi **link
   + kutipan pendek + metadata**, bukan artikel utuh. Jadi isi rangkuman ini
   sebagian besar memang link.
3. Tidak bisa dicari. "Kapan terakhir ada berita soal DHE" tidak terjawab oleh 90
   file PDF; terjawab oleh satu query DuckDB.
4. Butuh dependensi baru (weasyprint/reportlab) untuk keuntungan nol. §1 sudah
   memutuskan: jangan tambah stack.

### Jendela waktu dan jadwal

Edisi hari ini memuat berita **05:30 WIB kemarin sampai 05:30 WIB hari ini**.

Cron GitHub Actions memakai UTC, jadi 05:30 WIB adalah **22:30 UTC hari
sebelumnya**. Ini gampang salah sehari, dan §15 #9 sudah memperingatkan soal
timezone campur: simpan UTC di semua lapisan, konversi ke WIB hanya saat tampil.
Jendela dihitung dari parameter waktu edisi, bukan dari `now()` — supaya edisi
kemarin bisa dibuat ulang persis.

§8 mencatat cron GH Actions bisa telat belasan menit saat runner sibuk. Untuk
halaman baca pagi itu tidak masalah; yang penting jendela waktunya tetap, bukan
jam terbitnya.

### Bagian dan pembatasan

Empat bagian, sesuai yang mau dibaca:

1. **Makro & kebijakan Indonesia** — rilis BPS/BI, APBN, pajak, suku bunga, kurs, regulasi
2. **Pasar & emiten IDX** — aksi korporasi, laporan keuangan, IPO, berita emiten
3. **Politik & sosial** — yang berpotensi menggerakkan pasar
4. **Global** — The Fed, komoditas, geopolitik

**Tiap bagian dibatasi jumlah itemnya.** Empat kategori dari belasan media
gampang menghasilkan seratus item, dan halaman yang tidak muat dibaca dalam lima
menit tidak akan dibaca sama sekali. Batas ini fitur, bukan keterbatasan.

### Dedup menentukan halaman ini berhasil atau tidak

Bagian tersulit bukan tampilannya, tapi **near-duplicate detection**. Selusin
media menulis peristiwa yang sama dari rilis yang sama. Tanpa dedup, halamannya
berisi 80 item yang sebenarnya 15 peristiwa, dan berhenti dibuka di hari ketiga.

Hasil sampingnya langsung memberi urutan: **berapa banyak media meliput satu
peristiwa = seberapa penting peristiwa itu**. Proxy yang murah, tidak butuh NLP,
dan biasanya lebih jujur daripada skor sentimen. Ini yang membuat §10 tidak ada
di jalur kritis.

Tiap item ditampilkan sebagai judul + satu-dua kalimat + sumber + jam, dengan
media lain yang meliput hal sama dilipat jadi satu baris. Batasnya §11: link,
kutipan pendek, dan metadata — bukan teks artikel utuh, sekalipun halaman ini
hanya dibaca sendiri.

### Aturan yang mengikat: edisi di-generate dari data tersimpan

`alur/edisi.py` menerima **parameter tanggal**, membaca artikel yang sudah
tersimpan dalam jendela waktu edisi itu, dan menghasilkan halaman. Job harian
hanyalah pemanggilan dengan tanggal hari ini.

Konsekuensinya: edisi tanggal berapa pun bisa dibuat ulang. Kalau tampilannya
diperbaiki bulan depan, seluruh arsip bisa di-render ulang; kalau logika
dedup diperbaiki, edisi lama bisa dinilai ulang dengan aturan baru. Kalau halaman
disusun langsung di dalam job harian sambil mengambil feed, kemampuan itu hilang
permanen — kesalahan yang sejenis dengan tidak menyimpan raw (§5).

Karena itu urutannya tetap **dua langkah terpisah**, bukan satu: `alur/berita.py`
mengambil dan menyimpan, `alur/edisi.py` menyusun halaman. Pemisahan ini soal
bisa-diulang, bukan soal frekuensi — keduanya boleh jalan di job yang sama.

### Frekuensi: sekali sehari, jam 05:00 WIB

Diputuskan setelah mengukur retensi tiap feed (`SUMBER-DATA.md` §C1). Sekali ambil
per hari menangkap **28% dari item yang terbit** — angka yang terdengar buruk tapi
menyesatkan:

- Yang hilang terkonsentrasi di feed paling berisik. Investing.com menerbitkan
  ~67 item/jam dan hanya menyimpan 6 menit terakhir; Antara terkini ~42 item/jam.
  Isinya persis bagian yang dibuang oleh penyaringan 97% di atas.
- Feed yang paling berguna justru **tertangkap 100%**: CNN Indonesia ekonomi
  (retensi 45 jam), Detik finance (31j), CNBC Indonesia market (47j), ketiga feed
  Google News, dan Fed/ECB/BBC yang menyimpan berminggu-minggu.
- Pengaman struktural: peristiwa penting diliput banyak media sekaligus — dasar
  pengurutan yang dipakai bab ini. Kalau satu feed menggeser berita penting
  keluar, feed lain hampir pasti masih menyimpannya. Yang benar-benar hilang
  adalah berita yang hanya diliput satu media berisi tinggi.

**Jamnya 05:00 WIB, bukan tengah malam.** Sesi pasar Amerika tutup 03:00–04:00
WIB; job yang jalan jam 23:00 membuat kategori global selalu tertinggal sehari.
Cron GitHub Actions: `0 22 * * *` (22:00 UTC hari sebelumnya), memberi margin
terhadap keterlambatan runner yang dicatat §8 sebelum halaman dibaca jam 06:00.

Kalau nanti ternyata ada berita penting yang sering terlewat, penawarnya menambah
satu pengambilan sore — bukan mengubah arsitektur. Langkahnya sudah terpisah.

### Menambahkan angka makro, nanti

Mulai fase 3, bagian pertama halaman diawali angka rilis terbaru dari
`seri_makro` — IHK, BI-Rate, kurs — dengan nilai sebelumnya dan arahnya, dan
ditandai kalau angka itu revisi (§5). Ini alasan `seri_makro` tetap dibangun
meski produk utamanya halaman baca: satu baris angka di puncak halaman jauh lebih
berguna daripada sepuluh judul berita tentang angka yang sama.

### Kapan

**Fase 1 — sekarang.** Ini produk utamanya, bukan pelengkap yang menyusul.

Yang belum ada di fase 1 dan memang tidak perlu: indeks sentimen, tabel
peristiwa, dan seluruh §10. Halaman pagi yang berisi berita ter-dedup dan
terurut sudah menjawab kebutuhannya. §10 baru relevan kalau ternyata membaca
halaman itu tidak cukup — dan itu pertanyaan yang hanya bisa dijawab setelah
beberapa bulan membacanya.
