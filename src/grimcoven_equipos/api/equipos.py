"""Endpoints de equipos de cazadores.

Rutas:
- GET /api/equipos/aleatorio?tamano=N[&semilla=S]
- GET /api/equipos/recomendados?griefbound=ID&tamano=N
"""

from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from grimcoven_equipos.api.dependencias import obtener_catalogo
from grimcoven_equipos.catalogo import Catalogo
from grimcoven_equipos.equipos.aleatorio import generar_equipo_aleatorio
from grimcoven_equipos.equipos.recomendador import recomendar_equipos

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


# ---------------------------------------------------------------------------
# Recomendador de equipos contra un Griefbound
# ---------------------------------------------------------------------------


class DesgloseEquipo(BaseModel):
    """Desglose de la puntuacion de un equipo recomendado."""

    amenazas_cubiertas: list[str]
    roles_cubiertos: list[str]


class EquipoRecomendado(BaseModel):
    """Un equipo recomendado con su puntuacion y desglose."""

    cazadores: list[str]
    puntuacion: int
    desglose: DesgloseEquipo


class RecomendacionResponse(BaseModel):
    """Esquema de respuesta de GET /equipos/recomendados."""

    griefbound: str
    tamano: int
    equipos: list[EquipoRecomendado]


@router.get("/recomendados", response_model=RecomendacionResponse)
def equipos_recomendados(
    griefbound: str = Query(..., max_length=100, description="Id del Griefbound a enfrentar"),  # noqa: B008
    tamano: int = Query(..., ge=2, le=5, description="Numero de cazadores (2-5)"),  # noqa: B008
    catalogo: Catalogo = Depends(obtener_catalogo),  # noqa: B008
) -> RecomendacionResponse:
    """Recomienda los 3 mejores equipos de cazadores contra un Griefbound.

    Evalua todas las combinaciones de ``tamano`` cazadores y devuelve los 3
    equipos con mayor puntuacion. Si el Griefbound es un pretender, excluye
    al cazador de origen.
    """
    gb = catalogo.griefbound_por_id(griefbound)
    if gb is None:
        raise HTTPException(
            status_code=404,
            detail=f"Griefbound no encontrado: {griefbound}",
        )

    try:
        resultado = recomendar_equipos(
            gb,
            list(catalogo.cazadores),
            tamano=tamano,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return RecomendacionResponse(
        griefbound=griefbound,
        tamano=tamano,
        equipos=[
            EquipoRecomendado(
                cazadores=e["cazadores"],
                puntuacion=e["puntuacion"],
                desglose=DesgloseEquipo(
                    amenazas_cubiertas=e["desglose"]["amenazas_cubiertas"],
                    roles_cubiertos=e["desglose"]["roles_cubiertos"],
                ),
            )
            for e in resultado
        ],
    )
