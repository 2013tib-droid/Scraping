# Inventaris Sumber Data

Urut berdasarkan prinsip di `ARSITEKTUR.md` §2: **API resmi dulu, scraping HTML
paling akhir**. Kolom **Status** menandai mana yang sudah dicek langsung dan mana
yang masih perlu diverifikasi sebelum dijadwalkan.

Legenda status:
- ✅ dikonfirmasi (dokumentasi/endpoint sudah dicek)
- ⚠️ kemungkinan besar benar, belum dicek langsung — verifikasi sebelum dipakai

---

## A. Makro Indonesia — resmi

| Sumber | Data | Metode | Key | Status |
|---|---|---|---|---|
| **BPS WebAPI** — `webapi.bps.go.id` | IHK/inflasi, PDB, ekspor–impor, tenaga kerja, kemiskinan, tabel statis & dinamis | REST JSON | Ya, gratis, daftar di `/developer/` | ✅ |
| **BI Web Service kurs** | Kurs transaksi BI per mata uang, harian | `GET /biwebservice/wskursbi.asmx/getSubKursLokal3?mts=USD&startdate=&enddate=` | Tidak | ✅ |
| **BI — JISDOR & informasi kurs** | JISDOR USD/IDR (sejak 2013), kurs acuan non-USD | Halaman `bi.go.id/id/fungsi-utama/moneter/informasi-kurs/` | Tidak | ✅ halaman ada; format tabel ⚠️ |
| **BI — SEKI** | Statistik Ekonomi & Keuangan Indonesia: moneter, fiskal, sektor riil, eksternal. Terbit bulanan | Unduh XLSX per tabel | Tidak | ✅ ada; **tidak ada API** — parsing file |
| **BI — BI-Rate / kebijakan moneter** | Suku bunga acuan, hasil RDG | Halaman + siaran pers | Tidak | ⚠️ |
| **Satu Data Indonesia** — `data.go.id`, `katalog.data.go.id` | Katalog lintas K/L; banyak dataset daerah | **CKAN API**: `package_search`, `package_show`, `datastore_search` | Tidak | ✅ |
| **Kemenkeu** | APBN, realisasi, utang pemerintah, SBN | Portal data + XLSX/PDF | Tidak | ⚠️ cek ketersediaan API |
| **DJPPR Kemenkeu** | Profil utang, lelang SBN, yield | Halaman + XLSX | Tidak | ⚠️ |
| **OJK** | Statistik perbankan, IKNB, pasar modal | PDF/XLSX bulanan | Tidak | ⚠️ format PDF, biaya parsing tinggi |
| **IDX** — `idx.co.id` | Emiten, laporan keuangan, ringkasan perdagangan | Endpoint JSON internal | Tidak | ⚠️ tidak resmi, sering di balik Cloudflare — cek ToS dulu |

**Catatan BI:** tidak ada API terpadu untuk seluruh statistik BI. Kurs punya web
service; sisanya lewat file rilis. Rencanakan dua jalur berbeda untuk satu
lembaga ini.

## B. Makro global & pembanding

| Sumber | Data | Metode | Key | Status |
|---|---|---|---|---|
| **FRED / ALFRED** — St. Louis Fed | Ribuan seri global termasuk Indonesia; **ALFRED = vintage/point-in-time** | REST, lib `fredapi` | Ya, gratis | ✅ |
| **World Bank** | WDI: PDB, populasi, gini, indikator pembangunan | REST v2 JSON | Tidak | ⚠️ (umumnya tanpa key) |
| **IMF** | IFS, WEO, BOP | SDMX, lib `pandasdmx` | Tidak | ⚠️ |
| **BIS** | Kurs efektif, kredit, properti | SDMX / CSV bulk | Tidak | ⚠️ |
| **Yahoo Finance** | Harga saham, indeks, komoditas, FX | `yfinance` (sudah dipakai di `Screening-Saham`) | Tidak | ✅ sudah terpakai |

FRED penting bukan hanya karena cakupannya, tapi karena **ALFRED menyediakan
vintage** — satu-satunya cara murah memvalidasi apakah logika point-in-time
(`ARSITEKTUR.md` §5) benar-benar bekerja.

## C. Berita, politik, sosial

| Sumber | Data | Metode | Key | Status |
|---|---|---|---|---|
| **GDELT DOC 2.0 API** | Berita global terindeks, filter negara/bahasa/rentang waktu, **tone −100..+100** | REST, gratis | Tidak | ✅ |
| **GDELT Events / GKG** | Peristiwa terstruktur, aktor, tema, tone — via file bulk atau BigQuery | Bulk CSV / BigQuery | Tidak (BigQuery berbayar) | ⚠️ |
| **RSS media ID + global** | 29 feed terverifikasi lintas 4 kategori | `feedparser` | Tidak | ✅ **lihat §C1** — ditembak langsung 2026-09-09 |
| **peraturan.go.id / JDIH** | Regulasi baru, PP, Perpres, PMK | Halaman + PDF | Tidak | ⚠️ |
| **Google Trends** | Minat pencarian per topik/wilayah | `pytrends` (tidak resmi) | Tidak | ⚠️ sering rate-limit; jangan jadi ketergantungan |
| **ACLED** | Data konflik & protes | REST | Ya, registrasi | ⚠️ cek lisensi non-komersial |
| **Reddit / X** | Sentimen ritel | API resmi | Ya, X sekarang mahal | ⚠️ nilai rendah dibanding biayanya |

**Prioritas realistis:** RSS media Indonesia. Menutup sebagian besar kebutuhan
berita dengan biaya nyaris nol dan tanpa masalah legal. GDELT ditunda — baru
relevan kalau §10 (NLP) dikerjakan, dan `ARSITEKTUR.md` §14 kini menyatakan fase
itu boleh tidak pernah ada. Media sosial juga ditunda: biaya tinggi, kualitas
sinyal rendah, dan paling rawan secara UU PDP.

---

## C1. Feed RSS — hasil verifikasi 2026-09-09

Semua baris di bawah **ditembak langsung**, bukan diambil dari dokumentasi.
Kolom "dlm 24j" = jumlah item yang jatuh di dalam jendela edisi (`ARSITEKTUR.md`
§16). Kolom "teks" = panjang ringkasan di item pertama; `judul` berarti feed itu
hanya memberi judul tanpa ringkasan.

### A. Makro & kebijakan Indonesia

| Feed | URL | Item | dlm 24j | Teks |
|---|---|---:|---:|---|
| CNBC Indonesia news | `cnbcindonesia.com/news/rss` | 100 | 100 | 274c |
| Bloomberg Technoz | `bloombergtechnoz.com/rss` | 100 | 100 | 155c |
| Media Indonesia ekonomi | `mediaindonesia.com/rss/ekonomi` | 100 | 100 | 134c |
| Detik finance | `finance.detik.com/rss` | 100 | 71 | 300c |
| CNN Indonesia ekonomi | `cnnindonesia.com/ekonomi/rss` | 100 | 50 | 283c |
| Liputan6 bisnis | `feed.liputan6.com/rss/bisnis` | 50 | 50 | 145c |
| Sindonews ekbis | `ekbis.sindonews.com/rss` | 30 | 30 | 155c |
| Kontan nasional | `nasional.kontan.co.id/rss` | 25 | 25 | 139c |
| Kontan keuangan | `keuangan.kontan.co.id/rss` | 25 | 25 | 137c |
| Kontan industri | `industri.kontan.co.id/rss` | 25 | 25 | 152c |
| Katadata | `katadata.co.id/rss` | 25 | 25 | 362c |
| Republika ekonomi | `republika.co.id/rss/ekonomi` | 15 | 15 | 223c |
| Antara terkini | `antaranews.com/rss/terkini.xml` | 50 | — | 259c |

Antara terkini hidup tapi **labil** — satu dari dua percobaan gagal dengan
`RemoteProtocolError`. Retry (§9 #1) menutupinya; jangan sampai dianggap mati.

### B. Pasar & emiten IDX

| Feed | URL | Item | dlm 24j | Teks |
|---|---|---:|---:|---|
| CNBC Indonesia market | `cnbcindonesia.com/market/rss` | 100 | 42 | 374c |
| Google News "IHSG/BEI" | `news.google.com/rss/search?q=IHSG…` | 100 | 87 | 447c |
| Google News "emiten" | `news.google.com/rss/search?q=emiten…` | 71 | 71 | 405c |
| IDN Financials | `idnfinancials.com/id/feed` | 30 | 30 | 123c |
| Pasardana | `pasardana.id/rss` | 30 | 30 | 54c |
| Kontan investasi | `investasi.kontan.co.id/rss` | 25 | 25 | 108c |

Ini kategori paling tipis, sesuai dugaan. Media khusus pasar modal sebagian besar
tidak lagi menyediakan RSS (lihat C2). Dua feed Google News menambal celahnya:
formatnya rapi, bertanggal, dan ringkasannya justru paling panjang. Feed IDN
Financials tidak diiklankan di mana pun — ditemukan lewat autodiscovery
`<link rel="alternate">` di HTML beranda.

### C. Politik & sosial

| Feed | URL | Item | dlm 24j | Teks |
|---|---|---:|---:|---|
| Detik news | `news.detik.com/rss` | 100 | 100 | 322c |
| CNN Indonesia nasional | `cnnindonesia.com/nasional/rss` | 100 | 80 | 268c |
| Republika utama | `republika.co.id/rss` | 15 | 15 | 236c |

### D. Global

| Feed | URL | Item | dlm 24j | Teks |
|---|---|---:|---:|---|
| Google News "Reuters business" | `news.google.com/rss/search?q=site:reuters.com…` | 100 | 100 | 425c |
| CNBC US | `cnbc.com/id/100003114/device/rss/rss.html` | 30 | 29 | 149c |
| Al Jazeera | `aljazeera.com/xml/rss/all.xml` | 25 | 25 | 91c |
| BBC business | `feeds.bbci.co.uk/news/business/rss.xml` | 53 | 20 | 111c |
| MarketWatch | `feeds.content.dowjones.io/public/rss/mw_topstories` | 10 | 10 | 90c |
| Investing.com | `investing.com/rss/news.rss` | 10 | 10 | judul |
| Federal Reserve | `federalreserve.gov/feeds/press_all.xml` | 20 | 0 | 154c |
| ECB press | `ecb.europa.eu/rss/press.html` | 15 | 1 | judul |

Fed dan ECB nol/satu item dalam 24 jam bukan tanda rusak — siaran pers bank
sentral memang jarang. Justru itu yang membuat keduanya bernilai tinggi: kalau
muncul, hampir pasti layak dibaca. Jangan disamakan perlakuannya dengan feed
media yang menghasilkan ratusan item.

### Tiga angka yang menentukan desain

1. **1.291 item dalam jendela 24 jam** dari 29 feed. Target bacanya lima menit —
   sekitar 30–40 item. Artinya **97% harus dibuang**. Dedup dan pembatasan per
   bagian (`ARSITEKTUR.md` §16) bukan penyempurnaan, itu keseluruhan produknya.
2. **Retensi feed sangat timpang** — diukur dari umur item tertua. Sekali ambil
   per hari menangkap 28% dari total item terbit, tapi sebarannya yang penting:

   | Retensi | Feed | Tertangkap 1x/hari |
   |---|---|---|
   | < 4 jam | Investing.com (0,1j), Antara terkini (1,2j), Republika utama (2,5j), Katadata (3,9j) | 1–16% |
   | 7–10 jam | Al Jazeera, Detik news, Kontan investasi, IDN Financials, MarketWatch | 31–41% |
   | 14–21 jam | Media Indonesia, Republika ekonomi, 3× Kontan, Sindonews, CNBC ID news, Pasardana, Bloomberg Technoz, Liputan6 | 61–88% |
   | > 24 jam | CNN ID ekonomi (45j), CNBC ID market (47j), Detik finance (31j), CNBC US (32j), 3× Google News, Fed/ECB/BBC (berminggu) | 100% |

   Yang hilang terkonsentrasi di feed berlaju tinggi — Investing.com ~67 item/jam,
   Antara terkini ~42 item/jam — yaitu bagian yang memang dibuang penyaringan.
   Feed paling berguna justru tertangkap penuh. Dasar keputusan frekuensi di §16.
3. **Semua feed yang lolos bertanggal 100%.** Tidak perlu menebak waktu terbit
   dari isi — dan `published` sudah beroffset benar (`+0700` untuk media ID).

### Catatan environment: proxy TLS-inspection

Dari jaringan kantor, sebagian besar host di atas gagal dengan
`CERTIFICATE_VERIFY_FAILED` — proxy kantor membongkar TLS, dan sertifikatnya
tidak ada di bundel CA bawaan Python. Bukan masalah feed-nya.

Penawarnya `truststore`, yang membuat Python memakai certificate store Windows:

```python
import truststore
truststore.inject_into_ssl()
```

Ini cara yang benar — bukan mematikan verifikasi TLS. Lihat `inti/notifikasi.py`
untuk sikap yang sama.

Satu jebakan lagi yang sudah memakan waktu: **User-Agent wajib ASCII.** §9 #4
meminta UA jujur beralamat kontak; kalau di dalamnya ada em dash, httpx melempar
`UnicodeEncodeError` sebelum request keluar, dan gejalanya terlihat seperti semua
situs mati serempak.

## C3. Blokir IP dari runner GitHub

Terungkap saat workflow benar-benar dipicu, bukan saat diuji lokal. **Delapan feed
membalas HTTP 403 dari runner GitHub Actions** (yang berlokasi di AS), padahal
semuanya normal dari jaringan Indonesia:

CNBC Indonesia (news + market), CNN Indonesia (ekonomi + nasional),
Kontan (nasional, industri, investasi), Media Indonesia ekonomi.

Menariknya `keuangan.kontan.co.id` lolos sementara tiga subdomain Kontan lain
diblokir — aturannya tidak seragam bahkan dalam satu penerbit.

**Bukan soal header.** Sudah diuji dengan menambahkan `Accept` dan
`Accept-Language` yang benar; hasilnya persis sama. Ini blokir berbasis IP
(datacenter/geografis). Header tetap dipertahankan karena memang seharusnya ada.

**Yang tidak dilakukan:** memakai proxy residensial atau memalsukan fingerprint
supaya lolos. `ARSITEKTUR.md` §11 menyatakan itu tanda batas sudah dilewati, dan
403 dari sebuah IP adalah penerbit yang menolak IP itu — bukan undangan mencari
jalan lain.

**Penawarnya:** Google News tidak diblokir, dan justru mengagregasi penerbit yang
sama. Feed `Google News ekonomi ID` memulihkan CNBC Indonesia, CNN Indonesia, dan
Kompas.com — yang terakhir bahkan tidak punya feed langsung sama sekali (§C2).
Tautannya tetap menuju penerbit aslinya.

Dua kandidat penambal lain diuji dan **ditolak** karena kualitasnya:

| Kandidat | Sumber teratas yang muncul | Putusan |
|---|---|---|
| Google News "moneter" | fxstreet-id.com, Vietnam.vn | Tolak — noise tinggi |
| Google News "politik ID" | Berita Cilegon, Kompasiana, Pemprov Banten | Tolak — blog dan situs pemda, bukan berita nasional |

Kalau nanti dijalankan dari IP Indonesia (PC sendiri atau VPS Indonesia),
kedelapan feed itu hidup lagi tanpa perubahan kode — daftarnya tetap di
`sumber/feed.toml`, hanya statusnya yang berubah.

## C2. Feed yang ditolak, dan alasannya

Dicatat supaya tidak dicoba ulang tiap beberapa bulan.

| Kandidat | Alasan |
|---|---|
| **Bisnis.com** | Tidak ada feed yang bisa ditemukan. Lima pola URL 404/bozo, dan beranda tidak mendeklarasikan autodiscovery |
| **Kompas** | Sama — semua pola 403/404, tanpa autodiscovery |
| **Antara ekonomi & politik** | Hidup, tapi isinya artikel *evergreen* SEO ("Apa itu IKD", "PHK dan resign apa bedanya"), bukan berita. Feed politik basi 11 hari |
| **Tempo bisnis & nasional** | Item terbaru berumur 60 jam. Tanggalnya benar — feed-nya memang tertinggal |
| **Okezone economy** | Tanggal rusak — item pertama terbaca berumur ~10 tahun |
| **Emitennews** | HTTP 500 di `/feed` dan `/rss` |
| **Investor.id, Bareksa, Stockwatch, IQPlus, Tirto, Kumparan** | 404 / 403 / bukan XML |
| **Kemenkeu, BI** | Tidak menyediakan RSS. Rilisnya lewat halaman dan file — jalur berbeda (§A) |

## D. Yang sebaiknya tidak dikejar

- **Trading Economics, CEIC, Bloomberg** — datanya bagus, tapi berlangganan mahal
  dan ToS melarang scraping. Kalau butuh, beli; jangan scrape.
- **Situs berbayar / paywall** — lihat `ARSITEKTUR.md` §11.
- **Agregator tak jelas asalnya** — kalau tidak bisa ditelusuri ke sumber resmi,
  datanya tidak bisa dipertanggungjawabkan di backtest.

---

## Langkah verifikasi sebelum menambah sumber

Checklist singkat, jalankan untuk tiap baris ⚠️ di atas:

1. Cek `robots.txt` dan ToS.
2. Cari API/feed resmi sebelum melihat HTML.
3. Buka DevTools → Network → XHR: ada endpoint JSON?
4. Ambil satu respons, simpan ke `uji/fixtures/`.
5. Tentukan frekuensi update sebenarnya — jangan polling lebih sering dari itu.
6. Catat: apakah sumber ini merevisi angkanya? Kalau ya, `tanggal_rilis` wajib.
