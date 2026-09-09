"""
berita.py — ambil semua feed, simpan mentah, catat artikel.

Langkah pertama dari dua (ARSITEKTUR.md §16). Modul ini **tidak** menyusun
halaman dan tidak memutuskan apa yang layak dibaca; tugasnya hanya memastikan
teksnya tersimpan. Teks yang tidak dikumpulkan hari ini tidak bisa dikumpulkan
retroaktif — itu alasan pemisahannya.

Jalan sekali sehari 05:00 WIB (§16). Kalau gagal, yang rusak satu feed, bukan
seluruh run: tiap feed ditangani sendiri dan kegagalannya dicatat lalu
dilaporkan sekaligus di akhir — bukan 30 pesan Telegram terpisah.
"""

from __future__ import annotations

import html
import re
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import feedparser

from inti import notifikasi
from inti.http import Klien
from inti.penyimpanan import (
    Artikel,
    ambil_state,
    buka,
    catat_run,
    simpan_artikel,
    simpan_bronze,
    simpan_state,
)

BERKAS_FEED = Path("sumber/feed.toml")

# Parameter pelacakan yang tidak mengubah isi halaman. Dibuang supaya URL yang
# sama dari sumber berbeda menghasilkan artikel_id yang sama.
PARAM_BUANG = ("utm_", "fbclid", "gclid", "ref", "source")

MAKS_RINGKASAN = 400
TAG = re.compile(r"<[^>]+>")
SPASI = re.compile(r"\s+")


@dataclass(slots=True)
class Ringkasan:
    run_id: str
    diperiksa: int = 0
    tidak_berubah: int = 0
    gagal: list[tuple[str, str]] = field(default_factory=list)
    item: int = 0
    baru: int = 0

    def teks(self) -> str:
        baris = [
            f"feed diperiksa : {self.diperiksa}",
            f"tidak berubah  : {self.tidak_berubah}",
            f"item terbaca   : {self.item}",
            f"artikel baru   : {self.baru}",
            f"gagal          : {len(self.gagal)}",
        ]
        for nama, sebab in self.gagal:
            baris.append(f"  - {nama}: {sebab}")
        return "\n".join(baris)


def muat_feed(berkas: Path = BERKAS_FEED) -> list[dict]:
    return tomllib.loads(berkas.read_text(encoding="utf-8"))["feed"]


def kanonik(url: str) -> str:
    """Buang fragment dan parameter pelacakan, supaya dedup bekerja."""
    bagian = urlsplit(url)
    query = "&".join(
        p
        for p in bagian.query.split("&")
        if p and not p.lower().startswith(PARAM_BUANG)
    )
    return urlunsplit((bagian.scheme, bagian.netloc, bagian.path, query, ""))


def bersihkan(teks: str | None) -> str | None:
    """Buang tag HTML dari ringkasan feed. Tanpa parser — ini bukan dokumen."""
    if not teks:
        return None
    polos = SPASI.sub(" ", html.unescape(TAG.sub(" ", teks))).strip()
    if not polos:
        return None
    return polos[:MAKS_RINGKASAN]


def _ringkasan_berguna(ringkasan: str | None, judul: str) -> str | None:
    """Buang ringkasan yang cuma mengulang judulnya.

    Google News mengisi `summary` dengan judul + nama penerbit, jadi tanpa ini
    setiap itemnya tampil dua kali: sekali sebagai judul, sekali sebagai
    "ringkasan" yang tidak menambah apa pun.
    """
    if not ringkasan:
        return None
    sederhana = lambda s: "".join(c for c in s.lower() if c.isalnum())  # noqa: E731
    return None if sederhana(ringkasan).startswith(sederhana(judul)[:60]) else ringkasan


def waktu_terbit(entri) -> datetime | None:
    t = entri.get("published_parsed") or entri.get("updated_parsed")
    # feedparser sudah menormalkan ke UTC; offset feed (mis. +0700) sudah
    # diperhitungkan. §15 #9 — simpan UTC, konversi ke WIB hanya saat tampil.
    return datetime(*t[:6], tzinfo=timezone.utc) if t else None


def ke_artikel(entri, feed: dict, saat_fetch: datetime) -> Artikel | None:
    tautan = (entri.get("link") or "").strip()
    judul = (entri.get("title") or "").strip()
    if not tautan or not judul:
        return None  # tanpa salah satunya, item ini tidak bisa dipakai

    # Bentuk kanonik hanya untuk ID. URL yang disimpan tetap yang asli — membuang
    # parameter bisa membuat tautannya mati saat diklik, dan halaman pagi ini
    # isinya sebagian besar memang tautan (§11).
    url = tautan.split("#", 1)[0]
    isi = entri.get("content")

    # Item Google News menunjuk ke news.google.com, padahal yang penting adalah
    # penerbit aslinya: kalau tidak diurai, tiga berita dari tiga media terhitung
    # satu domain dan pemeringkatan lintas-media (§16) jadi salah. `source.href`
    # menormalkan ke domain yang sama dengan feed langsung penerbit itu.
    sumber = entri.get("source") or {}
    asal = sumber.get("href")
    domain = urlsplit(asal or url).netloc.removeprefix("www.")

    # Google News menempelkan " - Penerbit" di ujung judul. Itu mengotori
    # tampilan sekaligus menggeser token yang dipakai dedup.
    if nama_sumber := sumber.get("title"):
        judul = judul.removesuffix(f" - {nama_sumber}").strip()

    return Artikel(
        artikel_id=sha256(kanonik(tautan).encode("utf-8")).hexdigest(),
        url=url,
        domain=domain,
        judul=html.unescape(judul),
        ringkasan=_ringkasan_berguna(
            bersihkan((isi[0].get("value") if isi else None) or entri.get("summary")),
            judul,
        ),
        waktu_terbit=waktu_terbit(entri),
        waktu_fetch=saat_fetch,
        feed=feed["nama"],
        kategori=feed["kategori"],
        bobot=float(feed.get("bobot", 1.0)),
    )


def proses_satu(con, klien: Klien, feed: dict, run_id: str, ringkas: Ringkasan) -> None:
    nama, url = feed["nama"], feed["url"]
    ringkas.diperiksa += 1
    etag, last_modified = ambil_state(con, url)

    try:
        r = klien.ambil(url, etag=etag, last_modified=last_modified)
    except Exception as e:  # noqa: BLE001 — satu feed rusak tidak menjatuhkan run
        ringkas.gagal.append((nama, f"{type(e).__name__}: {str(e)[:80]}"))
        catat_run(con, run_id, nama, "galat", catatan=f"{type(e).__name__}")
        return

    if r.tidak_berubah:
        ringkas.tidak_berubah += 1
        catat_run(con, run_id, nama, "304", durasi=r.durasi)
        return

    if not r.berhasil:
        ringkas.gagal.append((nama, f"HTTP {r.status}"))
        catat_run(con, run_id, nama, "galat", durasi=r.durasi,
                  catatan=f"HTTP {r.status}")
        return

    simpan_bronze(nama, r)

    terurai = feedparser.parse(r.isi)
    artikel = [a for e in terurai.entries if (a := ke_artikel(e, feed, r.waktu))]
    baru = simpan_artikel(con, artikel)

    ringkas.item += len(artikel)
    ringkas.baru += baru
    simpan_state(con, url, r.etag, r.last_modified, r.hash_isi)
    catat_run(con, run_id, nama, "ok", jumlah_item=len(artikel),
              jumlah_baru=baru, durasi=r.durasi)

    # §9: parser yang sukses tapi menghasilkan 0 baris adalah kegagalan diam.
    if not artikel:
        ringkas.gagal.append((nama, "0 item terbaca dari respons 200"))


def jalankan(con, klien: Klien, feed: list[dict], run_id: str) -> Ringkasan:
    ringkas = Ringkasan(run_id=run_id)
    for f in feed:
        proses_satu(con, klien, f, run_id, ringkas)
    return ringkas


def main() -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    feed = muat_feed()
    con = buka()
    try:
        with Klien() as klien:
            ringkas = jalankan(con, klien, feed, run_id)
    finally:
        con.close()

    print(ringkas.teks())

    if ringkas.gagal:
        notifikasi.kirim_kegagalan(
            "berita", f"{len(ringkas.gagal)} feed bermasalah:\n" + ringkas.teks(),
            run_id=run_id,
        )
    # Semua feed gagal berarti masalahnya bukan di feed — jaringan, proxy, atau
    # kredensial. Bedakan dari kegagalan sebagian supaya tidak terbaca sama.
    return 1 if len(ringkas.gagal) == ringkas.diperiksa else 0


if __name__ == "__main__":
    sys.exit(main())
