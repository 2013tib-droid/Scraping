"""Uji ekstraksi gambar feed, migrasi kolomnya, dan tampilnya di halaman.

Semua feed di sini palsu dan dibangun di memori — tidak ada jaringan, sesuai
syarat ARSITEKTUR.md §13. Bentuk XML-nya sengaja ditiru dari yang benar-benar
dikirim media Indonesia, bukan dikarang: `<enclosure>` ala detikcom,
`<media:thumbnail>` ala antaranews, dan `<img>` di dalam CDATA ala WordPress.
"""

from datetime import datetime

import duckdb
import feedparser
import pytest

from alur import edisi, reparse
from alur.berita import gambar, ke_artikel
from inti import penyimpanan, render
from inti.penyimpanan import Artikel

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel>
  <image><url>https://a.test/logo-redaksi.png</url></image>
  {item}
</channel>
</rss>"""


def entri(isi: str):
    """Satu entri feedparser dari potongan <item>."""
    return feedparser.parse(FEED.format(item=f"<item>{isi}</item>")).entries[0]


def satu(isi: str) -> str | None:
    return gambar(entri(f"<title>Judul</title><link>https://a.test/1</link>{isi}"))


# --------------------------------------------------------------------------- #
# dari mana gambarnya diambil
# --------------------------------------------------------------------------- #


def uji_media_thumbnail():
    assert satu('<media:thumbnail url="https://cdn.test/a.jpg"/>') == "https://cdn.test/a.jpg"


def uji_enclosure():
    assert satu(
        '<enclosure length="25000" type="image/jpeg" url="https://cdn.test/b.jpeg?w=360&amp;q=90"/>'
    ) == "https://cdn.test/b.jpeg?w=360&q=90"


def uji_query_tidak_menghalangi_pengenalan_ekstensi():
    """CDN media hampir selalu menempelkan `?w=...&q=...`. Kalau ekstensi
    diperiksa pada URL utuh, tidak ada satu pun gambar yang lolos."""
    assert satu('<media:thumbnail url="https://cdn.test/c.jpg?w=1200&amp;q=90"/>')


def uji_img_dalam_ringkasan_sebagai_jalan_terakhir():
    assert satu(
        "<description><![CDATA[<img src='https://cdn.test/d.png'> Isi berita.]]></description>"
    ) == "https://cdn.test/d.png"


def uji_thumbnail_menang_atas_img_ringkasan():
    """`<img>` pertama di HTML ringkasan sering logo penerbit, jadi elemen yang
    memang berarti "ini thumbnail-nya" harus lebih dulu."""
    assert satu(
        '<media:thumbnail url="https://cdn.test/asli.jpg"/>'
        "<description><![CDATA[<img src='https://cdn.test/logo.png'>]]></description>"
    ) == "https://cdn.test/asli.jpg"


# --------------------------------------------------------------------------- #
# yang harus ditolak
# --------------------------------------------------------------------------- #


def uji_enclosure_bukan_gambar_ditolak():
    """Sebagian feed memakai <enclosure> yang sama untuk podcast dan video."""
    assert satu('<enclosure type="audio/mpeg" url="https://cdn.test/e.mp3"/>') is None
    assert satu('<media:content medium="video" url="https://cdn.test/f.mp4"/>') is None


def uji_pelacak_ditolak():
    """Piksel 1x1 lolos setiap pemeriksaan ekstensi, tapi tampil sebagai kotak
    kosong di kartu sorotan."""
    for u in ("https://feedburner.test/x.gif", "https://t.test/pixel/1x1.png"):
        assert satu(f"<description><![CDATA[<img src='{u}'>]]></description>") is None


def uji_url_tak_terpakai_ditolak():
    assert satu("<description><![CDATA[<img src='/lokal/g.jpg'>]]></description>") is None
    assert satu("<description><![CDATA[<img src='data:image/gif;base64,R0lGOD'>]]></description>") is None


def uji_tanpa_gambar_mengembalikan_none():
    assert satu("<description>Teks polos tanpa gambar.</description>") is None


def uji_menempel_ke_artikel():
    e = entri(
        "<title>Judul</title><link>https://a.test/1</link>"
        '<media:thumbnail url="https://cdn.test/h.jpg"/>'
    )
    a = ke_artikel(e, {"nama": "f", "kategori": "makro"}, datetime(2026, 9, 9))
    assert a.gambar == "https://cdn.test/h.jpg"


# --------------------------------------------------------------------------- #
# penyimpanan: kolom baru dan migrasinya
# --------------------------------------------------------------------------- #


@pytest.fixture
def con(tmp_path):
    c = penyimpanan.buka(tmp_path / "uji.duckdb")
    yield c
    c.close()


def artikel(**kw):
    dasar = dict(
        artikel_id="id1", url="https://a.test/1", domain="a.test", judul="Judul",
        ringkasan="isi", waktu_terbit=datetime(2026, 9, 8, 10, 0),
        waktu_fetch=datetime(2026, 9, 9, 0, 0), feed="f", kategori="makro",
    )
    return Artikel(**(dasar | kw))


def uji_gambar_tersimpan_dan_terbaca(con):
    penyimpanan.simpan_artikel(con, [artikel(gambar="https://cdn.test/i.jpg")])
    baris = edisi.ambil(con, datetime(2026, 9, 8), datetime(2026, 9, 9))
    assert baris[0]["gambar"] == "https://cdn.test/i.jpg"


def uji_tanpa_gambar_tetap_null(con):
    penyimpanan.simpan_artikel(con, [artikel()])
    assert edisi.ambil(con, datetime(2026, 9, 8), datetime(2026, 9, 9))[0]["gambar"] is None


def uji_migrasi_menambah_kolom_ke_basis_lama(tmp_path):
    """Basis data di cache Actions sudah berisi ribuan baris dari sebelum kolom
    `gambar` ada. CREATE TABLE IF NOT EXISTS tidak menyentuhnya, jadi tanpa
    ALTER kolomnya tidak akan pernah muncul di sana."""
    berkas = tmp_path / "lama.duckdb"
    lama = duckdb.connect(str(berkas))
    lama.execute(
        """CREATE TABLE artikel (
             artikel_id VARCHAR PRIMARY KEY, url VARCHAR NOT NULL,
             domain VARCHAR NOT NULL, judul VARCHAR NOT NULL, ringkasan VARCHAR,
             waktu_terbit TIMESTAMP, waktu_fetch TIMESTAMP NOT NULL,
             feed VARCHAR NOT NULL, kategori VARCHAR NOT NULL,
             bobot DOUBLE NOT NULL DEFAULT 1.0)"""
    )
    lama.execute(
        "INSERT INTO artikel VALUES ('id1','https://a.test/1','a.test','Judul',"
        "NULL, NULL, TIMESTAMP '2026-09-09 00:00:00','f','makro',1.0)"
    )
    lama.close()

    con = penyimpanan.buka(berkas)
    try:
        kolom = [c[1] for c in con.execute("PRAGMA table_info('artikel')").fetchall()]
        assert "gambar" in kolom
        # Barisnya harus selamat — memulai dari nol berarti membuang artikel
        # yang tidak bisa diambil ulang.
        assert con.execute("SELECT count(*) FROM artikel").fetchone()[0] == 1
    finally:
        con.close()


def uji_migrasi_idempoten(tmp_path):
    for _ in range(3):
        penyimpanan.buka(tmp_path / "u.duckdb").close()


# --------------------------------------------------------------------------- #
# reparse: isi yang kosong, jangan timpa yang sudah ada
# --------------------------------------------------------------------------- #


def uji_reparse_mengisi_yang_kosong(con):
    penyimpanan.simpan_artikel(con, [artikel()])
    assert reparse.isi(con, {"id1": "https://cdn.test/j.jpg"}) == 1
    assert con.execute("SELECT gambar FROM artikel").fetchone()[0] == "https://cdn.test/j.jpg"


def uji_reparse_tidak_menimpa(con):
    """`artikel` append-only (§5). Mengisi lubang berbeda dari menulis ulang
    sejarah, jadi pengecualiannya dijaga tetap sempit."""
    penyimpanan.simpan_artikel(con, [artikel(gambar="https://cdn.test/asli.jpg")])
    assert reparse.isi(con, {"id1": "https://cdn.test/baru.jpg"}) == 0
    assert con.execute("SELECT gambar FROM artikel").fetchone()[0] == "https://cdn.test/asli.jpg"


# --------------------------------------------------------------------------- #
# halaman: hanya kartu sorotan, tidak pernah item bernomor
# --------------------------------------------------------------------------- #


def peristiwa(judul, url, gambar=None):
    return edisi.Peristiwa(
        judul=judul, url=url, domain="a.test", ringkasan="isi",
        waktu_terbit=datetime(2026, 9, 8, 10, 0), kategori="makro",
        jumlah_media=1, bobot=1.0, gambar=gambar,
    )


def halaman(daftar):
    return render.halaman(
        datetime(2026, 9, 9, 5, 0), {"makro": daftar},
        jumlah_sumber=1, total_dipertimbangkan=len(daftar),
    )


def uji_sorotan_bergambar():
    html = halaman([peristiwa("Satu", "u1", "https://cdn.test/k.jpg")])
    assert 'class="sorotan bergambar"' in html
    assert 'class="thumb" src="https://cdn.test/k.jpg"' in html
    # Dekoratif: judulnya sudah mengatakan segalanya, dan gambar yang mati tidak
    # boleh meninggalkan teks alternatif yang menggantung.
    assert 'alt=""' in html
    assert 'loading="lazy"' in html


def uji_sorotan_tanpa_gambar_tidak_berubah():
    html = halaman([peristiwa("Satu", "u1")])
    # Kelasnya diperiksa di tag <article>, bukan di seluruh halaman: blok GAYA
    # selalu memuat aturan .sorotan.bergambar entah dipakai atau tidak.
    assert '<article class="sorotan">' in html
    assert '<article class="sorotan bergambar">' not in html
    assert "<img" not in html


def uji_item_bernomor_tidak_pernah_bergambar():
    """Batas inilah fiturnya: 35 thumbnail berarti ~1,5 MB, sepuluh kartu
    sorotan ~300 KB. Kalau gambar bocor ke daftar bernomor, batas itu hilang."""
    daftar = [peristiwa(f"Berita {i}", f"u{i}", f"https://cdn.test/{i}.jpg") for i in range(6)]
    html = halaman(daftar)
    import re

    for li in re.findall(r"<li>(.*?)</li>", html, re.S):
        assert "<img" not in li
    assert html.count('class="thumb"') == 1  # hanya sorotan bagian ini


def uji_url_gambar_di_escape():
    """URL gambar datang dari feed pihak ketiga dan masuk ke dalam atribut HTML,
    jadi tanda kutip di dalamnya harus tidak bisa menutup atribut itu."""
    html = halaman([peristiwa("Satu", "u1", 'https://cdn.test/a.jpg?x="onerror=alert(1)')])
    assert 'src="https://cdn.test/a.jpg?x=&quot;onerror=alert(1)"' in html
    # Yang berbahaya adalah kutip mentah yang menutup src lalu memulai atribut
    # baru; bentuk itu tidak boleh ada di mana pun.
    assert '?x="onerror' not in html
