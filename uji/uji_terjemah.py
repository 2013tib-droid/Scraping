"""Uji `inti/terjemah.py` dan terjemahan bagian Global. Tanpa jaringan: yang
meminta ke Google selalu diganti fungsi palsu."""

import json
from datetime import date, datetime

import httpx
import pytest

from alur import edisi
from inti import penyimpanan, terjemah
from inti.penyimpanan import Artikel


@pytest.fixture
def con(tmp_path):
    c = penyimpanan.buka(tmp_path / "uji.duckdb")
    yield c
    c.close()


def artikel(judul, domain, kategori="global", ringkasan="Summary text here."):
    return Artikel(
        artikel_id=f"{domain}-{judul}"[:60],
        url=f"https://{domain}/news/{abs(hash(judul)) % 9999}",
        domain=domain,
        judul=judul,
        ringkasan=ringkasan,
        waktu_terbit=datetime(2026, 9, 8, 10, 0),
        waktu_fetch=datetime(2026, 9, 9, 0, 0),
        feed=domain,
        kategori=kategori,
    )


def palsu(teks):
    return {t: f"[id] {t}" for t in teks}


# --------------------------------------------------------------------------- #
# balasan endpoint
# --------------------------------------------------------------------------- #


def uji_urai_menyambung_potongan_kalimat():
    """Balasan gtx memotong per kalimat; semuanya harus disambung kembali."""
    isi = json.dumps([
        [["Harga minyak turun. ", "Oil falls. ", None, None, 10],
         ["Pasar khawatir.", "Markets worry.", None, None, 10]],
        None, "en",
    ]).encode()
    assert terjemah.urai(isi) == "Harga minyak turun. Pasar khawatir."


@pytest.mark.parametrize("isi", [b"<html>captcha</html>", b"[]", b"[[]]", b'[[[""]]]'])
def uji_urai_menolak_bentuk_asing(isi):
    """Format yang berubah harus jadi galat, bukan judul kosong di halaman."""
    with pytest.raises(ValueError):
        terjemah.urai(isi)


# --------------------------------------------------------------------------- #
# cache dan kegagalan
# --------------------------------------------------------------------------- #


def uji_hasil_disimpan_dan_tidak_diminta_ulang(con):
    diminta = []

    def minta(t):
        diminta.append(t)
        return f"ID {t}"

    assert terjemah.terjemahkan(con, ["Oil falls", "Oil falls", ""], minta) == {
        "Oil falls": "ID Oil falls"
    }
    # Edisi yang dibangun ulang tidak boleh meminta lagi.
    assert terjemah.terjemahkan(con, ["Oil falls"], minta) == {"Oil falls": "ID Oil falls"}
    assert diminta == ["Oil falls"]


def uji_jaringan_gagal_berhenti_tanpa_meledak(con):
    diminta = []

    def minta(t):
        diminta.append(t)
        raise httpx.ConnectError("mati")

    assert terjemah.terjemahkan(con, ["a", "b", "c"], minta) == {}
    # Sisanya tidak dicoba: masing-masing akan menunggu backoff yang sama.
    assert diminta == ["a"]
    assert con.execute("SELECT count(*) FROM terjemahan").fetchone()[0] == 0


def uji_balasan_aneh_hanya_melewati_satu(con):
    def minta(t):
        if t == "rusak":
            raise ValueError("balasan terjemahan tidak dikenal")
        return f"ID {t}"

    assert terjemah.terjemahkan(con, ["rusak", "baik"], minta) == {"baik": "ID baik"}


# --------------------------------------------------------------------------- #
# edisi
# --------------------------------------------------------------------------- #


def uji_global_diterjemahkan_tautan_tetap_asli(con):
    penyimpanan.simpan_artikel(con, [
        artikel("Oil prices slip on demand worries", "cnbc.com"),
    ])
    html, bagian, _ = edisi.bangun(con, date(2026, 9, 9), penerjemah=palsu)
    p = bagian["global"][0]

    assert p.judul == "[id] Oil prices slip on demand worries"
    assert p.ringkasan == "[id] Summary text here."
    assert p.judul_asli == "Oil prices slip on demand worries"
    assert p.url.startswith("https://cnbc.com/news/")
    assert f'<a href="{p.url}" hreflang="en">[id] Oil prices slip' in html
    assert "diterjemahkan" in html
    assert 'title="Oil prices slip on demand worries"' in html


def uji_bagian_lain_tidak_disentuh(con):
    penyimpanan.simpan_artikel(con, [
        artikel("Cadangan devisa naik pada akhir Agustus", "a.test", kategori="makro",
                ringkasan="isi"),
    ])
    diminta = []
    _, bagian, _ = edisi.bangun(
        con, date(2026, 9, 9), penerjemah=lambda t: diminta.extend(t) or {}
    )
    semua = [p for v in bagian.values() for p in v]
    assert [p.judul for p in semua] == ["Cadangan devisa naik pada akhir Agustus"]
    assert diminta == []


def uji_global_di_blok_utama_ikut_diterjemahkan(con):
    """Siaran pers FOMC naik ke blok utama; kategorinya tetap Global."""
    penyimpanan.simpan_artikel(con, [
        Artikel(
            artikel_id="fed", url="https://www.federalreserve.gov/x", domain="federalreserve.gov",
            judul="Federal Reserve issues FOMC statement", ringkasan=None,
            waktu_terbit=datetime(2026, 9, 8, 10, 0), waktu_fetch=datetime(2026, 9, 9),
            feed="fed", kategori="global", bobot=2.0,
        ),
    ])
    _, bagian, _ = edisi.bangun(con, date(2026, 9, 9), penerjemah=palsu)
    assert bagian["utama"][0].judul == "[id] Federal Reserve issues FOMC statement"


def uji_penilaian_memakai_teks_asli(con):
    """Terjemahan jalan setelah penilai dampak: "FOMC" di judul Inggris yang
    mengangkatnya, bukan apa pun yang dihasilkan terjemahan."""
    penyimpanan.simpan_artikel(con, [
        artikel("Federal Reserve issues FOMC statement", "x.test"),
    ])
    _, bagian, _ = edisi.bangun(
        con, date(2026, 9, 9), penerjemah=lambda t: {x: "kosong" for x in t}
    )
    assert bagian["utama"][0].dampak == 3


def uji_tanpa_terjemahan_halaman_seperti_dulu(con):
    """Penerjemah gagal total = edisi tetap terbit, dalam bahasa Inggris."""
    penyimpanan.simpan_artikel(con, [artikel("Oil prices slip", "cnbc.com")])
    html, bagian, _ = edisi.bangun(con, date(2026, 9, 9), penerjemah=lambda t: {})
    assert bagian["global"][0].judul == "Oil prices slip"
    assert bagian["global"][0].judul_asli is None
    assert "hreflang" not in html and 'class="terjemah"' not in html
