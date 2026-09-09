# Sistem Intelijen Data Makro–Mikro Indonesia

Halaman baca pagi: berita mikro dan makro Indonesia dari 24 jam terakhir,
ter-dedup dan terurut, cukup dibaca lima menit sambil ngopi. Di belakangnya,
pipeline yang lama-lama juga menyimpan seri data makro untuk dipakai
`Screening-Saham`. Dipakai satu orang, bukan produk multi-user.

**Halaman paginya: <https://2013tib-droid.github.io/Scraping/>**

Terbit sendiri tiap 05:00 WIB, berisi berita 24 jam terakhir yang sudah
di-dedup dan diurutkan menurut berapa banyak media meliputnya. Edisi lama ada di
`docs/arsip/`.

**Status: fase 1 jalan.** Pengambil, dedup, dan halaman sudah ada dan
terjadwal. Seri makro (fase 3) belum.

Tiga dokumen di bawah ditulis lebih dulu supaya pilihan teknisnya punya alasan
yang bisa ditelusuri, bukan warisan kebiasaan. Implementasi menyusul mengikuti
roadmap di `ARSITEKTUR.md` §14.

## Dokumen

| Dokumen | Isi |
|---|---|
| [ARSITEKTUR.md](ARSITEKTUR.md) | Keputusan teknis: bahasa, penyimpanan, skema, reliabilitas, legal, anti-pattern |
| [SUMBER-DATA.md](SUMBER-DATA.md) | Inventaris sumber beserta status verifikasinya |
| [KEPUTUSAN-TOOLING.md](KEPUTUSAN-TOOLING.md) | Evaluasi Scrapling, ScrapeGraphAI, agent-reach — apa yang diambil dan kenapa |

## Menjalankan

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[uji]"   # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m pytest
```

Uji tidak menyentuh jaringan sama sekali — itu syarat, bukan kebetulan
(`ARSITEKTUR.md` §13). Salin `.env.example` jadi `.env` kalau mau notifikasi
benar-benar terkirim ke Telegram; kalau dibiarkan kosong, notifikasi turun ke
terminal dan tidak ada yang error.

**Penilai dampak** (`inti/dampak.py`) memisahkan yang high impact dari yang
sekadar enak diketahui: sekali per edisi, seluruh peristiwa yang sudah ter-dedup
dinilai Claude pada skala 0–3 plus satu kalimat "kenapa penting". Yang 3 naik ke
blok *Penting Pagi Ini*, yang 0 dibuang. Aktif hanya kalau `ANTHROPIC_API_KEY`
ada (lokal lewat `.env`, di Actions lewat `gh secret set ANTHROPIC_API_KEY`);
tanpa itu halaman diurutkan jumlah media saja, seperti sebelumnya. Hasil
penilaian disimpan per URL, jadi membangun ulang edisi tidak memanggil API lagi.

## Prinsip yang mengikat semuanya

Scraping adalah **pilihan terakhir**, bukan titik awal:

```
API resmi  →  SDMX / open-data catalog  →  file rilis (xlsx/csv)
           →  RSS/Atom  →  endpoint JSON internal  →  parsing HTML  →  browser
```

Setiap langkah ke kanan berarti lebih rapuh, lebih lambat, lebih sering rusak,
dan lebih berat secara hukum. Sebagian besar data makro Indonesia sudah tersedia
tanpa scraping sama sekali — BPS punya WebAPI, data.go.id punya CKAN, FRED dan
World Bank punya REST. Menulis scraper HTML untuk data yang punya API adalah
utang teknis yang dibayar ulang setiap kali situsnya ganti tema.

Konsekuensi yang dipegang sejak awal:

- **Raw selalu disimpan.** Parser akan salah dan situs akan berubah; kalau raw
  ada, memperbaiki parser berarti re-parse — murah dan retroaktif.
- **Data makro direvisi, jadi tabelnya append-only.** Tiap observasi menyimpan
  periode, tanggal rilis, dan masa berlaku (pola ALFRED/FRED). Tanpa ini,
  backtest kena look-ahead bias.
- **Diam bukan tanda sehat.** Parser yang sukses tapi menghasilkan sampah lebih
  berbahaya daripada yang melempar exception.
- **Tidak menyamarkan diri.** Tanpa rotasi proxy, pemalsuan fingerprint, atau
  penyelesaian CAPTCHA. Kalau sebuah sumber butuh itu, sumbernya yang diganti.

## Roadmap

1. **Halaman pagi** — RSS → bronze → dedup → HTML statis → Telegram kirim link,
   cron harian. Sempit tapi lengkap; ini cetakan untuk sumber berikutnya.
2. **Kualitas bacaan** — tambah sumber, perbaiki dedup, saring noise. Ukurannya
   jujur: apakah halamannya masih dibuka di minggu ketiga.
3. **Makro** — BPS, BI, FRED, World Bank, dengan vintage sejak baris pertama.
   Angka rilis terbaru naik ke puncak halaman pagi.
4. **NLP — kalau terbukti perlu.** Sentimen dan indeks harian. Boleh tidak
   pernah dikerjakan.
5. **Integrasi** — sambungkan `seri_makro` ke `Screening-Saham`.

## Catatan

Repositori pribadi. Dokumen di sini adalah catatan keputusan untuk diri sendiri,
bukan rekomendasi umum — beberapa pilihannya hanya masuk akal pada skala satu
orang dan ratusan–ribuan dokumen per hari.
