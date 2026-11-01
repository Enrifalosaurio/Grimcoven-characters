"""Endpoint del selector aleatorio de equipos.

Ruta: GET /api/equipos/aleatorio?tamano=N[&semilla=S]
"""

from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from grimcoven_equipos.api.dependencias import obtener_catalogo
from grimcoven_equipos.catalogo import Catalogo
from grimcoven_equipos.equipos.aleatorio import generar_equipo_aleatorio

router = APIRouter(prefix="/equipos", tags=["equipos"])


class CazadorResumen(BaseModel):
    """Representacion resumida de un cazador en la respuesta."""

    id: str
    nombre: str
    roles: list[str]


class EquipoAleatorioResponse(BaseModel):
    """Esquema de respuesta de GET /equipos/aleatorio."""

    tamano: int
    semilla: int | None
    cazadores: list[CazadorResumen]


@router.get("/aleatorio", response_model=EquipoAleatorioResponse)
def equipo_aleatorio(
    tamano: int = Query(..., ge=2, le=5, description="Numero de cazadores (2-5)"),
    semilla: int | None = Query(None, description="Semilla para reproducibilidad"),
    catalogo: Catalogo = Depends(obtener_catalogo),  # noqa: B008
) -> EquipoAleatorioResponse:
    """Genera un equipo aleatorio de cazadores sin repetir.

    El selector recibe los cazadores en el orden del catalogo (el del fichero JSON),
    de modo que una misma semilla reproduce siempre el mismo equipo.
    """
    rng = random.Random(semilla)
    try:
        equipo = generar_equipo_aleatorio(list(catalogo.cazadores), tamano, rng)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return EquipoAleatorioResponse(
        tamano=tamano,
        semilla=semilla,
        cazadores=[
            CazadorResumen(id=c.id, nombre=c.nombre, roles=list(c.roles))
            for c in equipo
        ],
    )
