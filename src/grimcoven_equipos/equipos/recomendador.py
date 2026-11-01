"""Recomendador de equipos de cazadores contra un Griefbound.

Logica pura: evalua todas las combinaciones de cazadores con
itertools.combinations y devuelve los mejores equipos.
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grimcoven_equipos.catalogo import Cazador, Griefbound


# Constantes de puntuacion
PESO_AMENAZA = 10
PESO_ROL = 5
ROLES_ESENCIALES = frozenset({"tanque", "dano", "apoyo"})


def _evaluar_equipo(
    equipo: tuple[Cazador, ...],
    amenazas_gb: set[str],
) -> dict[str, object]:
    """Evalua un equipo contra las amenazas de un Griefbound.

    Devuelve un dict con cazadores (ids ordenados), puntuacion y desglose.
    """
    # Amenazas cubiertas: amenazas del griefbound que algun miembro contrarresta
    contrarresta_equipo: set[str] = set()
    for cazador in equipo:
        contrarresta_equipo.update(cazador.contrarresta)
    amenazas_cubiertas = sorted(amenazas_gb & contrarresta_equipo)

    # Roles esenciales cubiertos (tanque, dano, apoyo; control no puntua)
    roles_equipo: set[str] = set()
    for cazador in equipo:
        roles_equipo.update(cazador.roles)
    roles_cubiertos = sorted(roles_equipo & ROLES_ESENCIALES)

    puntuacion = PESO_AMENAZA * len(amenazas_cubiertas) + PESO_ROL * len(roles_cubiertos)

    ids_ordenados = sorted(c.id for c in equipo)

    return {
        "cazadores": ids_ordenados,
        "puntuacion": puntuacion,
        "desglose": {
            "amenazas_cubiertas": amenazas_cubiertas,
            "roles_cubiertos": roles_cubiertos,
        },
    }


def recomendar_equipos(
    griefbound: Griefbound,
    cazadores: list[Cazador],
    tamano: int,
    top: int = 3,
) -> list[dict[str, object]]:
    """Recomienda los mejores equipos contra un Griefbound.

    Genera todas las combinaciones de ``tamano`` cazadores y las ordena por
    puntuacion descendente; en caso de empate, por orden lexicografico de los
    ids ordenados alfabeticamente. Devuelve los ``top`` mejores.

    Si el Griefbound es un pretender con ``cazador_origen``, se excluye ese
    cazador de las combinaciones (regla R p31).
    """
    # Excluir cazador_origen si es un pretender
    if griefbound.cazador_origen is not None:
        cazadores = [c for c in cazadores if c.id != griefbound.cazador_origen]

    if len(cazadores) < tamano:
        raise ValueError(
            f"No hay suficientes cazadores disponibles ({len(cazadores)}) "
            f"para formar equipos de tamano {tamano}"
        )

    amenazas_gb = set(griefbound.amenazas)

    evaluados = [
        _evaluar_equipo(combo, amenazas_gb)
        for combo in itertools.combinations(cazadores, tamano)
    ]

    # Ordenar: por puntuacion desc, luego por ids lexicografico asc
    evaluados.sort(key=lambda e: (-e["puntuacion"], e["cazadores"]))

    return evaluados[:top]
