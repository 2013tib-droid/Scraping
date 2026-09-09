"""
notifikasi.py — satu-satunya jalan keluar pesan dari sistem ini.

Dua kanal yang sengaja dipisah (ARSITEKTUR.md §16):

    kirim_kegagalan(), kirim_anomali()  -> operasional: pipeline sehat atau tidak
    kirim_rangkuman()                   -> isi: apa yang terjadi di data hari ini

Jangan digabung jadi satu fungsi. Kegagalan teknis harus tetap terbaca pada hari
ketika rangkuman kosong karena memang tidak ada rilis.

Aturan modul ini:

- **Tidak pernah melempar exception ke pemanggil.** Notifikasi yang gagal tidak
  boleh menjatuhkan job pengumpulan data (§9).
- **Tapi juga tidak pernah diam.** Setiap kegagalan kirim dicetak ke stderr.
  `try/except: pass` adalah anti-pattern #6.
- **Token kosong bukan error.** Modul turun ke terminal, supaya alur bisa
  dikembangkan dan diuji tanpa mengirim pesan sungguhan (pola `IDX Screener`).
- **Timeout eksplisit** di semua request (§9 #6).
- **Retry dengan backoff + jitter** (§9 #1), dan `retry_after` dari Telegram
  dihormati kalau kena rate limit.
- **Teks polos, tanpa `parse_mode`.** MarkdownV2 mewajibkan escape pada 18
  karakter; satu judul berita bertanda hubung sudah cukup membuat pesan ditolak.
  Peringatan yang gagal terkirim lebih buruk daripada peringatan yang jelek.

Konfigurasi lewat environment, tidak pernah konstanta di source:

    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

from __future__ import annotations

import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone

import httpx

_API = "https://api.telegram.org/bot{token}/sendMessage"

# Batas keras Telegram untuk satu pesan.
BATAS_PESAN = 4096

# §9 #6 — connect dipisah supaya DNS/proxy yang menggantung tidak menahan job.
TIMEOUT = httpx.Timeout(10.0, connect=5.0)

PERCOBAAN = 3
JEDA_MAKS = 30.0  # batas atas untuk retry_after dari Telegram

# WIB tidak mengenal DST, jadi offset tetap sudah persis benar — dan menghindari
# ketergantungan pada paket `tzdata`, yang tidak ada di Windows secara bawaan.
# §15 #9: simpan UTC di semua lapisan, konversi ke WIB hanya saat tampil.
WIB = timezone(timedelta(hours=7), "WIB")


def aktif() -> bool:
    """True kalau kredensial lengkap. Dipakai `doctor` untuk melaporkan status."""
    return _kredensial() is not None


def kirim_kegagalan(sumber: str, pesan: str, *, run_id: str | None = None) -> bool:
    """Kanal operasional: sesuatu rusak dan butuh tindakan."""
    return _kirim(_susun("GAGAL", sumber, pesan, run_id))


def kirim_anomali(sumber: str, pesan: str, *, run_id: str | None = None) -> bool:
    """Kanal operasional: data lolos parse tapi nilainya mencurigakan (§9)."""
    return _kirim(_susun("ANOMALI", sumber, pesan, run_id))


def kirim_rangkuman(teks: str) -> bool:
    """Kanal isi: rangkuman harian, sudah jadi teks dari `alur/rangkuman.py`.

    Modul ini tidak menyusun isinya. §16 mewajibkan rangkuman di-generate dari
    lapisan gold supaya bisa dibuat ulang untuk tanggal mana pun; kalau
    penyusunannya pindah ke sini, kemampuan itu hilang.
    """
    return _kirim(teks.rstrip())


# --------------------------------------------------------------------------- #
# Internal
# --------------------------------------------------------------------------- #


def _kredensial() -> tuple[str, str] | None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return None
    return token, chat_id


def _stempel(saat: datetime | None = None) -> str:
    saat = saat or datetime.now(timezone.utc)
    return saat.astimezone(WIB).strftime("%d/%m/%Y %H:%M WIB")


def _susun(jenis: str, sumber: str, pesan: str, run_id: str | None) -> str:
    tanda = "❌" if jenis == "GAGAL" else "⚠️"
    baris = [f"{tanda} {jenis} — {sumber}", _stempel(), "", pesan.strip()]
    if run_id:
        baris += ["", f"run: {run_id}"]
    return "\n".join(baris)


def _potong(teks: str, batas: int = BATAS_PESAN) -> list[str]:
    """Pecah pesan panjang di batas baris, bukan di tengah kata.

    Rangkuman harian dengan banyak link gampang melewati 4096 karakter, dan
    Telegram menolak — bukan memotong — pesan yang kelebihan.
    """
    if len(teks) <= batas:
        return [teks]

    ruang = batas - 24  # sisakan tempat untuk penanda bagian
    bagian: list[str] = []
    sekarang: list[str] = []
    panjang = 0

    for baris in teks.split("\n"):
        while len(baris) > ruang:  # satu baris saja sudah kelewat panjang
            if sekarang:
                bagian.append("\n".join(sekarang))
                sekarang, panjang = [], 0
            bagian.append(baris[:ruang])
            baris = baris[ruang:]
        if sekarang and panjang + len(baris) + 1 > ruang:
            bagian.append("\n".join(sekarang))
            sekarang, panjang = [], 0
        sekarang.append(baris)
        panjang += len(baris) + 1

    if sekarang:
        bagian.append("\n".join(sekarang))

    total = len(bagian)
    return [f"{b}\n\n({i}/{total})" for i, b in enumerate(bagian, 1)]


def _verifikasi() -> bool | str:
    """Cara memverifikasi TLS.

    Di balik proxy TLS-inspection kantor, jalan yang benar adalah menunjuk ke
    bundel CA yang memuat sertifikat proxy — bukan mematikan verifikasi. Opsi
    mematikan tetap ada tapi harus dinyalakan sadar lewat environment, tidak
    pernah jadi fallback diam-diam seperti di `IDX Screener`.
    """
    if os.environ.get("NOTIFIKASI_TANPA_VERIFIKASI", "").strip() == "1":
        _lapor("verifikasi TLS DIMATIKAN lewat NOTIFIKASI_TANPA_VERIFIKASI=1")
        return False
    berkas = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    return berkas if berkas else True


def _buat_klien() -> httpx.Client:
    """Titik sisip untuk uji — uji mengganti fungsi ini dengan MockTransport."""
    return httpx.Client(timeout=TIMEOUT, verify=_verifikasi())


def _aman(teks: str, aliran) -> str:
    """Buat teks bisa ditulis ke `aliran` apa pun encoding-nya.

    Console Windows bawaan memakai cp1252, yang tidak bisa mengkodekan emoji di
    pesan-pesan modul ini. Tanpa ini, `print` melempar UnicodeEncodeError dan
    menjatuhkan job — persis yang modul ini janjikan tidak terjadi, dan justru
    di jalur yang paling sering dipakai (terminal, saat Telegram belum diisi).
    """
    encoding = getattr(aliran, "encoding", None) or "utf-8"
    try:
        teks.encode(encoding)
        return teks
    except (UnicodeEncodeError, LookupError):
        # Ganti yang tidak terkodekan, jangan gagal. Peringatan dengan beberapa
        # karakter '?' masih terbaca; peringatan yang melempar tidak.
        return teks.encode(encoding, errors="replace").decode(encoding, errors="replace")


def _tulis(aliran, teks: str) -> None:
    # Satu kali tulis, sesudah teks dipastikan aman — supaya tidak ada
    # kemungkinan separuh baris keburu keluar lalu sisanya melempar.
    aliran.write(_aman(teks, aliran) + "\n")
    aliran.flush()


def _lapor(pesan: str) -> None:
    _tulis(sys.stderr, f"[notifikasi] {pesan}")


def _ke_terminal(teks: str) -> None:
    _tulis(sys.stdout, "\n" + teks + "\n" + "-" * 60)


def _mundur(percobaan: int) -> float:
    """Exponential backoff + jitter (§9 #1)."""
    return min(2.0 ** (percobaan - 1), 8.0) + random.uniform(0.0, 0.5)


def _jeda_429(respons: httpx.Response) -> float | None:
    try:
        retry = respons.json()["parameters"]["retry_after"]
        return min(float(retry), JEDA_MAKS)
    except (ValueError, KeyError, TypeError):
        return None


def _kirim_satu(klien: httpx.Client, url: str, chat_id: str, teks: str) -> bool:
    for percobaan in range(1, PERCOBAAN + 1):
        jeda: float | None = None
        try:
            respons = klien.post(url, data={"chat_id": chat_id, "text": teks})
            if respons.status_code == 200:
                return True
            if respons.status_code == 429:
                jeda = _jeda_429(respons)
            _lapor(f"ditolak: HTTP {respons.status_code} {respons.text[:160]}")
        except httpx.HTTPError as e:
            _lapor(f"tidak terjangkau: {e!r}")

        if percobaan < PERCOBAAN:
            time.sleep(jeda if jeda is not None else _mundur(percobaan))

    return False


def _kirim(teks: str) -> bool:
    """Kirim, atau cetak ke terminal kalau belum terkonfigurasi.

    Selalu mengembalikan bool, tidak pernah melempar: pemanggilnya adalah
    penanganan error, dan penanganan error yang ikut gagal menyembunyikan
    masalah aslinya.
    """
    kredensial = _kredensial()
    if kredensial is None:
        _ke_terminal(teks)
        return False

    token, chat_id = kredensial
    url = _API.format(token=token)

    try:
        with _buat_klien() as klien:
            # Sengaja tidak short-circuit: kalau bagian pertama gagal, bagian
            # sisanya tetap dicoba. Peringatan yang terpotong masih peringatan.
            hasil = [
                _kirim_satu(klien, url, chat_id, potongan)
                for potongan in _potong(teks)
            ]
        return all(hasil)
    except Exception as e:  # noqa: BLE001 — lihat docstring: tidak boleh naik
        _lapor(f"gagal total: {e!r}")
        _ke_terminal(teks)
        return False
