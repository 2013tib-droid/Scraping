"""
dampak.py — nilai seberapa penting tiap peristiwa, sekali sehari, lewat Claude.

Kenapa modul ini ada (ARSITEKTUR.md §16): "berapa banyak media meliput" hanya
membedakan puncaknya. Dari ~550 peristiwa sehari, 95% diliput satu media, jadi
di ekor panjang urutannya efektif "yang paling baru" — dan halaman pagi terisi
berita yang cuma enak diketahui, bukan yang mengubah keputusan.

Yang dilakukan di sini sengaja sempit, dan bukan anti-pattern #8 ("semua artikel
dikirim ke LLM"):

- Masukannya **peristiwa yang sudah ter-dedup**, judul plus sepotong ringkasan —
  bukan 1.000 artikel penuh. Satu panggilan per edisi, bukan per artikel.
- Keluarannya **skala 0–3 plus satu kalimat "kenapa penting"** (§10: keluaran yang
  berguna untuk hilir, bukan sekadar skor sentimen).
- Hasilnya **disimpan di tabel terpisah** per URL dan versi prompt (§6:
  anotasi dipisah dari artikel — model berubah, teks tidak). Edisi yang dibangun
  ulang tidak memanggil API lagi.
- **Tanpa kunci API modul ini diam** dan halaman disusun seperti biasa. Tidak ada
  jalur yang membuat edisi gagal terbit karena penilai tidak tersedia (§9).

Skala:

    3  harus tahu hari ini — menggerakkan pasar atau ekonomi luas
    2  penting — mengubah pandangan tentang sektor/emiten, arah kebijakan
    1  nice to know — menarik, tidak mengubah keputusan
    0  abaikan — seremonial, promosi, daerah kecil, tips, selebriti, kriminal biasa

Halaman memisahkan yang 3 ke blok teratas, menampilkan alasan untuk 2 dan 3, dan
membuang 0 sama sekali.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable

import anthropic

MODEL = "claude-opus-5"

# Naikkan kalau SISTEM atau skemanya berubah — hasil lama tidak akan dipakai lagi.
VERSI_PROMPT = 1

UKURAN_KELOMPOK = 250  # peristiwa per panggilan; cukup kecil untuk satu jawaban
PANJANG_RINGKASAN = 110
PANJANG_ALASAN = 140

SKEMA_TABEL = """
CREATE TABLE IF NOT EXISTS dampak_peristiwa (
    url           VARCHAR NOT NULL,
    versi_prompt  INTEGER NOT NULL,
    model         VARCHAR NOT NULL,
    dampak        INTEGER NOT NULL,      -- 0..3
    alasan        VARCHAR,
    waktu         TIMESTAMP NOT NULL,    -- UTC polos
    PRIMARY KEY (url, versi_prompt)
);
"""

SISTEM = """Kamu analis makro untuk satu investor saham Indonesia yang membaca ringkasan pagi dalam lima menit. Tugasmu memilah: mana yang benar-benar berdampak, mana yang cuma enak diketahui.

Nilai SETIAP nomor yang diberikan dengan skala dampak:

3 = harus tahu hari ini. Menggerakkan IHSG, rupiah, obligasi, atau sektor besar. Contoh: keputusan BI Rate atau The Fed, rilis inflasi/PDB/neraca dagang/cadangan devisa, perubahan APBN, pajak, tarif, atau regulasi sektor yang sudah diputuskan, guncangan politik nasional (reshuffle, konflik lembaga, kebijakan presiden), aksi korporasi emiten besar, bencana atau gejolak sosial berskala nasional, kejutan geopolitik atau harga komoditas utama.
2 = penting. Mengubah pandangan tentang satu sektor atau emiten menengah, arah kebijakan yang sedang dibahas serius, data pendukung yang menguatkan tren, sinyal awal masalah (kredit macet, PHK massal, gagal bayar).
1 = nice to know. Menarik tapi tidak mengubah keputusan apa pun: pernyataan normatif pejabat, proyeksi umum ekonom, kinerja emiten kecil, target perusahaan.
0 = abaikan. Seremonial, peresmian, promosi produk, berita pemda atau daerah kecil, tips dan edukasi, evergreen, selebriti, olahraga, kriminal biasa, kecelakaan, opini tanpa fakta baru.

Pegang ketat. Dari ~500 peristiwa sehari biasanya hanya 3-8 yang bernilai 3 dan 20-40 yang bernilai 2. Jumlah media yang meliput adalah petunjuk, bukan penentu: berita ramai bisa bernilai 1, siaran pers sepi bisa bernilai 3.

Untuk nilai 2 dan 3, isi "k" dengan SATU kalimat maksimal 15 kata, bahasa Indonesia, yang menjelaskan kenapa ini penting bagi investor — jangan mengulang judul. Untuk nilai 0 dan 1, "k" kosong.

Masukan berbentuk satu baris per peristiwa: nomor | kategori | jumlah media | domain | judul — ringkasan."""

SKEMA_JAWABAN = {
    "type": "object",
    "properties": {
        "nilai": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "i": {"type": "integer"},
                    "d": {"type": "integer", "enum": [0, 1, 2, 3]},
                    "k": {"type": "string"},
                },
                "required": ["i", "d", "k"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["nilai"],
    "additionalProperties": False,
}


@dataclass(slots=True, frozen=True)
class Penilaian:
    dampak: int
    alasan: str | None


Pemanggil = Callable[[str], dict]


def aktif() -> bool:
    """True kalau kunci API ada. Tanpa ini, `nilai()` mengembalikan kosong."""
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def nilai(con, peristiwa: list, *, panggil: Pemanggil | None = None) -> dict[str, Penilaian]:
    """Penilaian per URL wakil peristiwa. Kosong kalau penilai tidak tersedia.

    `panggil` adalah titik sisip untuk uji — uji tidak boleh menyentuh jaringan
    (§13). Di produksi dibiarkan None dan Claude yang dipanggil.
    """
    if not peristiwa:
        return {}

    con.execute(SKEMA_TABEL)
    hasil = _dari_cache(con, [p.url for p in peristiwa])
    belum = [p for p in peristiwa if p.url not in hasil]

    if not belum or (panggil is None and not aktif()):
        return hasil

    panggil = panggil or _panggil_claude
    for awal in range(0, len(belum), UKURAN_KELOMPOK):
        kelompok = belum[awal : awal + UKURAN_KELOMPOK]
        try:
            jawaban = panggil(_susun_masukan(kelompok))
        except Exception as e:  # noqa: BLE001 — penilai gagal != edisi gagal
            # Dilaporkan, tidak dilempar: halaman tetap terbit dengan urutan
            # lama, dan yang belum dinilai dicoba lagi saat edisi dibangun ulang.
            _lapor(f"penilaian gagal ({type(e).__name__}): {str(e)[:200]}")
            break
        baru = _tafsir(jawaban, kelompok)
        _simpan(con, baru)
        hasil.update(baru)
        _lapor(f"{len(baru)} dari {len(kelompok)} peristiwa dinilai")

    return hasil


# --------------------------------------------------------------------------- #
# Internal
# --------------------------------------------------------------------------- #


def _susun_masukan(kelompok: list) -> str:
    baris = []
    for i, p in enumerate(kelompok, start=1):
        ringkas = (p.ringkasan or "")[:PANJANG_RINGKASAN].strip()
        ekor = f" — {ringkas}" if ringkas else ""
        baris.append(f"{i} | {p.kategori} | {p.jumlah_media} media | {p.domain} | {p.judul}{ekor}")
    return "\n".join(baris)


def _panggil_claude(teks: str) -> dict:
    klien = anthropic.Anthropic()
    # Streaming supaya jawaban panjang (ratusan objek JSON) tidak kena timeout HTTP.
    with klien.messages.stream(
        model=MODEL,
        max_tokens=32000,
        system=SISTEM,
        messages=[{"role": "user", "content": teks}],
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": SKEMA_JAWABAN},
        },
    ) as aliran:
        pesan = aliran.get_final_message()

    if pesan.stop_reason == "refusal":
        raise RuntimeError("permintaan ditolak model")
    jawaban = next(b.text for b in pesan.content if b.type == "text")
    return json.loads(jawaban)


def _tafsir(jawaban: dict, kelompok: list) -> dict[str, Penilaian]:
    """Cocokkan nomor ke URL. Nomor yang tidak dikenal atau hilang dilewati —
    yang hilang tetap tidak ter-cache, jadi dicoba lagi lain kali."""
    hasil: dict[str, Penilaian] = {}
    for baris in jawaban.get("nilai", []):
        try:
            i, d = int(baris["i"]), int(baris["d"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 1 <= i <= len(kelompok):
            continue
        d = max(0, min(3, d))
        alasan = str(baris.get("k") or "").strip()[:PANJANG_ALASAN] or None
        hasil[kelompok[i - 1].url] = Penilaian(d, alasan if d >= 2 else None)
    return hasil


def _dari_cache(con, url: Iterable[str]) -> dict[str, Penilaian]:
    url = list(url)
    if not url:
        return {}
    baris = con.execute(
        f"""SELECT url, dampak, alasan FROM dampak_peristiwa
            WHERE versi_prompt = ? AND url IN ({",".join("?" * len(url))})""",
        [VERSI_PROMPT, *url],
    ).fetchall()
    return {u: Penilaian(d, a) for u, d, a in baris}


def _simpan(con, hasil: dict[str, Penilaian]) -> None:
    if not hasil:
        return
    kini = datetime.now(timezone.utc).replace(tzinfo=None)
    con.executemany(
        """INSERT INTO dampak_peristiwa (url, versi_prompt, model, dampak, alasan, waktu)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT (url, versi_prompt) DO NOTHING""",
        [(u, VERSI_PROMPT, MODEL, n.dampak, n.alasan, kini) for u, n in hasil.items()],
    )


def _lapor(pesan: str) -> None:
    sys.stderr.write(f"[dampak] {pesan}\n")
    sys.stderr.flush()
