"""Respaldo entre proveedores de LLM: si uno no responde, la misma petición pasa al siguiente.

Se configura con `LLM_RESPALDO` (por ejemplo `gemini,ollama`). El orden es el de preferencia: el
primero es `LLM_PROVIDER`.

- Si un proveedor responde con su límite de uso, se aparta durante el tiempo que pide
  (`retry-after`) y la petición pasa al siguiente. Mientras está apartado no se le vuelve a
  llamar, así que una cuota diaria agotada no cuesta una petición fallida en cada sección.
- Un fallo de red, de servidor o de clave aparta al proveedor un minuto y pasa al siguiente.
- Si la respuesta no cumple el esquema tras los reintentos, no se cambia de proveedor: es un
  problema del prompt o del modelo, no de disponibilidad.
- Si todos están apartados por límite, se lanza `ErrorLimiteLLM` con la espera más corta, y quien
  llama decide si espera (la clasificación espera si es razonable) o se detiene.

Mezclar modelos en un mismo documento cambia los resultados. Por eso cada respuesta queda
contada por proveedor (`respuestas_por_proveedor`), y la evaluación de la tesis debe ejecutarse
con un único proveedor y sin respaldo.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from orchestrator.llm.base import (
    ErrorLimiteLLM,
    ErrorProveedorLLM,
    Nivel,
    ProveedorLLM,
    T,
)

# Cuánto se aparta un proveedor cuando no dice cuánto esperar.
PAUSA_LIMITE_S = 30.0
PAUSA_LIMITE_DIARIO_S = 15 * 60.0
PAUSA_ERROR_S = 60.0

AlCambiar = Callable[[str, str, str], None]


@dataclass
class _Apartado:
    hasta: float = 0.0
    por_limite: bool = False
    diario: bool = False


class ProveedorEnCadena:
    def __init__(
        self,
        proveedores: Sequence[ProveedorLLM],
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        if not proveedores:
            raise ValueError("La cadena necesita al menos un proveedor")
        self.proveedores = list(proveedores)
        self.nombres = [getattr(p, "nombre", type(p).__name__) for p in self.proveedores]
        self.nombre = self.nombres[0]
        self.respuestas_por_proveedor: Counter[str] = Counter()
        # Se avisa al pasar de un proveedor al siguiente: (de, a, motivo).
        self.al_cambiar: AlCambiar | None = None
        self._reloj = reloj
        self._apartados = [_Apartado() for _ in self.proveedores]

    def generar_estructurado(
        self,
        prompt: str,
        esquema: type[T],
        nivel: Nivel = "rapido",
        sistema: str | None = None,
    ) -> T:
        disponibles = [i for i, a in enumerate(self._apartados) if a.hasta <= self._reloj()]
        if not disponibles:
            raise self._ninguno_disponible()

        anterior: tuple[str, str] | None = None  # (nombre, motivo) del que acaba de fallar
        for indice in disponibles:
            nombre = self.nombres[indice]
            if anterior is not None and self.al_cambiar is not None:
                self.al_cambiar(anterior[0], nombre, anterior[1])
            try:
                respuesta = self.proveedores[indice].generar_estructurado(
                    prompt, esquema, nivel, sistema
                )
            except ErrorLimiteLLM as error:
                pausa = error.espera_s
                if pausa is None:
                    pausa = PAUSA_LIMITE_DIARIO_S if error.diario else PAUSA_LIMITE_S
                self._apartados[indice] = _Apartado(self._reloj() + pausa, True, error.diario)
                anterior = (nombre, str(error))
                continue
            except ErrorProveedorLLM as error:
                self._apartados[indice] = _Apartado(self._reloj() + PAUSA_ERROR_S)
                anterior = (nombre, str(error))
                continue
            self.respuestas_por_proveedor[nombre] += 1
            return respuesta

        raise self._ninguno_disponible()

    def _ninguno_disponible(self) -> ErrorProveedorLLM:
        ahora = self._reloj()
        espera = max(min(a.hasta for a in self._apartados) - ahora, 0.0)
        nombres = ", ".join(self.nombres)
        if all(a.por_limite for a in self._apartados):
            return ErrorLimiteLLM(
                f"todos los proveedores ({nombres}) alcanzaron su límite de uso",
                espera_s=espera,
                diario=all(a.diario for a in self._apartados),
            )
        return ErrorProveedorLLM(f"ningún proveedor de LLM disponible ({nombres})")
