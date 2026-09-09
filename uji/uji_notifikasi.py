"""
Uji `inti/notifikasi.py`. Tidak menyentuh jaringan sama sekali (ARSITEKTUR.md §13)
— semua permintaan dilayani `httpx.MockTransport`.

Yang diuji di sini bukan "apakah pesannya bagus", tapi janji-janji yang dipegang
modul itu: tidak pernah melempar, tidak pernah diam, dan tidak pernah mengirim
pesan lebih panjang dari yang diterima Telegram.
"""

import httpx
import pytest

from inti import notifikasi


@pytest.fixture(autouse=True)
def _tanpa_tidur(monkeypatch):
    """Backoff nyata membuat uji lambat tanpa menambah keyakinan."""
    jeda = []
    monkeypatch.setattr(notifikasi.time, "sleep", jeda.append)
    return jeda


@pytest.fixture
def kredensial(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "111:AAA")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "222")


def pasang(monkeypatch, penangan):
    """Ganti klien dengan MockTransport, dan kumpulkan request yang lewat."""
    terkirim: list[httpx.Request] = []

    def _tangani(request: httpx.Request) -> httpx.Response:
        terkirim.append(request)
        return penangan(request)

    monkeypatch.setattr(
        notifikasi,
        "_buat_klien",
        lambda: httpx.Client(transport=httpx.MockTransport(_tangani)),
    )
    return terkirim


def _ok(_request):
    return httpx.Response(200, json={"ok": True})


# --------------------------------------------------------------------------- #


def uji_tanpa_kredensial_turun_ke_terminal(monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    assert notifikasi.aktif() is False
    assert notifikasi.kirim_kegagalan("bps", "WebAPI 503") is False

    # Turun ke terminal, bukan error — dan isinya tetap terbaca.
    keluaran = capsys.readouterr().out
    assert "GAGAL" in keluaran and "bps" in keluaran and "WebAPI 503" in keluaran


def uji_kirim_berhasil(monkeypatch, kredensial):
    terkirim = pasang(monkeypatch, _ok)

    assert notifikasi.kirim_kegagalan("bps", "0 baris", run_id="r-1") is True
    assert len(terkirim) == 1

    isi = terkirim[0].content.decode()
    assert "chat_id=222" in isi
    assert "r-1" in isi
    # Teks polos: parse_mode tidak pernah dikirim.
    assert "parse_mode" not in isi
    assert terkirim[0].url.path == "/bot111:AAA/sendMessage"


def uji_kanal_operasional_dan_isi_tidak_tertukar(monkeypatch, kredensial):
    terkirim = pasang(monkeypatch, _ok)

    notifikasi.kirim_kegagalan("bps", "rusak")
    notifikasi.kirim_anomali("bi", "kurs melompat 12%")
    notifikasi.kirim_rangkuman("Makro hari ini\n- IHK 2,1%")

    gagal, anomali, rangkuman = (r.content.decode() for r in terkirim)
    assert "GAGAL" in gagal
    assert "ANOMALI" in anomali
    # Rangkuman tidak ikut dibungkus penanda operasional (§16).
    assert "GAGAL" not in rangkuman and "ANOMALI" not in rangkuman


def uji_pesan_panjang_dipotong_di_bawah_batas(monkeypatch, kredensial):
    terkirim = pasang(monkeypatch, _ok)

    panjang = "\n".join(f"baris {i} — " + "x" * 80 for i in range(200))
    assert len(panjang) > notifikasi.BATAS_PESAN

    assert notifikasi.kirim_rangkuman(panjang) is True
    assert len(terkirim) > 1
    for request in terkirim:
        teks = httpx.QueryParams(request.content.decode())["text"]
        assert len(teks) <= notifikasi.BATAS_PESAN
    assert "(1/" in httpx.QueryParams(terkirim[0].content.decode())["text"]


def uji_baris_tunggal_sangat_panjang_tetap_dipotong():
    bagian = notifikasi._potong("y" * 10_000)
    assert len(bagian) > 1
    assert all(len(b) <= notifikasi.BATAS_PESAN for b in bagian)


def uji_gagal_terus_menerus_tidak_melempar(monkeypatch, kredensial, capsys):
    terkirim = pasang(monkeypatch, lambda _r: httpx.Response(500, text="boom"))

    assert notifikasi.kirim_kegagalan("bps", "x") is False
    assert len(terkirim) == notifikasi.PERCOBAAN  # dicoba ulang, lalu menyerah
    assert "HTTP 500" in capsys.readouterr().err  # tidak diam (anti-pattern #6)


def uji_error_jaringan_tidak_melempar(monkeypatch, kredensial, capsys):
    def _meledak(_request):
        raise httpx.ConnectError("dns gagal")

    pasang(monkeypatch, _meledak)

    assert notifikasi.kirim_anomali("bi", "x") is False
    assert "tidak terjangkau" in capsys.readouterr().err


def uji_429_menghormati_retry_after(monkeypatch, kredensial, _tanpa_tidur):
    balasan = [
        httpx.Response(429, json={"parameters": {"retry_after": 7}}),
        httpx.Response(200, json={"ok": True}),
    ]
    pasang(monkeypatch, lambda _r: balasan.pop(0))

    assert notifikasi.kirim_rangkuman("halo") is True
    assert _tanpa_tidur == [7.0]  # jeda dari Telegram dipakai, bukan backoff


def uji_retry_after_gila_dibatasi(monkeypatch, kredensial, _tanpa_tidur):
    pasang(monkeypatch, lambda _r: httpx.Response(429, json={"parameters": {"retry_after": 9999}}))

    assert notifikasi.kirim_rangkuman("halo") is False
    assert all(j <= notifikasi.JEDA_MAKS for j in _tanpa_tidur)


def uji_terminal_cp1252_tidak_melempar(monkeypatch):
    """Regresi: console Windows bawaan cp1252 tidak bisa mengkodekan emoji.

    Sebelum diperbaiki, ini melempar UnicodeEncodeError dan menjatuhkan job di
    jalur yang paling sering dipakai — terminal, saat Telegram belum diisi.
    """
    import io

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    sempit = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(notifikasi.sys, "stdout", sempit)

    assert notifikasi.kirim_kegagalan("bps", "WebAPI 503") is False

    sempit.seek(0)
    keluaran = sempit.buffer.getvalue().decode("cp1252")
    assert "GAGAL" in keluaran and "bps" in keluaran  # isinya tetap terbaca


def uji_stempel_waktu_dalam_wib():
    from datetime import datetime, timezone

    utc = datetime(2026, 9, 9, 7, 3, tzinfo=timezone.utc)
    assert notifikasi._stempel(utc) == "09/09/2026 14:03 WIB"  # UTC+7 (§15 #9)
