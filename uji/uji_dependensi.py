"""
Tiap paket pihak ketiga yang diimpor harus tercatat di `pyproject.toml`.

Uji ini lahir dari bug nyata: `duckdb` dipasang manual ke venv lokal tapi tidak
pernah ditulis di `pyproject.toml`. Semuanya jalan di mesin sendiri, lalu job
GitHub Actions pertama mati dengan `ModuleNotFoundError`. Kelas kesalahan ini
tidak terlihat oleh uji fungsional mana pun — venv lokal selalu lebih kaya
daripada environment bersih.
"""

import ast
import sys
import tomllib
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
PAKET_LOKAL = {"inti", "alur", "sumber", "uji"}


def _diimpor() -> set[str]:
    nama: set[str] = set()
    for berkas in AKAR.rglob("*.py"):
        if ".venv" in berkas.parts:
            continue
        pohon = ast.parse(berkas.read_text(encoding="utf-8"))
        for simpul in ast.walk(pohon):
            if isinstance(simpul, ast.Import):
                nama |= {a.name.split(".")[0] for a in simpul.names}
            elif isinstance(simpul, ast.ImportFrom) and simpul.level == 0 and simpul.module:
                nama.add(simpul.module.split(".")[0])
    return nama - set(sys.stdlib_module_names) - PAKET_LOKAL


def _tercatat() -> set[str]:
    proyek = tomllib.loads((AKAR / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    semua = list(proyek["dependencies"])
    for tambahan in proyek.get("optional-dependencies", {}).values():
        semua += tambahan
    return {d.split("==")[0].split(">")[0].split("[")[0].strip().lower() for d in semua}


def uji_semua_impor_tercatat_di_pyproject():
    hilang = {p.lower() for p in _diimpor()} - _tercatat()
    assert not hilang, f"dipakai tapi tidak tercatat di pyproject.toml: {sorted(hilang)}"


def uji_semua_versi_dipin():
    """§3 — dependensi '>=' membuat 'jalan di lokal, rusak di CI' tidak bisa
    dibedakan dari perubahan perilaku sumber."""
    proyek = tomllib.loads((AKAR / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    semua = list(proyek["dependencies"])
    for tambahan in proyek.get("optional-dependencies", {}).values():
        semua += tambahan
    tanpa_pin = [d for d in semua if "==" not in d]
    assert not tanpa_pin, f"versi belum di-pin: {tanpa_pin}"
