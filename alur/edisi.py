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

from inti import dampak, notifikasi, pajak, render, sentimen
from inti.dedup import kelompokkan
from inti.penyimpanan import buka

WIB = timezone(timedelta(hours=7), "WIB")
JAM_EDISI = time(5, 0)  # 05:00 WIB — §16

# Batas per bagian. Ini fitur, bukan keterbatasan: halaman yang tidak habis dalam
# lima menit tidak akan dibaca sama sekali.
#
# Perpajakan diisi dari isi berita, bukan dari feed (inti/pajak.py): berita
# pajak yang dulu menumpang di Makro pindah ke sini, jadi Makro tidak kehilangan
# tempat untuk berita lain.
BATAS = {"makro": 12, "pajak": 10, "pasar": 10, "politik": 6, "global": 8}

# Blok "Penting Pagi Ini": peristiwa berdampak 3 menurut penilai (inti/dampak.py),
# lintas kategori. Kosong pada hari yang memang sepi, dan itu jawaban yang benar.
BATAS_UTAMA = 6

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
    # URL thumbnail dari feed penerbit; None untuk sekitar sepertiga sumber.
    # Hanya dipakai di kartu sorotan — lihat inti/render.py.
    gambar: str | None = None
    juga: list[tuple[str, str]] = field(default_factory=list)
    # Diisi oleh inti/dampak.py di `bangun()`; None hanya sebelum itu.
    dampak: int | None = None
    alasan: str | None = None
    # Diisi oleh inti/sentimen.py di `bangun()`: "positif", "negatif", atau
    # "netral". `pemicu` adalah frasa yang menentukannya, untuk ditelusuri
    # kalau labelnya meleset.
    sentimen: str | None = None
    pemicu: str | None = None
    # Diisi di `bangun()` hanya untuk peristiwa yang berakhir di bagian
    # Perpajakan: daerah/pusat, buang, dan subtopiknya (inti/pajak.py).
    klasifikasi_pajak: pajak.Klasifikasi | None = None

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
        """SELECT judul, url, domain, ringkasan, waktu_terbit, kategori, bobot, gambar
           FROM artikel
           WHERE waktu_terbit >= ? AND waktu_terbit < ?
           ORDER BY waktu_terbit DESC""",
        [mulai, akhir],
    ).fetchall()
    kolom = ("judul", "url", "domain", "ringkasan", "waktu_terbit", "kategori",
             "bobot", "gambar")
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
                # Gambar diambil dari wakil yang sama dengan judul dan
                # tautannya, bukan dari anggota mana pun yang kebetulan punya.
                # Meminjam foto redaksi lain untuk berita yang tautannya ke
                # redaksi ini akan salah atribusi — dan kadang salah peristiwa,
                # karena dedup mencocokkan kemiripan judul, bukan isi.
                gambar=utama["gambar"],
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


def tandai_pajak(peristiwa: list[Peristiwa]) -> None:
    """Pindahkan berita pajak ke bagian Perpajakan dan beri subtopiknya.

    Dua jalan masuk: feed yang seluruh isinya pajak (kategori `pajak` di
    feed.toml), atau berita Makro/Politik yang isinya pajak. Harus jalan
    setelah penilai dampak — yang ditimpa di sini adalah `alasan`-nya.
    """
    for p in peristiwa:
        k = pajak.periksa(p)
        if p.kategori != "pajak" and not (k.pajak and p.kategori in pajak.DAPAT_PINDAH):
            continue
        p.kategori, p.klasifikasi_pajak = "pajak", k
        # Penilai dampak memberi 2 pada apa pun yang menyebut "pajak" atau
        # "cukai", tapi tidak kenal "PPN", "SPP-TDLN", atau "Coretax". Tanpa
        # ini, "SPP-TDLN Berlaku 10 September" — berita pajak kunci 9 Sep —
        # jatuh di bawah siaran pers pemda yang kebetulan menyebut "pajak".
        if p.dampak == 1 and not k.daerah:
            p.dampak = 2
        # Di bagian yang semua isinya pajak, "Regulasi" tidak menerangkan apa
        # pun; "Restitusi" atau "Penegakan hukum" menerangkan. Dampak 3
        # dibiarkan: labelnya menjelaskan kenapa ia naik ke blok utama.
        if k.topik and p.dampak != 3:
            p.alasan = k.topik


def _lolos(p: Peristiwa) -> bool:
    """Dua saringan yang menumpuk, bukan saling menggantikan.

    `relevan()` adalah daftar-izin: bagian politik harus menyentuh kata ekonomi,
    feed bank sentral harus menyentuh kata kebijakan. `dampak == 0` adalah
    daftar-tolak: seremonial, olahraga, kriminal. Keduanya menangkap hal yang
    berbeda, jadi keduanya dipakai — daftar-tolak tidak bisa menebak apa yang
    *tidak* ekonomi, dan daftar-izin tidak menyaring peresmian pabrik.

    Bagian Perpajakan punya daftar-tolak ketiga (brevet, seminar, halaman tag)
    yang sengaja tidak berlaku di bagian lain — lihat inti/pajak.py."""
    k = p.klasifikasi_pajak
    return relevan(p) and p.dampak != 0 and not (k and k.buang)


def _urutan(p: Peristiwa) -> tuple:
    # Dampak dulu (kalau ada), lalu jumlah media, lalu yang terbaru.
    #
    # Di bagian Perpajakan, pajak daerah selalu di bawah pajak pusat, apa pun
    # dampaknya. Tanpa ini, siaran pers pemda soal pemutihan PKB — yang lolos
    # sebagai dampak 2 karena menyebut "pajak" — mengisi separuh bagiannya.
    # Dan di antara yang sama-sama diliput satu media, yang punya subtopik
    # (Restitusi, Coretax, ...) di atas yang cuma menyebut "pajak": yang kedua
    # itu sebagian besar opini, panduan, dan berita investasi luar negeri.
    k = p.klasifikasi_pajak
    return (
        bool(k and k.daerah),
        -(p.dampak or 0),
        -p.skor,
        bool(k and not k.topik),
        -(p.waktu_terbit or datetime.min).timestamp(),
    )


def per_bagian(peristiwa: list[Peristiwa]) -> dict[str, list[Peristiwa]]:
    bagian: dict[str, list[Peristiwa]] = {}
    terpakai: set[int] = set()

    # `_lolos` juga berlaku di sini. Tanpa itu, pidato pejabat Fed yang
    # menyebut "federal reserve" bisa menembus blok teratas justru lewat pintu
    # yang dibuat untuk mengangkatnya — padahal DOMAIN_BANK_SENTRAL ada supaya
    # yang naik hanya yang menyebut keputusan.
    utama = sorted(
        (p for p in peristiwa if p.dampak == 3 and _lolos(p)), key=_urutan
    )[:BATAS_UTAMA]
    if utama:
        bagian["utama"] = utama
        terpakai = {id(p) for p in utama}

    for kategori, batas in BATAS.items():
        terpilih = sorted(
            (
                p for p in peristiwa
                if p.kategori == kategori and id(p) not in terpakai and _lolos(p)
            ),
            key=_urutan,
        )
        bagian[kategori] = terpilih[:batas]
    return bagian


def bangun(con, tanggal: date) -> tuple[str, dict[str, list[Peristiwa]], int]:
    mulai, akhir = jendela(tanggal)
    artikel = ambil(con, mulai, akhir)
    peristiwa = jadikan_peristiwa(artikel)

    # Penilaian dampak menempel ke peristiwa, bukan ke artikel: yang dinilai
    # adalah "kejadian"-nya, dan URL wakil stabil untuk kelompok yang sama.
    penilaian = dampak.nilai(peristiwa)
    for p in peristiwa:
        if n := penilaian.get(p.url):
            p.dampak, p.alasan = n.dampak, n.alasan

    # Status arah — positif/negatif/netral. Dipisah dari dampak karena
    # menjawab pertanyaan lain: dampak menyaring dan mengurutkan, sentimen
    # hanya menerangkan. Tidak ikut `_urutan` dan tidak membuang apa pun;
    # berita buruk bukan berita yang kurang penting.
    status = sentimen.nilai(peristiwa)
    for p in peristiwa:
        if s := status.get(p.url):
            p.sentimen, p.pemicu = s.label, s.pemicu

    tandai_pajak(peristiwa)
    bagian = per_bagian(peristiwa)
    # Tautan ke edisi kemarin hanya kalau berkasnya memang ada di arsip —
    # tautan mati lebih buruk daripada tidak ada tautan.
    kemarin = tanggal - timedelta(days=1)
    sebelumnya = (
        f"arsip/{kemarin:%Y-%m-%d}.html"
        if (KELUARAN / "arsip" / f"{kemarin:%Y-%m-%d}.html").exists()
        else None
    )
    html = render.halaman(
        datetime.combine(tanggal, JAM_EDISI),
        bagian,
        jumlah_sumber=len({a["domain"] for a in artikel}),
        total_dipertimbangkan=len(artikel),
        sebelumnya=sebelumnya,
    )
    return html, bagian, len(artikel)


def tulis(html: str, tanggal: date, keluaran: Path | None = None) -> Path:
    akar = keluaran or KELUARAN
    (akar / "arsip").mkdir(parents=True, exist_ok=True)
    arsip = akar / "arsip" / f"{tanggal:%Y-%m-%d}.html"
    # Salinan di arsip/ berada satu folder lebih dalam, jadi tautan
    # "arsip/..." yang benar dari index.html harus jadi tautan sesama folder.
    arsip.write_text(html.replace('href="arsip/', 'href="'), encoding="utf-8")
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
    # Yang berdampak tinggi ikut di pesan: itu yang mau dibaca dari notifikasi
    # tanpa harus membuka halaman dulu.
    # Arahnya ikut sebagai penanda: ▲ positif, ▼ negatif, • netral.
    tanda = {sentimen.POSITIF: "▲", sentimen.NEGATIF: "▼"}
    utama = "".join(
        f"\n{tanda.get(p.sentimen, '•')} {p.judul}"
        for p in bagian.get("utama", [])
    )
    notifikasi.kirim_rangkuman(
        f"Ringkas Pagi {tanggal:%d/%m}\n{dipilih} peristiwa ({rincian})\n"
        f"dari {total} artikel semalam.{utama}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
