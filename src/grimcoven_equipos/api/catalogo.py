"""Router de consulta del catalogo de cazadores y Griefbound.

Los endpoints obtienen el catalogo de la app con ``Depends(obtener_catalogo)``; este
modulo no guarda estado propio.
"""

from __future__ import annotations

from enum import StrEnum

from fastapi import APIRouter, Depends, HTTPException, Query

from grimcoven_equipos.api.dependencias import obtener_catalogo
from grimcoven_equipos.catalogo import Catalogo

router = APIRouter()


class TipoGriefbound(StrEnum):
    """Valores validos para el filtro de tipo de griefbound."""

    griefbound = "griefbound"
    pretender = "pretender"


# ----- Endpoints de cazadores -----


@router.get("/cazadores")
def listar_cazadores(
    catalogo: Catalogo = Depends(obtener_catalogo),  # noqa: B008
) -> list[dict]:
    """Devuelve la lista de cazadores ordenada por id."""
    return [c.model_dump() for c in catalogo.cazadores_ordenados()]


@router.get("/cazadores/{cazador_id}")
def obtener_cazador(
    cazador_id: str,
    catalogo: Catalogo = Depends(obtener_catalogo),  # noqa: B008
) -> dict:
    """Devuelve un cazador por su id o 404."""
    cazador = catalogo.cazador(cazador_id)
    if cazador is None:
        raise HTTPException(status_code=404, detail=f"Cazador no encontrado: {cazador_id}")
    return cazador.model_dump()


# ----- Endpoints de griefbound -----


@router.get("/griefbound")
def listar_griefbound(
    tipo: TipoGriefbound | None = Query(default=None),  # noqa: B008
    catalogo: Catalogo = Depends(obtener_catalogo),  # noqa: B008
) -> list[dict]:
    """Devuelve la lista de griefbound, opcionalmente filtrada por tipo."""
    return [
        g.model_dump()
        for g in catalogo.griefbound
        if tipo is None or g.tipo == tipo.value
    ]


@router.get("/griefbound/{griefbound_id}")
def obtener_griefbound(
    griefbound_id: str,
    catalogo: Catalogo = Depends(obtener_catalogo),  # noqa: B008
) -> dict:
    """Devuelve un griefbound por su id o 404."""
    griefbound = catalogo.griefbound_por_id(griefbound_id)
    if griefbound is None:
        raise HTTPException(
            status_code=404, detail=f"Griefbound no encontrado: {griefbound_id}"
        )
    return griefbound.model_dump()
