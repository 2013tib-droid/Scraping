"""
Uji `alur/berita.py` dan `inti/http.py`. Tanpa jaringan (ARSITEKTUR.md §13):
respons dilayani `httpx.MockTransport`, dan feed dibaca dari fixture.
"""

from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from alur import berita
from inti import http as inti_http
from inti import penyimpanan

FIXTURE = Path(__file__).parent / "fixtures" / "rss_contoh.xml"


@pytest.fixture(autouse=True)
def _tanpa_tidur(monkeypatch):
    monkeypatch.setattr(inti_http.time, "sleep", lambda _d: None)


@pytest.fixture
def con(tmp_path):
    c = penyimpanan.buka(tmp_path / "uji.duckdb")
    yield c
    c.close()


@pytest.fixture
def rss():
    return FIXTURE.read_bytes()


def klien_palsu(monkeypatch, penangan):
    """Klien asli, tapi transport-nya dipalsukan — retry & rate limit tetap diuji."""
    k = inti_http.Klien(jeda_domain=0.0)
    k._klien = httpx.Client(transport=httpx.MockTransport(penangan))
    return k


FEED = [{"nama": "Uji Media", "url": "https://contoh.test/rss", "kategori": "makro"}]


# --------------------------------------------------------------------------- #
# inti/http.py
# --------------------------------------------------------------------------- #


def uji_ua_wajib_ascii():
    """Em dash di User-Agent membuat httpx melempar sebelum request keluar,
    dan gejalanya terlihat seperti semua situs mati serempak."""
    with pytest.raises(UnicodeEncodeError):
        inti_http.Klien(ua="intel-makro/0.1 — kontak")


def uji_conditional_request_dikirim(monkeypatch, rss):
    dilihat = {}

    def tangani(request):
        dilihat.update(request.headers)
        return httpx.Response(304)

    k = klien_palsu(monkeypatch, tangani)
    r = k.ambil("https://contoh.test/rss", etag='"abc"', last_modified="Mon, 08 Sep 2026 00:00:00 GMT")
    k.tutup()

    assert dilihat["if-none-match"] == '"abc"'
    assert dilihat["if-modified-since"].startswith("Mon, 08 Sep")
    assert r.tidak_berubah and not r.berhasil


def uji_retry_lalu_berhasil(monkeypatch, rss):
    balasan = [httpx.Response(503), httpx.Response(200, content=rss)]
    k = klien_palsu(monkeypatch, lambda _r: balasan.pop(0))
    r = k.ambil("https://contoh.test/rss")
    k.tutup()

    assert r.berhasil and r.hash_isi and len(r.hash_isi) == 64


def uji_404_tidak_diulang(monkeypatch):
    percobaan = []

    def tangani(request):
        percobaan.append(1)
        return httpx.Response(404)

    k = klien_palsu(monkeypatch, tangani)
    r = k.ambil("https://contoh.test/rss")
    k.tutup()

    # 404 berarti permintaan kita yang salah; mengulang hanya menambah beban.
    assert len(percobaan) == 1 and r.status == 404 and not r.berhasil


def uji_gagal_terus_melempar(monkeypatch):
    k = klien_palsu(monkeypatch, lambda _r: httpx.Response(503))
    with pytest.raises(httpx.HTTPError):
        k.ambil("https://contoh.test/rss")
    k.tutup()


# --------------------------------------------------------------------------- #
# alur/berita.py
# --------------------------------------------------------------------------- #


def uji_kanonik_membuang_pelacak():
    a = berita.kanonik("https://x.test/a?utm_source=x&id=7#bagian")
    assert a == "https://x.test/a?id=7"


def uji_url_disimpan_utuh(rss, con, monkeypatch, tmp_path):
    """Parameter query boleh dibuang untuk ID, tapi tautannya harus tetap hidup."""
    monkeypatch.setattr(penyimpanan, "AKAR", tmp_path)
    k = klien_palsu(monkeypatch, lambda _r: httpx.Response(200, content=rss))
    berita.jalankan(con, k, FEED, "r1")
    k.tutup()

    url = con.execute(
        "SELECT url FROM artikel WHERE url LIKE '%utm%'"
    ).fetchall()
    assert url, "artikel dengan parameter pelacakan harus tetap menyimpan URL asli"


def uji_jalankan_menyimpan_artikel_dan_bronze(rss, con, monkeypatch, tmp_path):
    monkeypatch.setattr(penyimpanan, "AKAR", tmp_path)
    k = klien_palsu(monkeypatch, lambda _r: httpx.Response(200, content=rss))
    ringkas = berita.jalankan(con, k, FEED, "r1")
    k.tutup()

    assert ringkas.item == 3 and ringkas.baru == 3 and not ringkas.gagal
    assert con.execute("SELECT count(*) FROM artikel").fetchone()[0] == 3

    # Raw tersimpan (§5) — memperbaiki parser nanti berarti re-parse, bukan re-scrape.
    mentah = list(tmp_path.rglob("*.xml"))
    meta = list(tmp_path.rglob("*.json"))
    assert len(mentah) == 1 and len(meta) == 1


def uji_jalan_dua_kali_idempoten(rss, con, monkeypatch, tmp_path):
    monkeypatch.setattr(penyimpanan, "AKAR", tmp_path)
    for run in ("r1", "r2"):
        k = klien_palsu(monkeypatch, lambda _r: httpx.Response(200, content=rss))
        ringkas = berita.jalankan(con, k, FEED, run)
        k.tutup()

    assert ringkas.baru == 0, "run kedua tidak boleh menambah artikel"
    assert con.execute("SELECT count(*) FROM artikel").fetchone()[0] == 3


def uji_304_dilewati(rss, con, monkeypatch, tmp_path):
    monkeypatch.setattr(penyimpanan, "AKAR", tmp_path)
    k = klien_palsu(monkeypatch, lambda _r: httpx.Response(304))
    ringkas = berita.jalankan(con, k, FEED, "r1")
    k.tutup()

    assert ringkas.tidak_berubah == 1 and ringkas.item == 0 and not ringkas.gagal
    assert list(tmp_path.rglob("*.xml")) == []


def uji_satu_feed_rusak_tidak_menjatuhkan_sisanya(rss, con, monkeypatch, tmp_path):
    monkeypatch.setattr(penyimpanan, "AKAR", tmp_path)

    def tangani(request):
        if "rusak" in str(request.url):
            raise httpx.ConnectError("dns gagal")
        return httpx.Response(200, content=rss)

    feed = [
        {"nama": "Rusak", "url": "https://rusak.test/rss", "kategori": "makro"},
        *FEED,
    ]
    k = klien_palsu(monkeypatch, tangani)
    ringkas = berita.jalankan(con, k, feed, "r1")
    k.tutup()

    assert len(ringkas.gagal) == 1 and ringkas.gagal[0][0] == "Rusak"
    assert ringkas.baru == 3, "feed sehat tetap terproses"


def uji_200_tapi_nol_item_dianggap_gagal(con, monkeypatch, tmp_path):
    """Kegagalan diam: HTTP 200 tapi parser tidak menghasilkan apa pun (§9)."""
    monkeypatch.setattr(penyimpanan, "AKAR", tmp_path)
    kosong = b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    k = klien_palsu(monkeypatch, lambda _r: httpx.Response(200, content=kosong))
    ringkas = berita.jalankan(con, k, FEED, "r1")
    k.tutup()

    assert ringkas.gagal and "0 item" in ringkas.gagal[0][1]


def uji_metrik_tercatat(rss, con, monkeypatch, tmp_path):
    monkeypatch.setattr(penyimpanan, "AKAR", tmp_path)
    k = klien_palsu(monkeypatch, lambda _r: httpx.Response(200, content=rss))
    berita.jalankan(con, k, FEED, "r1")
    k.tutup()

    baris = con.execute(
        "SELECT status, jumlah_item, jumlah_baru FROM metrik_run WHERE run_id='r1'"
    ).fetchall()
    assert baris == [("ok", 3, 3)]


def uji_waktu_terbit_dinormalkan_ke_utc(rss, con, monkeypatch, tmp_path):
    monkeypatch.setattr(penyimpanan, "AKAR", tmp_path)
    k = klien_palsu(monkeypatch, lambda _r: httpx.Response(200, content=rss))
    berita.jalankan(con, k, FEED, "r1")
    k.tutup()

    t = con.execute(
        "SELECT waktu_terbit FROM artikel WHERE judul LIKE 'Inflasi%'"
    ).fetchone()[0]
    # Fixture menulis 09:00 +0700 -> 02:00 UTC (§15 #9).
    # Disimpan sebagai UTC polos: jangan panggil astimezone() di sini — pada
    # datetime naive, Python akan menganggapnya waktu lokal (WIB) dan menggeser
    # nilainya 7 jam. Justru itu jebakan yang mau dicegah konvensi ini.
    assert t.tzinfo is None, "kolom waktu disimpan polos, bukan beroffset"
    assert (t.year, t.month, t.day, t.hour) == (2026, 9, 9, 2)


def uji_ringkasan_dibersihkan_dari_html():
    assert berita.bersihkan("<p>Halo &amp; <b>dunia</b></p>") == "Halo & dunia"
    assert berita.bersihkan("   ") is None
    assert berita.bersihkan(None) is None
