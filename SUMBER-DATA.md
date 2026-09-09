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
| **RSS media ekonomi ID** | Antara, Kontan, Bisnis, CNBC Indonesia, Katadata, Tempo, Detik Finance | `feedparser` | Tidak | ⚠️ cek URL feed satu per satu |
| **peraturan.go.id / JDIH** | Regulasi baru, PP, Perpres, PMK | Halaman + PDF | Tidak | ⚠️ |
| **Google Trends** | Minat pencarian per topik/wilayah | `pytrends` (tidak resmi) | Tidak | ⚠️ sering rate-limit; jangan jadi ketergantungan |
| **ACLED** | Data konflik & protes | REST | Ya, registrasi | ⚠️ cek lisensi non-komersial |
| **Reddit / X** | Sentimen ritel | API resmi | Ya, X sekarang mahal | ⚠️ nilai rendah dibanding biayanya |

**Prioritas realistis untuk fase 3:** GDELT + RSS media Indonesia. Dua ini menutup
sebagian besar kebutuhan berita dengan biaya nyaris nol dan tanpa masalah legal.
Media sosial sebaiknya ditunda — biaya tinggi, kualitas sinyal rendah, dan paling
rawan secara UU PDP.

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
