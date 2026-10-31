"""Selector aleatorio de equipos de cazadores.

Funcion pura que genera un equipo aleatorio sin repetir a partir de un
catalogo de cazadores, un tamano solicitado y un generador de numeros
aleatorios (random.Random).
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grimcoven_equipos.catalogo import Cazador


def generar_equipo_aleatorio(
    cazadores: list[Cazador],
    tamano: int,
    rng: random.Random,
) -> list[Cazador]:
    """Selecciona *tamano* cazadores distintos al azar.

    Lanza ``ValueError`` si no hay suficientes cazadores para el tamano
    solicitado.
    """
    if tamano > len(cazadores):
        raise ValueError(f"No hay suficientes cazadores para un equipo de {tamano}")
    return rng.sample(cazadores, tamano)
