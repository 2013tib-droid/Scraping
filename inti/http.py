"""
http.py — satu-satunya klien HTTP sistem ini.

Semua pengambilan lewat sini, supaya aturan di ARSITEKTUR.md §9 dipasang sekali
dan berlaku untuk semua sumber, bukan diulang (dan lupa diulang) per modul.

Yang dipasang di sini:

- **Timeout eksplisit** di setiap request (§9 #6). Default sebagian library tak
  terbatas; satu koneksi menggantung bisa membekukan job sampai batas 6 jam.
- **Retry + exponential backoff + jitter** (§9 #1). Tanpa jitter, semua target
  di-retry serempak dan pola bebannya terlihat seperti serangan.
- **Rate limit per domain**, bukan global (§9 #2). Situs pemerintah sering di
  server lemah; 1 request/detik sudah sopan dan cukup.
- **Conditional request** — `If-None-Match` / `If-Modified-Since` (§9 #3). Respons
  304 hemat bandwidth di kedua sisi dan lebih cepat.
- **User-Agent jujur dengan alamat kontak** (§9 #4), dan dipastikan ASCII.

Catatan environment (SUMBER-DATA.md §C1): di jaringan dengan proxy
TLS-inspection, bundel CA bawaan Python menolak hampir semua host. `truststore`
membuat Python memakai certificate store sistem. Ini penawar yang benar — bukan
mematikan verifikasi.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urlsplit

import truststore

truststore.inject_into_ssl()

import httpx

# Kontak wajib ada supaya admin bisa mengirim email sebelum memblokir IP (§9 #4).
UA = "intel-makro/0.1 (+kontak: 2013.tib@gmail.com) pengumpul RSS pribadi"

TIMEOUT = httpx.Timeout(30.0, connect=10.0)
PERCOBAAN = 3
JEDA_DOMAIN = 1.0  # detik minimum antar-request ke domain yang sama

# Status yang layak dicoba ulang. 4xx lain berarti permintaan kita yang salah —
# mengulanginya hanya menambah beban tanpa mengubah hasil.
ULANGI = {408, 425, 429, 500, 502, 503, 504}


@dataclass(slots=True)
class Respons:
    url: str
    status: int
    isi: bytes
    etag: str | None
    last_modified: str | None
    waktu: datetime  # UTC, saat fetch
    durasi: float
    hash_isi: str | None

    @property
    def tidak_berubah(self) -> bool:
        """304 — isi sama seperti terakhir kali; tidak perlu diproses ulang."""
        return self.status == 304

    @property
    def berhasil(self) -> bool:
        return self.status == 200 and bool(self.isi)


class Klien:
    """Klien dengan rate limit per domain. Dipakai sebagai context manager."""

    def __init__(self, ua: str = UA, jeda_domain: float = JEDA_DOMAIN) -> None:
        # Header HTTP harus latin-1. UA dengan em dash membuat httpx melempar
        # UnicodeEncodeError sebelum request keluar, dan gejalanya terlihat
        # seperti semua situs mati serempak. Gagal di sini, bukan di lapangan.
        ua.encode("ascii")
        self._ua = ua
        self._jeda_domain = jeda_domain
        self._terakhir: dict[str, float] = {}
        self._klien = httpx.Client(
            timeout=TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"},
        )

    def __enter__(self) -> "Klien":
        return self

    def __exit__(self, *_) -> None:
        self.tutup()

    def tutup(self) -> None:
        self._klien.close()

    def ambil(
        self,
        url: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> Respons:
        """Ambil satu URL. Melempar httpx.HTTPError kalau semua percobaan gagal."""
        header: dict[str, str] = {}
        if etag:
            header["If-None-Match"] = etag
        if last_modified:
            header["If-Modified-Since"] = last_modified

        galat: Exception | None = None
        for percobaan in range(1, PERCOBAAN + 1):
            self._tunggu_giliran(url)
            mulai = time.monotonic()
            try:
                r = self._klien.get(url, headers=header)
            except httpx.HTTPError as e:
                galat = e
            else:
                if r.status_code not in ULANGI:
                    isi = r.content if r.status_code == 200 else b""
                    return Respons(
                        url=str(r.url),
                        status=r.status_code,
                        isi=isi,
                        etag=r.headers.get("etag"),
                        last_modified=r.headers.get("last-modified"),
                        waktu=datetime.now(timezone.utc),
                        durasi=time.monotonic() - mulai,
                        hash_isi=sha256(isi).hexdigest() if isi else None,
                    )
                galat = httpx.HTTPStatusError(
                    f"HTTP {r.status_code}", request=r.request, response=r
                )

            if percobaan < PERCOBAAN:
                time.sleep(_mundur(percobaan))

        raise galat if galat else httpx.HTTPError("gagal tanpa sebab yang tercatat")

    def _tunggu_giliran(self, url: str) -> None:
        """Rate limit per domain (§9 #2), bukan global."""
        domain = urlsplit(url).netloc
        sisa = self._jeda_domain - (time.monotonic() - self._terakhir.get(domain, 0.0))
        if sisa > 0:
            time.sleep(sisa)
        self._terakhir[domain] = time.monotonic()


def _mundur(percobaan: int) -> float:
    """Exponential backoff + jitter (§9 #1)."""
    return min(2.0 ** (percobaan - 1), 8.0) + random.uniform(0.0, 0.5)
