# Sistem Intelijen Data Makro–Mikro Indonesia

Pipeline pengumpulan data makro, politik, dan sosial Indonesia — untuk memberi
konteks pada keputusan pasar. Dipakai satu orang, bukan produk multi-user.

**Status: fase 1 baru dimulai.** Dokumen keputusan lengkap; dari kode, baru
`inti/notifikasi.py` yang ada.

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

1. **Tulang punggung** — satu sumber (BPS) end-to-end: bronze → silver → DuckDB,
   lengkap dengan retry, validasi, uji, cron, notifikasi. Ini jadi cetakan.
2. **Perluas makro** — BI, World Bank, FRED. Di sini skema diuji beneran.
3. **Berita** — RSS media ekonomi Indonesia + GDELT. Kumpulkan dulu, NLP nanti.
4. **NLP** — saring, dedup, sentimen, indeks harian.
5. **Integrasi** — sambungkan ke `Screening-Saham` sebagai fitur tambahan.

## Catatan

Repositori pribadi. Dokumen di sini adalah catatan keputusan untuk diri sendiri,
bukan rekomendasi umum — beberapa pilihannya hanya masuk akal pada skala satu
orang dan ratusan–ribuan dokumen per hari.
