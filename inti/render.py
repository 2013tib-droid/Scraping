"""
render.py — ubah peristiwa terpilih jadi satu halaman HTML statis.

Halaman ini kanal utama (ARSITEKTUR.md §16), jadi keterbacaannya bagian dari
fungsinya, bukan hiasan. Keputusan tampilannya:

- **Hierarki, bukan daftar rata.** Item pertama tiap bagian sudah yang paling
  banyak diliput (`alur/edisi.py`), jadi ia ditampilkan sebagai sorotan: judul
  lebih besar, ringkasan penuh, bidang aksen. Sisanya bernomor dan rapat, supaya
  mata tahu mana yang wajib dan mana yang boleh dilewati.
- **Navigasi lengket di atas.** Empat bagian dengan jumlah itemnya; satu ketuk
  langsung ke Pasar tanpa menggulir Makro. Murni CSS, tanpa JavaScript.
- **Warna aksen per bagian.** Makro, Pasar, Politik, Global masing-masing punya
  warna; nomor, garis, dan tautan bagian mengikutinya. Membedakan bagian saat
  digulir cepat tanpa harus membaca judul bagiannya.
- **Panjang baris dijaga tetap, lebarnya yang berubah.** Sampai ~1.120 px:
  satu kolom 42rem, panjang baris yang nyaman dibaca sambil berdiri di dapur.
  Di atas itu wadahnya melebar ke 80% layar **dan** isinya pecah jadi dua kolom
  — melebar tanpa memecah cuma menghasilkan baris ~200 karakter, yang membuat
  mata kehilangan jejak saat kembali ke awal baris berikutnya. Serif untuk
  judul, membedakan "isi" dari "keterangan".
- **Terang/gelap ikut setelan perangkat.** Dibaca jam 5 pagi; memaksa latar putih
  menyilaukan.
- **Tanpa JavaScript.** Satu berkas yang bisa dibuka dari mana saja.
- **Gambar hanya di kartu sorotan, dan hanya itu satu-satunya aset eksternal.**
  Item bernomor tetap teks murni — di sana kerapatannya yang berguna. Batas ini
  bukan selera: 35 thumbnail hotlink berarti ~1,5 MB dan 35 permintaan ke belasan
  domain untuk halaman yang sekarang 62 KB; sepuluh kartu sorotan menahannya di
  ~300 KB. Menyimpan gambarnya sendiri ke repo lebih buruk lagi — ~440 MB
  setahun yang tidak bisa dihapus dari riwayat git, persis yang dihindari §5.
  Harganya dibayar di arsip: URL gambar penerbit berumur bulanan sementara
  `docs/arsip/` permanen, jadi edisi lama akan kehilangan fotonya. Karena itu
  `alt` sengaja kosong dan tiap gambar duduk di atas bidang berwarna — yang mati
  meninggalkan kotak sunyi, bukan ikon rusak, dan teksnya tetap lengkap tanpa
  gambar itu sejak awal.
- **Waktu selalu WIB** — satu-satunya tempat konversi dari UTC terjadi (§15 #9).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from html import escape

WIB = timezone(timedelta(hours=7), "WIB")

BULAN = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember")
HARI = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")

# Urutan di sini = urutan di halaman. "utama" hanya ada kalau penilai dampak
# (inti/dampak.py) aktif; di dalamnya semua item tampil sebagai kartu.
BAGIAN = {
    "utama": ("Penting Pagi Ini", "dampak tinggi, lintas bagian"),
    "makro": ("Makro &amp; Kebijakan", "BPS, BI, APBN, pajak, kurs, regulasi"),
    "pasar": ("Pasar &amp; Emiten", "IHSG, aksi korporasi, laporan keuangan"),
    "politik": ("Politik &amp; Sosial", "yang berpotensi menggerakkan pasar"),
    "global": ("Global", "The Fed, komoditas, geopolitik"),
}

# Dateline di awal ringkasan: "REPUBLIKA.CO.ID, JAKARTA — ", "Jakarta, CNBC
# Indonesia - ", "Bisnis.com, JAKARTA — ". Informasinya sudah ada di baris meta
# (domain), jadi di sini hanya memakan dua baris pertama yang paling dibaca.
DATELINE = re.compile(r"^(?:[A-Z][\w.]*,?\s+){1,6}[—–-]\s+")

GAYA = """
:root {
  --bg: #f7f5f0; --kertas: #fffdf9; --teks: #1c1b18; --redup: #6f6c65;
  --garis: #e4e0d7; --sorot: #efebe2; --tautan: #8a3324;
  --utama: #a5700a; --makro: #b5462f; --pasar: #2e7d5b; --politik: #3b5fa8; --global: #7a4fa0;
  --naik: #1f7a4d; --turun: #b3261e;
  --bayang: 0 1px 2px rgba(30,25,15,.06), 0 6px 20px -8px rgba(30,25,15,.12);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #131417; --kertas: #1b1c20; --teks: #e9e6e0; --redup: #9a978f;
    --garis: #2b2d33; --sorot: #22242a; --tautan: #e8a88f;
    --utama: #e9c060; --makro: #e58a72; --pasar: #6cc59c; --politik: #8fabe8; --global: #bc9be0;
    --naik: #6ecf9c; --turun: #f08a80;
    --bayang: 0 1px 2px rgba(0,0,0,.4), 0 8px 24px -8px rgba(0,0,0,.6);
  }
}
* { box-sizing: border-box; }
html { scroll-padding-top: 3.4rem; scroll-behavior: smooth; }
body {
  margin: 0; padding: 0 0 4rem;
  background: var(--bg); color: var(--teks);
  font: 16px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  -webkit-text-size-adjust: 100%; overflow-wrap: anywhere;
}
a { color: inherit; }
/* Lebar dipegang satu variabel supaya wadah dan navigasi lengket tidak pernah
   berbeda — kalau keduanya bergeser sendiri-sendiri, tombol navigasi berhenti
   sejajar dengan teks di bawahnya. */
:root { --lebar: 42rem; }
.bungkus { max-width: var(--lebar); margin: 0 auto; padding: 0 1.1rem; }

/* --- masthead ------------------------------------------------------------ */
.kepala { padding: 2.4rem 0 1.4rem; }
.merek {
  font: 600 .74rem/1 system-ui, sans-serif; letter-spacing: .16em;
  text-transform: uppercase; color: var(--redup);
}
.kepala h1 {
  font: 700 clamp(1.9rem, 6vw, 2.5rem)/1.1 "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  margin: .45rem 0 .6rem; letter-spacing: -.015em;
}
.kepala h1 small { display: block; font-size: .5em; font-weight: 400; color: var(--redup); margin-top: .2rem; letter-spacing: 0; }
.angka { display: flex; flex-wrap: wrap; gap: .45rem; font-size: .8rem; color: var(--redup); }
.angka span { background: var(--sorot); border-radius: 999px; padding: .2rem .7rem; }
.angka b { color: var(--teks); font-weight: 600; }

/* --- navigasi lengket ----------------------------------------------------- */
.nav {
  position: sticky; top: 0; z-index: 10;
  background: color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--garis);
}
.nav ul {
  list-style: none; margin: 0 auto; padding: .5rem 1.1rem; max-width: var(--lebar);
  display: flex; gap: .35rem; overflow-x: auto; scrollbar-width: none;
}
.nav ul::-webkit-scrollbar { display: none; }
.nav a {
  display: inline-flex; align-items: center; gap: .4rem; white-space: nowrap;
  text-decoration: none; font-size: .8rem; font-weight: 600;
  padding: .35rem .75rem; border-radius: 999px; border: 1px solid var(--garis);
  background: var(--kertas);
}
.nav a i { width: .5rem; height: .5rem; border-radius: 50%; background: var(--warna); }
.nav a em { font-style: normal; font-weight: 500; color: var(--redup); }

/* --- bagian --------------------------------------------------------------- */
section { --warna: var(--makro); margin-top: 2.6rem; }
section.utama { --warna: var(--utama); }
section.utama .sorotan { margin-bottom: .8rem; }
section.pasar { --warna: var(--pasar); }
section.politik { --warna: var(--politik); }
section.global { --warna: var(--global); }
.judul-bagian { display: flex; align-items: baseline; gap: .7rem; margin-bottom: 1rem; }
.judul-bagian::before { content: ""; width: .35rem; height: 1.3rem; background: var(--warna); border-radius: 2px; align-self: center; }
.judul-bagian h2 { font: 700 1.15rem/1.2 system-ui, sans-serif; margin: 0; letter-spacing: -.01em; }
.judul-bagian small { font-size: .78rem; color: var(--redup); }

/* --- sorotan (item pertama) ------------------------------------------------ */
.sorotan {
  background: var(--kertas); border-radius: 14px; padding: 1.1rem 1.2rem 1rem;
  border-left: 4px solid var(--warna); box-shadow: var(--bayang); margin-bottom: .6rem;
}
/* Teks dan gambar berdampingan; gambar di kolom kanan tapi urutan DOM-nya
   sesudah teks, jadi judul tetap yang pertama dibaca pembaca layar. Lebar
   kolomnya tetap, sehingga tidak ada pergeseran tata letak saat gambar masuk —
   dan tidak ada bedanya kalau gambar itu tidak pernah datang. */
.sorotan.bergambar { display: grid; grid-template-columns: 1fr auto; column-gap: 1rem; align-items: start; }
.sorotan .isi { min-width: 0; }
.thumb {
  width: 6.5rem; height: 6.5rem; border-radius: 10px; object-fit: cover;
  display: block; background: var(--sorot); border: 1px solid var(--garis);
}
@media (max-width: 24rem) {
  .sorotan.bergambar { column-gap: .7rem; }
  .thumb { width: 4.5rem; height: 4.5rem; }
}
.sorotan h3 {
  font: 700 clamp(1.25rem, 4.6vw, 1.5rem)/1.25 "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  margin: 0 0 .5rem; letter-spacing: -.012em;
}
.sorotan .ringkas { font-size: .96rem; opacity: 1; }

/* --- item biasa ----------------------------------------------------------- */
.daftar { list-style: none; margin: 0; padding: 0; }
.daftar li {
  display: grid; grid-template-columns: 1.6rem 1fr; column-gap: .6rem;
  padding: .85rem 0; border-bottom: 1px solid var(--garis);
}
.daftar li:last-child { border-bottom: 0; }
.nomor {
  font: 700 .8rem/1.9 ui-monospace, "SF Mono", Consolas, monospace;
  color: var(--warna); padding-top: .05rem;
}
.daftar h3 {
  font: 600 1.06rem/1.35 "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  margin: 0 0 .25rem;
}
h3 a { text-decoration: none; }
h3 a:hover { color: var(--tautan); text-decoration: underline; text-underline-offset: 3px; }

/* --- meta, ringkasan, liputan --------------------------------------------- */
.meta {
  display: flex; flex-wrap: wrap; align-items: center; gap: .3rem .55rem;
  font-size: .76rem; color: var(--redup); margin: 0 0 .4rem;
}
.sumber { font-weight: 600; color: var(--teks); }
.media {
  font-weight: 700; color: var(--warna); background: color-mix(in srgb, var(--warna) 12%, transparent);
  padding: .05rem .5rem; border-radius: 999px;
}
.tinggi {
  font-weight: 700; color: var(--utama); background: color-mix(in srgb, var(--utama) 14%, transparent);
  padding: .05rem .5rem; border-radius: 999px;
}
/* Status arah. Bentuknya ikut membedakan, bukan hanya warna: panah naik/turun
   tetap terbaca oleh mata yang tidak membedakan merah-hijau. Netral tidak
   diberi lencana sama sekali — sebagian besar berita netral, dan menandai
   semuanya berarti tidak menandai apa pun. */
.arah {
  font-weight: 700; padding: .05rem .5rem; border-radius: 999px;
  color: var(--nada); background: color-mix(in srgb, var(--nada) 14%, transparent);
}
.arah.positif { --nada: var(--naik); }
.arah.negatif { --nada: var(--turun); }
.alasan {
  margin: 0 0 .4rem; font-size: .88rem; font-weight: 600; color: var(--warna);
  padding-left: .6rem; border-left: 2px solid var(--warna);
}
.ringkas { margin: 0; font-size: .92rem; opacity: .86; }
.juga { display: flex; flex-wrap: wrap; gap: .3rem; align-items: center; margin: .5rem 0 0; font-size: .72rem; color: var(--redup); }
.juga a {
  text-decoration: none; background: var(--sorot); border-radius: 6px;
  padding: .1rem .45rem; color: var(--teks); opacity: .8;
}
.juga a:hover { opacity: 1; }
.lagi { color: var(--redup); }

/* --- layar lebar ----------------------------------------------------------- */
/* Wadahnya melebar ke 80% viewport, tapi isinya pecah jadi dua kolom di titik
   yang sama. Keduanya satu paket, bukan dua keputusan: satu kolom selebar
   1.500 px berarti baris ~200 karakter, dan mata kehilangan jejak saat kembali
   ke awal baris berikutnya. Dipecah dua, tiap kolom ~700 px — senyaman versi
   sempit, tapi layarnya terpakai.

   Ambangnya 70rem (~1.120 px), bukan 1.024: pada laptop 1.024 px dua kolom
   dari 80vw tinggal ~390 px masing-masing, dan kartu sorotan hanya menyisakan
   ~260 px untuk teks setelah gambarnya. Di bawah ambang ini semuanya tetap
   satu kolom 42rem seperti sebelumnya — ponsel dan tablet tidak tersentuh. */
@media (min-width: 70rem) {
  :root { --lebar: min(80vw, 96rem); }

  /* Blok utama: enam kartu berdampingan dua-dua, bukan menumpuk sendirian. */
  section.utama .kartu {
    display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .9rem;
  }
  section.utama .sorotan { margin-bottom: 0; }

  /* Bagian lain: sorotan di kiri, daftar bernomor di kanan — judul bagiannya
     membentang di atas keduanya. */
  section:not(.utama) {
    display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
    column-gap: 3rem; align-items: start;
  }
  section:not(.utama) .judul-bagian { grid-column: 1 / -1; }
  section:not(.utama) .sorotan { margin-bottom: 0; }
  .daftar li:first-child { padding-top: 0; }

  /* Ruang yang bertambah dipakai gambar, bukan dibiarkan jadi margin. */
  .thumb { width: 8rem; height: 8rem; }
}

/* --- kaki ------------------------------------------------------------------ */
footer {
  margin-top: 3.5rem; padding-top: 1.2rem; border-top: 1px solid var(--garis);
  font-size: .78rem; color: var(--redup); line-height: 1.7;
}
footer a { color: var(--tautan); }
.kosong { color: var(--redup); font-style: italic; padding: 3rem 0; text-align: center; }
"""


def _tanggal_panjang(d: datetime) -> str:
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def _jam(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    # Tersimpan sebagai UTC polos; di sinilah satu-satunya konversi ke WIB.
    return dt.replace(tzinfo=timezone.utc).astimezone(WIB).strftime("%H:%M")


def _ringkasan(teks: str | None) -> str:
    if not teks:
        return ""
    return f'<p class="ringkas">{escape(DATELINE.sub("", teks, count=1))}</p>'


def _alasan(p) -> str:
    """Satu kalimat "kenapa penting" dari penilai dampak, kalau ada."""
    alasan = getattr(p, "alasan", None)
    return f'<p class="alasan">{escape(alasan)}</p>' if alasan else ""


# Lencana status arah (inti/sentimen.py). Netral sengaja tidak punya lencana.
ARAH = {"positif": ("positif", "↑"), "negatif": ("negatif", "↓")}


def _arah(p) -> str:
    """Lencana positif/negatif, dengan frasa pemicunya sebagai `title` — supaya
    label yang terasa keliru bisa langsung ditelusuri ke barisnya di
    inti/sentimen.py, bukan cuma dicurigai."""
    label = ARAH.get(getattr(p, "sentimen", None) or "")
    if not label:
        return ""
    nama, panah = label
    pemicu = getattr(p, "pemicu", None)
    judul = f' title="{escape(pemicu)}"' if pemicu else ""
    return f'<span class="arah {nama}"{judul}>{panah} {nama}</span>'


def _meta(p) -> str:
    bagian = []
    if getattr(p, "dampak", None) == 3:
        bagian.append('<span class="tinggi">dampak tinggi</span>')
    if arah := _arah(p):
        bagian.append(arah)
    if p.jumlah_media > 1:
        bagian.append(f'<span class="media">{p.jumlah_media} media</span>')
    bagian.append(f'<span class="sumber">{escape(p.domain)}</span>')
    bagian.append(f"<span>{_jam(p.waktu_terbit)} WIB</span>")
    return '<p class="meta">' + " ".join(bagian) + "</p>"


def _juga(p) -> str:
    if not p.juga:
        return ""
    tautan = "".join(
        f'<a href="{escape(u)}">{escape(d)}</a>' for d, u in p.juga[:5]
    )
    sisa = len(p.juga) - 5
    lagi = f'<span class="lagi">+{sisa} lagi</span>' if sisa > 0 else ""
    return f'<p class="juga"><span>juga di</span>{tautan}{lagi}</p>'


def _thumb(p) -> str:
    """Thumbnail kartu sorotan, kalau feed penerbitnya memberi satu.

    `alt` kosong disengaja: judulnya sudah mengatakan segalanya, jadi gambar ini
    dekoratif. Itu sekaligus membuat gambar yang mati — dan suatu saat semuanya
    akan mati — tidak meninggalkan teks alternatif yang menggantung.

    `loading="lazy"` membuat kartu di bawah lipatan tidak diambil sampai
    digulir; pada halaman yang dibuka jam 5 pagi di jaringan seluler, itu
    selisih antara mengunduh sepuluh gambar dan mengunduh dua.
    """
    url = getattr(p, "gambar", None)
    if not url:
        return ""
    return (
        f'<img class="thumb" src="{escape(url)}" alt="" loading="lazy" '
        f'decoding="async" width="208" height="208">'
    )


def _sorotan(p) -> str:
    thumb = _thumb(p)
    kelas = "sorotan bergambar" if thumb else "sorotan"
    return f"""      <article class="{kelas}">
        <div class="isi">
          <h3><a href="{escape(p.url)}">{escape(p.judul)}</a></h3>
          {_meta(p)}
          {_alasan(p)}
          {_ringkasan(p.ringkasan)}
          {_juga(p)}
        </div>
        {thumb}
      </article>"""


def _item(nomor: int, p) -> str:
    return f"""        <li>
          <span class="nomor">{nomor:02d}</span>
          <div>
            <h3><a href="{escape(p.url)}">{escape(p.judul)}</a></h3>
            {_meta(p)}
            {_alasan(p)}
            {_ringkasan(p.ringkasan)}
            {_juga(p)}
          </div>
        </li>"""


def _bagian(kunci: str, peristiwa: list) -> str:
    judul, keterangan = BAGIAN[kunci]
    if kunci == "utama":
        # Semuanya berdampak tinggi; tidak ada yang "sisa". Kartunya dibungkus
        # satu elemen supaya di layar lebar bisa dijajarkan dua-dua tanpa ikut
        # menyeret judul bagiannya ke dalam grid.
        sorotan = "\n".join(_sorotan(p) for p in peristiwa)
        return f"""    <section class="{kunci}" id="{kunci}">
      <div class="judul-bagian"><h2>{judul}</h2><small>{keterangan}</small></div>
      <div class="kartu">
{sorotan}
      </div>
    </section>"""
    sorotan = _sorotan(peristiwa[0])
    sisa = ""
    if len(peristiwa) > 1:
        baris = "\n".join(_item(i, p) for i, p in enumerate(peristiwa[1:], start=2))
        sisa = f'\n      <ol class="daftar">\n{baris}\n      </ol>'
    return f"""    <section class="{kunci}" id="{kunci}">
      <div class="judul-bagian"><h2>{judul}</h2><small>{keterangan}</small></div>
{sorotan}{sisa}
    </section>"""


def _nav(bagian: dict[str, list]) -> str:
    tombol = "".join(
        f'<li><a href="#{k}" style="--warna: var(--{k})"><i></i>{BAGIAN[k][0]}'
        f"<em>{len(bagian[k])}</em></a></li>"
        for k in BAGIAN
        if bagian.get(k)
    )
    return f'  <nav class="nav"><ul>{tombol}</ul></nav>' if tombol else ""


def halaman(
    tanggal: datetime,
    bagian: dict[str, list],
    jumlah_sumber: int,
    total_dipertimbangkan: int,
    sebelumnya: str | None = None,
) -> str:
    """Susun halaman. `sebelumnya` = path relatif edisi sebelumnya, kalau ada."""
    isi = [_bagian(k, bagian[k]) for k in BAGIAN if bagian.get(k)]
    badan = "\n".join(isi) or '    <p class="kosong">Tidak ada berita di jendela ini.</p>'
    ditampilkan = sum(len(v) for v in bagian.values())
    hari = HARI[tanggal.weekday()]
    disusun = _jam(datetime.now(timezone.utc).replace(tzinfo=None))
    tautan_arsip = (
        f' · <a href="{escape(sebelumnya)}">Edisi sebelumnya</a>' if sebelumnya else ""
    )

    return f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Ringkas Pagi — {_tanggal_panjang(tanggal)}</title>
<style>{GAYA}</style>
</head>
<body>
  <div class="bungkus">
    <header class="kepala">
      <div class="merek">Ringkas Pagi</div>
      <h1>{hari}, {_tanggal_panjang(tanggal)}
        <small>Berita 24 jam terakhir, sampai 05:00 WIB</small></h1>
      <div class="angka">
        <span><b>{ditampilkan}</b> peristiwa</span>
        <span>dari <b>{total_dipertimbangkan}</b> artikel</span>
        <span><b>{jumlah_sumber}</b> sumber</span>
      </div>
    </header>
  </div>
{_nav(bagian)}
  <div class="bungkus">
{badan}
    <footer>
      Disusun {disusun} WIB{tautan_arsip}.
      <br>Tautan menuju penerbit aslinya. Kutipan pendek untuk keperluan baca pribadi.
    </footer>
  </div>
</body>
</html>
"""
