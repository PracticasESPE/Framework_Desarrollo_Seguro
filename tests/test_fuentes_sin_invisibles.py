"""El código del framework no contiene caracteres invisibles ni de control de dirección.

Un carácter de ancho cero o un control bidireccional puede hacer que el código se lea distinto de
como se ejecuta (técnica «Trojan Source», CVE-2021-42574). Donde hacen falta, como en
orchestrator/ingest/normalizacion.py, se escriben con su escape: \\u200b.
"""

import unicodedata
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
FUENTES = sorted(
    p for carpeta in ("orchestrator", "tests", "evaluation") for p in (RAIZ / carpeta).rglob("*.py")
)


@pytest.mark.parametrize("ruta", FUENTES, ids=lambda p: p.relative_to(RAIZ).as_posix())
def test_sin_caracteres_invisibles(ruta):
    for numero, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), start=1):
        for caracter in linea:
            categoria = unicodedata.category(caracter)
            invisible = categoria in ("Cf", "Co") or (categoria == "Zs" and caracter != " ")
            control = categoria == "Cc" and caracter != "\t"
            assert not (invisible or control), f"línea {numero}: U+{ord(caracter):04X}"
