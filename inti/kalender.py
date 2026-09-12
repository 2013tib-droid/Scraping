"""
kalender.py — halaman arsip: satu kalender, tinggal pilih tanggalnya.

Sampai sekarang arsip hanya bisa ditelusuri lewat rantai "Edisi sebelumnya" di
kaki halaman: untuk membaca edisi seminggu lalu, tujuh kali klik. Kalender
membuatnya satu klik, dan sekaligus menjawab pertanyaan yang tidak bisa dijawab
rantai — tanggal berapa saja yang ada edisinya.

Tiga keputusan yang membentuk berkas ini:

- **Satu halaman, bukan kalender di tiap edisi.** Menempelkan kalender ke tiap
  halaman berarti tiap edisi baru harus menulis ulang kalender di semua edisi
  lama supaya tanggal baru ikut muncul — 365 berkas berubah tiap hari, dan
  riwayat git menyimpan semuanya (§5). Satu halaman yang di-render ulang tiap
  build hanya mengubah satu berkas, dan tidak pernah basi.
- **Daftar tanggalnya dari nama berkas, bukan dari basis data.** `docs/arsip/`
  adalah arsip yang sesungguhnya — state DuckDB hidup di cache Actions dan boleh
  tergusur (§5). Kalender yang dibangun dari cache akan menampilkan tanggal yang
  halamannya sudah tidak ada, atau sebaliknya.
- **Tanpa JavaScript, seperti halaman edisinya** (inti/render.py). Kalender
  adalah tabel, dan tabel sudah bisa dirender browser sejak 1996.

Alamatnya `docs/arsip/index.html`, jadi URL-nya `/arsip/` — cukup pendek untuk
di-bookmark sendiri, dan tidak menabrak `docs/arsip/YYYY-MM-DD.html` yang sudah
ada.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from html import escape
from pathlib import Path

from inti.render import BULAN, GAYA

NAMA = "index.html"

# Senin di kolom pertama — sama dengan kalender cetak Indonesia.
_KALENDER = calendar.Calendar(firstweekday=calendar.MONDAY)

# Dua huruf, bukan satu: "S" berlaku untuk Senin, Selasa, dan Sabtu sekaligus.
# Nama panjangnya tetap ada di `abbr` untuk pembaca layar.
HARI_SINGKAT = (
    ("Sn", "Senin"), ("Sl", "Selasa"), ("Rb", "Rabu"), ("Km", "Kamis"),
    ("Jm", "Jumat"), ("Sb", "Sabtu"), ("Mg", "Minggu"),
)

# Pintasan di atas kalender. Ini yang sebenarnya dipakai sehari-hari — "berita
# tiga hari lalu" jarang dipikirkan sebagai tanggal, dan menghitung mundur di
# kepala justru bagian yang bikin malas. Dihitung dari edisi terbaru, bukan dari
# hari ini: kalau cron gagal semalam, "kemarin" tetap menunjuk ke edisi yang ada.
PINTASAN = ((1, "Kemarin"), (3, "3 hari lalu"), (7, "Seminggu lalu"),
            (14, "2 minggu lalu"), (30, "Sebulan lalu"))

GAYA_KALENDER = """
/* Merek di masthead jadi jalan pulang ke edisi terbaru; garis bawahnya baru
   muncul saat disentuh, supaya kepala halaman tetap terbaca sebagai kepala
   halaman, bukan sebagai tautan. */
.merek a { text-decoration: none; }
.merek a:hover { color: var(--tautan); }
.pintasan { display: flex; flex-wrap: wrap; gap: .45rem; margin: 0 0 2.2rem; }
.pintasan a {
  text-decoration: none; font-size: .82rem; font-weight: 600;
  padding: .4rem .85rem; border-radius: 999px;
  border: 1px solid var(--garis); background: var(--kertas);
}
.pintasan a:hover { border-color: var(--utama); color: var(--utama); }
.pintasan a b { font-weight: 400; color: var(--redup); }

/* Satu kolom di ponsel, sebanyak yang muat di layar lebar. `auto-fill` dengan
   batas 15rem: di bawah itu angka tanggalnya mulai bertumpuk dengan sel
   sebelahnya. */
.bulan-bulan { display: grid; grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr)); gap: 1.2rem; }
/* Kartunya div, bukan <table>: dengan `border-collapse: collapse` padding tabel
   diabaikan, dan caption dirender di luar kotak tabel — jadi latar dan bayangan
   kartu berhenti tepat sebelum nama bulannya. */
.bulan {
  background: var(--kertas); border-radius: 14px; box-shadow: var(--bayang);
  border-left: 4px solid var(--utama); padding: .8rem .9rem 1rem;
}
table { width: 100%; border-collapse: separate; border-spacing: 0; }
caption {
  text-align: left; font: 700 1rem/1.2 system-ui, sans-serif;
  padding: .1rem .15rem .7rem; letter-spacing: -.01em;
}
caption em { font-style: normal; font-weight: 500; font-size: .78rem; color: var(--redup); }
th {
  font: 600 .68rem/1 system-ui, sans-serif; color: var(--redup);
  text-transform: uppercase; letter-spacing: .06em; padding-bottom: .45rem; font-weight: 600;
}
th abbr { text-decoration: none; }
td { text-align: center; padding: .1rem; }
/* Tanggal yang ada edisinya bisa diketuk; yang tidak tetap tampil supaya
   kalendernya terbaca sebagai kalender, tapi redup dan tanpa kotak. */
td a, td span {
  display: block; padding: .45rem 0; border-radius: 9px;
  font: 600 .92rem/1.2 system-ui, sans-serif;
}
td a {
  text-decoration: none; color: var(--teks);
  background: color-mix(in srgb, var(--utama) 14%, transparent);
}
td a:hover, td a:focus { background: var(--utama); color: var(--bg); }
td a.terbaru { background: var(--utama); color: var(--bg); }
td span { color: var(--redup); opacity: .45; font-weight: 400; }
"""


def tanggal_tersedia(arsip: Path) -> list[date]:
    """Tanggal edisi yang halamannya benar-benar ada, urut dari yang terlama.

    Nama berkas yang bukan tanggal — `index.html` ini sendiri, misalnya —
    dilewati tanpa suara: itu satu-satunya cara membedakannya, dan daftar
    pengecualian yang harus dirawat manual lebih mudah lupa daripada ini.
    """
    if not arsip.is_dir():
        return []
    hasil = []
    for berkas in arsip.glob("*.html"):
        try:
            hasil.append(date.fromisoformat(berkas.stem))
        except ValueError:
            continue
    return sorted(hasil)


def _tanggal_panjang(d: date) -> str:
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def _sel(hari: date, bulan: int, tersedia: set[date], terbaru: date) -> str:
    if hari.month != bulan:
        # Sel bocoran dari bulan sebelah — dikosongkan, bukan diberi angka.
        # Tanggal yang sama muncul dua kali di dua kartu bulan membuat kalender
        # yang seharusnya dipindai sekilas jadi perlu dibaca.
        return "<td></td>"
    if hari not in tersedia:
        return f"<td><span>{hari.day}</span></td>"
    kelas = ' class="terbaru"' if hari == terbaru else ""
    judul = f"Edisi {_tanggal_panjang(hari)}"
    return (
        f'<td><a href="{hari:%Y-%m-%d}.html"{kelas} title="{escape(judul)}">'
        f"{hari.day}</a></td>"
    )


def _bulan(tahun: int, bulan: int, tersedia: set[date], terbaru: date) -> str:
    jumlah = sum(1 for d in tersedia if (d.year, d.month) == (tahun, bulan))
    kepala = "".join(
        f'<th scope="col"><abbr title="{panjang}">{pendek}</abbr></th>'
        for pendek, panjang in HARI_SINGKAT
    )
    baris = "\n".join(
        "            <tr>"
        + "".join(_sel(h, bulan, tersedia, terbaru) for h in minggu)
        + "</tr>"
        for minggu in _KALENDER.monthdatescalendar(tahun, bulan)
    )
    return f"""      <div class="bulan">
        <table>
          <caption>{BULAN[bulan - 1]} {tahun} <em>{jumlah} edisi</em></caption>
          <thead><tr>{kepala}</tr></thead>
          <tbody>
{baris}
          </tbody>
        </table>
      </div>"""


def _pintasan(tersedia: set[date], terbaru: date) -> str:
    """Hanya pintasan yang halamannya ada. Tautan mati lebih buruk daripada
    tidak ada tautan — aturan yang sama dipakai "Edisi sebelumnya" di kaki
    halaman edisi."""
    tombol = ""
    for jarak, label in PINTASAN:
        d = terbaru - timedelta(days=jarak)
        if d in tersedia:
            tombol += (
                f'<a href="{d:%Y-%m-%d}.html">{label} '
                f"<b>{d.day} {BULAN[d.month - 1][:3]}</b></a>"
            )
    return f'    <div class="pintasan">{tombol}</div>\n' if tombol else ""


def halaman(tanggal: list[date]) -> str:
    """Susun halaman arsip dari daftar tanggal yang ada edisinya."""
    tersedia = set(tanggal)
    if tanggal:
        terbaru, terlama = max(tanggal), min(tanggal)
        keterangan = (
            f"{len(tanggal)} edisi, {_tanggal_panjang(terlama)} – "
            f"{_tanggal_panjang(terbaru)}"
        )
        # Bulan terbaru di atas: yang dicari hampir selalu beberapa hari
        # terakhir, dan menggulir ke bawah untuk itu tiap kali adalah pajak
        # harian yang dibayar demi urutan kronologis yang tidak ada gunanya di
        # sini.
        bulan = sorted({(d.year, d.month) for d in tanggal}, reverse=True)
        kartu = "\n".join(_bulan(t, b, tersedia, terbaru) for t, b in bulan)
        isi = f'    <div class="bulan-bulan">\n{kartu}\n    </div>'
        pintasan = _pintasan(tersedia, terbaru)
    else:
        keterangan = "belum ada edisi tersimpan"
        isi = '    <p class="kosong">Belum ada edisi di arsip.</p>'
        pintasan = ""

    return f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Arsip — Ringkas Pagi</title>
<style>{GAYA}{GAYA_KALENDER}</style>
</head>
<body>
  <div class="bungkus">
    <header class="kepala">
      <div class="merek"><a href="../index.html">Ringkas Pagi</a></div>
      <h1>Arsip edisi
        <small>{escape(keterangan)}</small></h1>
    </header>
{pintasan}{isi}
    <footer>
      <a href="../index.html">Edisi terbaru</a> · tiap edisi memuat berita 24 jam
      terakhir sampai 05:00 WIB pada tanggal itu.
    </footer>
  </div>
</body>
</html>
"""


def tulis(akar: Path) -> Path:
    """Render ulang halaman arsip dari isi `akar/arsip` apa adanya.

    Dipanggil tiap kali edisi ditulis (`alur/edisi.py`), jadi tanggal baru
    muncul di kalender pada run yang sama — dan kalender tidak pernah
    menjanjikan halaman yang tidak ada.
    """
    arsip = akar / "arsip"
    arsip.mkdir(parents=True, exist_ok=True)
    berkas = arsip / NAMA
    berkas.write_text(halaman(tanggal_tersedia(arsip)), encoding="utf-8")
    return berkas
