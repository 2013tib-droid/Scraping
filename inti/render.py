"""
render.py — ubah peristiwa terpilih jadi satu halaman HTML statis.

Halaman ini kanal utama (ARSITEKTUR.md §16), jadi keterbacaannya bagian dari
fungsinya, bukan hiasan. Keputusan tampilannya:

- **Satu kolom, lebar ~44rem.** Baris terlalu panjang membuat mata kehilangan
  awal baris berikutnya; ini panjang yang nyaman dibaca sambil berdiri di dapur.
- **Serif untuk judul berita, sans untuk metadata.** Membedakan "isi" dari
  "keterangan" tanpa perlu garis atau kotak.
- **Terang/gelap ikut setelan perangkat.** Dibaca jam 5 pagi; memaksa latar putih
  menyilaukan.
- **Tanpa JavaScript, tanpa aset eksternal.** Satu berkas yang bisa dibuka dari
  mana saja dan tetap terbaca sepuluh tahun lagi.
- **Waktu selalu WIB** — satu-satunya tempat konversi dari UTC terjadi (§15 #9).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape

WIB = timezone(timedelta(hours=7), "WIB")

BULAN = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember")

JUDUL_BAGIAN = {
    "makro": "Makro &amp; Kebijakan",
    "pasar": "Pasar &amp; Emiten",
    "politik": "Politik &amp; Sosial",
    "global": "Global",
}

GAYA = """
:root {
  --bg: #fbfaf7; --teks: #1a1a18; --redup: #6b6a66; --garis: #e2e0da;
  --tautan: #8a3324; --sorot: #f3f0e9;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #16171a; --teks: #e8e6e1; --redup: #94938e; --garis: #2c2e33;
    --tautan: #e0a08a; --sorot: #1e2024;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 2.2rem 1.2rem 4rem;
  background: var(--bg); color: var(--teks);
  font: 16px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  -webkit-text-size-adjust: 100%;
}
.bungkus { max-width: 44rem; margin: 0 auto; }
header { border-bottom: 2px solid var(--teks); padding-bottom: .8rem; margin-bottom: 2rem; }
h1 { font: 700 1.5rem/1.2 Georgia, "Iowan Old Style", serif; margin: 0 0 .3rem; letter-spacing: -.01em; }
.tanggal { color: var(--redup); font-size: .85rem; }
h2 {
  font: 600 .78rem/1 system-ui, sans-serif; text-transform: uppercase;
  letter-spacing: .09em; color: var(--redup);
  margin: 2.6rem 0 1rem; padding-bottom: .5rem; border-bottom: 1px solid var(--garis);
}
section:first-of-type h2 { margin-top: 0; }
article { margin: 0 0 1.6rem; }
article h3 { font: 600 1.08rem/1.35 Georgia, "Iowan Old Style", serif; margin: 0 0 .25rem; }
article h3 a { color: var(--teks); text-decoration: none; }
article h3 a:hover { color: var(--tautan); text-decoration: underline; text-underline-offset: 2px; }
.meta { font-size: .78rem; color: var(--redup); margin-bottom: .35rem; }
.meta .n { color: var(--tautan); font-weight: 600; }
.ringkas { margin: 0; color: var(--teks); opacity: .88; font-size: .93rem; }
.juga { margin: .3rem 0 0; font-size: .76rem; color: var(--redup); }
.juga a { color: var(--redup); }
footer {
  margin-top: 3.5rem; padding-top: 1rem; border-top: 1px solid var(--garis);
  font-size: .78rem; color: var(--redup);
}
footer a { color: var(--tautan); }
.kosong { color: var(--redup); font-style: italic; }
"""


def _tanggal_panjang(d: datetime) -> str:
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def _jam(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    # Tersimpan sebagai UTC polos; di sinilah satu-satunya konversi ke WIB.
    return dt.replace(tzinfo=timezone.utc).astimezone(WIB).strftime("%H:%M")


def _artikel(p) -> str:
    liputan = ""
    if p.juga:
        tautan = ", ".join(
            f'<a href="{escape(u)}">{escape(d)}</a>' for d, u in p.juga[:6]
        )
        liputan = f'<p class="juga">juga di {tautan}</p>'

    jumlah = ""
    if p.jumlah_media > 1:
        jumlah = f'<span class="n">{p.jumlah_media} media</span> · '

    ringkas = f'<p class="ringkas">{escape(p.ringkasan)}</p>' if p.ringkasan else ""

    return f"""      <article>
        <h3><a href="{escape(p.url)}">{escape(p.judul)}</a></h3>
        <p class="meta">{jumlah}{escape(p.domain)} · {_jam(p.waktu_terbit)} WIB</p>
        {ringkas}
        {liputan}
      </article>"""


def halaman(tanggal: datetime, bagian: dict[str, list], jumlah_sumber: int,
            total_dipertimbangkan: int) -> str:
    isi: list[str] = []
    for kunci, judul in JUDUL_BAGIAN.items():
        peristiwa = bagian.get(kunci) or []
        if not peristiwa:
            continue
        blok = "\n".join(_artikel(p) for p in peristiwa)
        isi.append(f"    <section>\n      <h2>{judul}</h2>\n{blok}\n    </section>")

    badan = "\n".join(isi) or '    <p class="kosong">Tidak ada berita di jendela ini.</p>'
    ditampilkan = sum(len(v) for v in bagian.values())

    return f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ringkas Pagi — {_tanggal_panjang(tanggal)}</title>
<style>{GAYA}</style>
</head>
<body>
  <div class="bungkus">
    <header>
      <h1>Ringkas Pagi</h1>
      <div class="tanggal">{_tanggal_panjang(tanggal)} · berita 24 jam terakhir sampai 05:00 WIB</div>
    </header>
{badan}
    <footer>
      {ditampilkan} peristiwa dipilih dari {total_dipertimbangkan} artikel,
      {jumlah_sumber} sumber. Disusun {_jam(datetime.now(timezone.utc).replace(tzinfo=None))} WIB.
      <br>Tautan menuju penerbit aslinya. Kutipan pendek untuk keperluan baca pribadi.
    </footer>
  </div>
</body>
</html>
"""
