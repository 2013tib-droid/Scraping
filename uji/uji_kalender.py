"""Uji `inti/kalender.py` — halaman arsip. Tanpa jaringan."""

import re
from datetime import date, datetime

from alur import edisi
from inti import kalender, render


def berkas_edisi(akar, *tanggal):
    """Bikin arsip palsu: isinya tidak dibaca siapa pun, hanya namanya."""
    arsip = akar / "arsip"
    arsip.mkdir(parents=True, exist_ok=True)
    for t in tanggal:
        (arsip / f"{t}.html").write_text("<!doctype html>", encoding="utf-8")
    return arsip


# --------------------------------------------------------------------------- #
# daftar tanggal
# --------------------------------------------------------------------------- #


def uji_tanggal_dibaca_dari_nama_berkas(tmp_path):
    arsip = berkas_edisi(tmp_path, "2026-09-10", "2026-09-08", "2026-09-09")
    assert kalender.tanggal_tersedia(arsip) == [
        date(2026, 9, 8), date(2026, 9, 9), date(2026, 9, 10),
    ]


def uji_berkas_bukan_tanggal_dilewati(tmp_path):
    """`index.html` — halaman arsip itu sendiri — tidak boleh jadi tanggal."""
    arsip = berkas_edisi(tmp_path, "2026-09-09")
    (arsip / "index.html").write_text("x", encoding="utf-8")
    (arsip / "catatan.html").write_text("x", encoding="utf-8")
    assert kalender.tanggal_tersedia(arsip) == [date(2026, 9, 9)]


def uji_arsip_belum_ada_bukan_galat(tmp_path):
    assert kalender.tanggal_tersedia(tmp_path / "belum-ada") == []


# --------------------------------------------------------------------------- #
# halaman kalender
# --------------------------------------------------------------------------- #


def uji_tanggal_yang_ada_edisinya_jadi_tautan():
    html = kalender.halaman([date(2026, 9, 9), date(2026, 9, 12)])
    assert 'href="2026-09-09.html"' in html
    assert 'href="2026-09-12.html"' in html
    # 10 dan 11 September tidak ada edisinya: tetap tampil sebagai angka, tapi
    # tanpa tautan — kalender yang bolong lebih jujur daripada tautan mati.
    assert 'href="2026-09-10.html"' not in html
    assert "<span>10</span>" in html and "<span>11</span>" in html


def uji_edisi_terbaru_ditandai():
    html = kalender.halaman([date(2026, 9, 9), date(2026, 9, 12)])
    assert 'href="2026-09-12.html" class="terbaru"' in html
    assert 'href="2026-09-09.html" class="terbaru"' not in html


def uji_bulan_terbaru_di_atas():
    html = kalender.halaman([date(2026, 8, 30), date(2026, 9, 1)])
    assert html.index("<caption>September 2026") < html.index("<caption>Agustus 2026")


def uji_pintasan_hanya_yang_halamannya_ada():
    """"Seminggu lalu" dihitung dari edisi terbaru, dan hanya muncul kalau
    edisinya memang ada."""
    terbaru = date(2026, 9, 12)
    html = kalender.halaman([terbaru, date(2026, 9, 11), date(2026, 9, 5)])
    assert 'href="2026-09-11.html">Kemarin' in html
    assert 'href="2026-09-05.html">Seminggu lalu' in html
    assert "3 hari lalu" not in html  # 9 Sep tidak ada di daftar


def uji_arsip_kosong_tidak_meledak():
    html = kalender.halaman([])
    assert "Belum ada edisi" in html
    assert 'class="pintasan"' not in html


def uji_semua_tautan_menunjuk_berkas_yang_ada(tmp_path):
    """Invarian halaman ini: tidak boleh menjanjikan edisi yang tidak ada."""
    tanggal = ["2026-08-29", "2026-09-01", "2026-09-05", "2026-09-12"]
    arsip = berkas_edisi(tmp_path, *tanggal)
    berkas = kalender.tulis(tmp_path)
    html = berkas.read_text(encoding="utf-8")

    tautan = re.findall(r'href="([^"]+)"', html)
    edisi_ditaut = [t for t in tautan if t.endswith(".html") and not t.startswith("..")]
    assert edisi_ditaut, "kalender tanpa satu pun tautan edisi"
    for t in edisi_ditaut:
        assert (arsip / t).exists(), f"tautan mati: {t}"
    assert {f"{t}.html" for t in tanggal} <= set(edisi_ditaut)


# --------------------------------------------------------------------------- #
# sambungan ke halaman edisi
# --------------------------------------------------------------------------- #


def uji_halaman_edisi_menaut_ke_arsip():
    html = render.halaman(datetime(2026, 9, 12, 5, 0), {}, jumlah_sumber=0,
                          total_dipertimbangkan=0)
    assert 'href="arsip/index.html"' in html


def uji_menulis_edisi_ikut_menyegarkan_kalender(tmp_path):
    html = render.halaman(datetime(2026, 9, 12, 5, 0), {}, jumlah_sumber=0,
                          total_dipertimbangkan=0)
    edisi.tulis(html, date(2026, 9, 12), tmp_path)

    kalender_html = (tmp_path / "arsip" / "index.html").read_text(encoding="utf-8")
    assert 'href="2026-09-12.html"' in kalender_html

    # Dari dalam arsip/, tautan ke kalender harus jadi tautan sesama folder.
    arsip_html = (tmp_path / "arsip" / "2026-09-12.html").read_text(encoding="utf-8")
    assert 'href="index.html"' in arsip_html
    assert 'href="arsip/index.html"' not in arsip_html
