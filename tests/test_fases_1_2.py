"""Resumen de la ejecución de las fases 1 y 2 con el dataset (evaluation/fases_1_2.py)."""

from evaluation.fases_1_2 import informe

FASE1 = {
    "encontrados": 29,
    "referencia": 30,
    "exhaustividad": 0.967,
    "falsos_positivos": 1,
    "tipo_correcto": 26,
    "acierto_tipo": 0.897,
    "etiquetas_precision": 0.84,
    "etiquetas_exhaustividad": 0.66,
    "etiquetas_f1": 0.739,
    "no_encontrados": ["RF-02"],
    "tipo_incorrecto": ["RF-14: no_funcional (esperado funcional)"],
    "falsos_positivos_texto": [],
}
FASE2 = {
    "servicios_propuestos": ["usuarios", "pedidos", "auditoria"],
    "servicios_referencia": ["usuarios", "pedidos"],
    "nombres_coincidentes": ["pedidos", "usuarios"],
    "pares_precision": 1.0,
    "pares_exhaustividad": 0.94,
    "pares_f1": 0.969,
    "correspondencia": {"pedidos": "pedidos", "usuarios": "usuarios"},
}


def _resumen(**cambios):
    return {
        "documento": "01_tienda_en_linea",
        "titulo": "Tienda en línea",
        "pasos": {"clasificar": {"correcto": True, "segundos": 12.5}},
        "fase1": FASE1,
        "ciclo": {
            "aprobada": True,
            "intentos": 2,
            "rechazos": ["Los servicios pagos, pedidos comparten la base de datos pedidos_db"],
            "patrones": ["api_gateway", "saga"],
            "patrones_referencia": ["api_gateway", "circuit_breaker", "saga"],
            "avisos": ["arquitectura.cadena_sincrona"] * 3 + ["arquitectura.ciclo_de_eventos"],
        },
        "fase2": FASE2,
        "adr": 9,
    } | cambios


def test_el_informe_resume_las_dos_fases():
    texto = informe([_resumen()], "docx")
    assert "--formato docx" in texto
    assert "| 01_tienda_en_linea | 29/30 (97%) | 1 | 26/29 (90%) | 84% / 66% / 0.74 |" in texto
    assert (
        "| 01_tienda_en_linea | aprobada en el intento 2 | 3 / 2 | 2 | 100% / 94% / 0.97 | "
        "2/3 (falta circuit_breaker) | 9 |"
    ) in texto
    assert "- Avisos de OPA: arquitectura.cadena_sincrona ×3, arquitectura.ciclo_de_eventos." in (
        texto
    )
    assert "- Patrones inferidos: api_gateway, saga." in texto
    assert "- Requisitos no encontrados: RF-02." in texto
    assert "- Rechazos de OPA: Los servicios pagos, pedidos comparten" in texto
    assert "- Correspondencia con la referencia: pedidos -> pedidos, usuarios -> usuarios." in texto


def test_el_informe_muestra_los_documentos_que_fallaron():
    sin_clasificar = _resumen(
        documento="02_gestion_academica",
        pasos={"clasificar": {"correcto": False, "segundos": 3.0}},
        fase1=None,
        ciclo=None,
        fase2=None,
    )
    rechazada = _resumen(
        documento="03_citas_medicas",
        ciclo=_resumen()["ciclo"] | {"aprobada": False, "intentos": 3},
        fase2=None,
    )
    texto = informe([sin_clasificar, rechazada], "pdf")
    assert "| 02_gestion_academica | no se pudo clasificar | | | |" in texto
    assert "| 03_citas_medicas | rechazada en 3 intentos | | | | | |" in texto
    assert "clasificar 3.0 s (ERROR)" in texto
