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
sekadar enak diketahui, pada skala 0–3. Yang 3 naik ke blok *Penting Pagi Ini*,
yang 0 dibuang. Aturannya deterministik dan seluruhnya lokal — frasa penanda di
judul, luas liputan, bobot sumber, dan saringan noise — jadi tidak ada kunci API,
tidak ada biaya, tidak ada kuota, dan tidak ada jalur gagal karena jaringan.

Ambangnya dikalibrasi ke sebaran nyata, bukan ke intuisi: 95% peristiwa hanya
diliput satu media dan maksimumnya lima, karena dedup mencocokkan kemiripan judul
sementara redaksi menuliskan hal yang sama dengan judul yang jauh berbeda. Itu
sebabnya liputan dipakai sebagai bukti hanya ketika angkanya ekstrem, dan frasa
yang memikul sebagian besar beban. Daftar frasanya ada di berkas itu juga dan
memang dimaksudkan untuk diubah — kalau blok utama terasa longgar atau ketat
setelah beberapa hari, di situ tempatnya.

Yang tidak dilakukan: kalimat "kenapa penting bagi investor". Itu tidak bisa
dihitung dari aturan, jadi `alasan` diisi label aturan yang menyala
("Kebijakan moneter", "Liputan luas") — bukan analisis yang dikarang.

**Status arah** (`inti/sentimen.py`) menandai tiap peristiwa positif, negatif,
atau netral, dan tampil sebagai lencana ↑/↓ di halaman. Aturannya lokal dan
deterministik seperti penilai dampak — tidak ada model, tidak ada kunci API,
tidak ada biaya.

Yang membedakannya dari kamus kata positif/negatif biasa: arah kata tidak
menentukan arah berita. "Naik" kabar baik untuk laba dan ekspor, kabar buruk
untuk inflasi, utang, dan pengangguran — kamus rata akan salah pada "Inflasi
naik jadi 4,2%", dan salahnya sistematis. Jadi kata arah dipasangkan dengan
pokok di dekatnya, lalu pokok itu yang menentukan tandanya; ditambah frasa
bertanda tetap ("gagal bayar", "insentif") dan pembalik negasi ("BI batal
menaikkan suku bunga").

Pada data 9–10 Sep 2026, sekitar tiga perempat peristiwa keluar **netral**, dan
itu jawaban yang benar: pengumuman jadwal, agenda rapat, dan pernyataan pejabat
memang tidak berarah. Netral tidak diberi lencana sama sekali — menandai semua
berarti tidak menandai apa pun. Status ini **tidak** ikut memilih atau
mengurutkan apa pun; berita buruk bukan berita yang kurang penting. Lencananya
menyimpan frasa pemicu di `title`, jadi label yang terasa meleset bisa
ditelusuri ke barisnya di berkas itu.

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
