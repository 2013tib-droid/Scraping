"""
edisi.py — susun halaman pagi untuk satu tanggal.

Langkah kedua dari dua (ARSITEKTUR.md §16). Modul ini **tidak** mengambil apa pun
dari jaringan; ia membaca artikel yang sudah tersimpan. Karena tanggalnya
parameter, edisi tanggal berapa pun bisa dibangun ulang kapan saja — kalau logika
dedup atau tampilannya diperbaiki bulan depan, seluruh arsip bisa di-render ulang.

Alurnya:

    jendela waktu  ->  ambil artikel  ->  kelompokkan peristiwa
                   ->  urutkan  ->  batasi per bagian  ->  halaman HTML

Penyusutan dari ~1.000 artikel jadi ~35 peristiwa hampir seluruhnya terjadi di
dua langkah terakhir. Dedup hanya menggabungkan liputan ganda (1.028 -> ~905 pada
data nyata); yang benar-benar memangkas adalah **pemeringkatan dan pembatasan**.
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from inti import notifikasi, render
from inti.dedup import kelompokkan
from inti.penyimpanan import buka

WIB = timezone(timedelta(hours=7), "WIB")
JAM_EDISI = time(5, 0)  # 05:00 WIB — §16

# Batas per bagian. Ini fitur, bukan keterbatasan: halaman yang tidak habis dalam
# lima menit tidak akan dibaca sama sekali.
BATAS = {"makro": 12, "pasar": 10, "politik": 6, "global": 8}

KELUARAN = Path("docs")

# Bagian politik ditarik dari feed berita umum (Detik news, CNN nasional), jadi
# isinya bercampur kriminal, selebriti, dan kecelakaan. Yang diminta di §16 adalah
# politik & sosial "yang berpotensi menggerakkan pasar", jadi bagian ini — dan
# hanya bagian ini — disaring kata kunci.
#
# Saringan kasar dan sengaja begitu: daftarnya bisa dibaca dan diubah dalam satu
# menit, dan kalau ada yang lolos atau terbuang, alasannya kelihatan. Klasifikasi
# yang lebih pintar baru sepadan kalau ini terbukti tidak cukup.
KATA_POLITIK = {
    "kebijakan", "pemerintah", "presiden", "wapres", "menteri", "kementerian",
    "dpr", "dpd", "mpr", "ruu", "undang", "perpres", "perppu", "permen", "pp",
    "kabinet", "apbn", "apbd", "anggaran", "pajak", "cukai", "subsidi", "bansos",
    "tarif", "impor", "ekspor", "bumn", "regulasi", "aturan", "izin", "moneter",
    "fiskal", "ekonomi", "investasi", "industri", "perdagangan", "upah", "buruh",
    "demo", "unjuk", "mogok", "pemilu", "pilkada", "koalisi", "reshuffle",
    "korupsi", "kpk", "kejaksaan", "ojk", "bi", "sri", "purbaya", "prabowo",
    "utang", "defisit", "inflasi", "rupiah", "pertamina", "pln", "energi",
    "pangan", "beras", "bbm", "sawit", "nikel", "tambang", "infrastruktur",
    # Sosial yang menggerakkan pasar: bencana mengganggu rantai pasok, PHK dan
    # upah menggeser konsumsi, program besar seperti MBG menggeser anggaran.
    "karhutla", "bencana", "banjir", "gempa", "erupsi", "phk", "mbg", "gaji",
    "ump", "umk", "listrik", "harga", "bpjs", "kesehatan", "pendidikan",
}

# Feed bank sentral memuat pidato, wawancara, dan "fireside chat" — bukan hanya
# keputusan. Bobotnya (feed.toml) mengangkat semuanya sama rata, sehingga sebuah
# obrolan santai bisa memuncaki bagian Global. Yang layak diangkat hanya yang
# menyebut keputusan, pernyataan, atau notulen kebijakan.
DOMAIN_BANK_SENTRAL = {"federalreserve.gov", "ecb.europa.eu"}
KATA_BANK_SENTRAL = {
    "decision", "decisions", "statement", "fomc", "minutes", "monetary",
    "rate", "rates", "policy", "projections", "press", "conference",
}


@dataclass(slots=True)
class Peristiwa:
    judul: str
    url: str
    domain: str
    ringkasan: str | None
    waktu_terbit: datetime | None
    kategori: str
    jumlah_media: int
    bobot: float
    juga: list[tuple[str, str]] = field(default_factory=list)

    @property
    def skor(self) -> float:
        """Berapa banyak media meliput = seberapa penting (§16).

        Bobot feed ikut berperan supaya siaran pers bank sentral — yang hampir
        tidak pernah diliput ulang media Indonesia — tidak selalu kalah dari
        berita ramai.
        """
        return self.jumlah_media * self.bobot


def jendela(tanggal: date) -> tuple[datetime, datetime]:
    """Jendela edisi dalam UTC polos: 05:00 WIB kemarin sampai 05:00 WIB tanggal ini.

    Cron GitHub Actions memakai UTC, dan 05:00 WIB adalah 22:00 UTC hari
    sebelumnya. Dihitung dari parameter tanggal, bukan dari `now()`, supaya edisi
    lama bisa dibangun ulang persis.
    """
    akhir_wib = datetime.combine(tanggal, JAM_EDISI, tzinfo=WIB)
    mulai_wib = akhir_wib - timedelta(days=1)
    ke_utc = lambda d: d.astimezone(timezone.utc).replace(tzinfo=None)  # noqa: E731
    return ke_utc(mulai_wib), ke_utc(akhir_wib)


def ambil(con, mulai: datetime, akhir: datetime) -> list[dict]:
    baris = con.execute(
        """SELECT judul, url, domain, ringkasan, waktu_terbit, kategori, bobot
           FROM artikel
           WHERE waktu_terbit >= ? AND waktu_terbit < ?
           ORDER BY waktu_terbit DESC""",
        [mulai, akhir],
    ).fetchall()
    kolom = ("judul", "url", "domain", "ringkasan", "waktu_terbit", "kategori", "bobot")
    return [dict(zip(kolom, b)) for b in baris]


def _wakil(anggota: list[dict], kelaziman: Counter) -> dict:
    """Pilih satu artikel mewakili peristiwa.

    Urutan pertimbangan:

    1. **Punya ringkasan.** Judul tanpa konteks memaksa mengklik untuk tahu isinya.
    2. **Ringkasan terpanjang.**
    3. **Media yang paling banyak menerbitkan** di jendela ini. Feed Google News
       ikut membawa media lokal kecil; tanpa ini satu peristiwa nasional bisa
       diwakili `acehtimes.co.id` alih-alih penerbit yang meliputnya penuh.
       Kelaziman dipakai sebagai proxy supaya tidak perlu daftar media pilihan
       yang harus dirawat manual.
    4. Terakhir: yang lebih dulu terbit.
    """
    return max(
        anggota,
        key=lambda a: (
            bool(a["ringkasan"]),
            len(a["ringkasan"] or ""),
            kelaziman[a["domain"]],
            -(a["waktu_terbit"] or datetime.max).timestamp(),
        ),
    )


def jadikan_peristiwa(artikel: list[dict]) -> list[Peristiwa]:
    if not artikel:
        return []

    # Seberapa produktif tiap media di jendela ini — proxy "media besar".
    kelaziman = Counter(a["domain"] for a in artikel)

    peristiwa: list[Peristiwa] = []
    for indeks in kelompokkan([a["judul"] for a in artikel]):
        anggota = [artikel[i] for i in indeks]
        utama = _wakil(anggota, kelaziman)

        domain_lain: dict[str, str] = {}
        for a in anggota:
            if a["domain"] != utama["domain"]:
                domain_lain.setdefault(a["domain"], a["url"])

        peristiwa.append(
            Peristiwa(
                judul=utama["judul"],
                url=utama["url"],
                domain=utama["domain"],
                ringkasan=utama["ringkasan"],
                waktu_terbit=utama["waktu_terbit"],
                # Kategori kelompok = yang terbanyak di antara anggotanya.
                kategori=Counter(a["kategori"] for a in anggota).most_common(1)[0][0],
                jumlah_media=len({a["domain"] for a in anggota}),
                bobot=max(a["bobot"] for a in anggota),
                juga=sorted(domain_lain.items()),
            )
        )
    return peristiwa


def _kata(teks: str) -> set[str]:
    return set("".join(c if c.isalnum() else " " for c in teks.lower()).split())


def relevan(p: Peristiwa) -> bool:
    """Dua saringan sempit; bagian lain lewat apa adanya karena sudah dari feed
    ekonomi."""
    if p.domain in DOMAIN_BANK_SENTRAL:
        return bool(_kata(p.judul) & KATA_BANK_SENTRAL)
    if p.kategori == "politik":
        return bool(_kata(f"{p.judul} {p.ringkasan or ''}") & KATA_POLITIK)
    return True


def per_bagian(peristiwa: list[Peristiwa]) -> dict[str, list[Peristiwa]]:
    bagian: dict[str, list[Peristiwa]] = {}
    for kategori, batas in BATAS.items():
        terpilih = sorted(
            (p for p in peristiwa if p.kategori == kategori and relevan(p)),
            key=lambda p: (
                -p.skor,
                -(p.waktu_terbit or datetime.min).timestamp(),
            ),
        )
        bagian[kategori] = terpilih[:batas]
    return bagian


def bangun(con, tanggal: date) -> tuple[str, dict[str, list[Peristiwa]], int]:
    mulai, akhir = jendela(tanggal)
    artikel = ambil(con, mulai, akhir)
    bagian = per_bagian(jadikan_peristiwa(artikel))
    html = render.halaman(
        datetime.combine(tanggal, JAM_EDISI),
        bagian,
        jumlah_sumber=len({a["domain"] for a in artikel}),
        total_dipertimbangkan=len(artikel),
    )
    return html, bagian, len(artikel)


def tulis(html: str, tanggal: date, keluaran: Path | None = None) -> Path:
    akar = keluaran or KELUARAN
    (akar / "arsip").mkdir(parents=True, exist_ok=True)
    arsip = akar / "arsip" / f"{tanggal:%Y-%m-%d}.html"
    arsip.write_text(html, encoding="utf-8")
    # index.html selalu edisi terbaru — satu URL yang bisa di-bookmark.
    (akar / "index.html").write_text(html, encoding="utf-8")
    return arsip


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    # Tanpa argumen: edisi hari ini menurut WIB.
    tanggal = (
        date.fromisoformat(argv[0])
        if argv
        else datetime.now(WIB).date()
    )

    con = buka()
    try:
        html, bagian, total = bangun(con, tanggal)
    finally:
        con.close()

    berkas = tulis(html, tanggal)
    dipilih = sum(len(v) for v in bagian.values())
    print(f"edisi {tanggal}: {dipilih} peristiwa dari {total} artikel -> {berkas}")

    if not dipilih:
        # Halaman kosong hampir selalu berarti pengambilnya tidak jalan, bukan
        # dunia sedang sepi (§9: diam bukan tanda sehat).
        notifikasi.kirim_kegagalan(
            "edisi", f"Edisi {tanggal} kosong — {total} artikel di jendela waktunya."
        )
        return 1

    rincian = ", ".join(f"{k} {len(v)}" for k, v in bagian.items() if v)
    notifikasi.kirim_rangkuman(
        f"Ringkas Pagi {tanggal:%d/%m}\n{dipilih} peristiwa ({rincian})\n"
        f"dari {total} artikel semalam."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
