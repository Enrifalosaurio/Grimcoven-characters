"""Router de consulta del catalogo de cazadores y Griefbound."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query

if TYPE_CHECKING:
    from grimcoven_equipos.catalogo import Cazador, Griefbound

router = APIRouter()

# Estos diccionarios se rellenan en create_app() via init_catalogo().
_cazadores_por_id: dict[str, Cazador] = {}
_cazadores_lista: list[dict] = []
_griefbound_por_id: dict[str, Griefbound] = {}
_griefbound_lista: list[dict] = []


class TipoGriefbound(StrEnum):
    """Valores validos para el filtro de tipo de griefbound."""

    griefbound = "griefbound"
    pretender = "pretender"


def init_catalogo(
    cazadores: list[Cazador],
    griefbound: list[Griefbound],
) -> None:
    """Inicializa los datos del catalogo (llamado una sola vez al arrancar).

    Si el catalogo ya contiene datos, no reinicializa (guarda contra
    multiples llamadas cuando el modulo se importa mas de una vez).
    """
    if _cazadores_por_id:
        return

    _cazadores_por_id.clear()
    _cazadores_lista.clear()
    _griefbound_por_id.clear()
    _griefbound_lista.clear()

    for c in sorted(cazadores, key=lambda x: x.id):
        _cazadores_por_id[c.id] = c
        _cazadores_lista.append(c.model_dump())

    for g in griefbound:
        _griefbound_por_id[g.id] = g
        _griefbound_lista.append(g.model_dump())


# ----- Endpoints de cazadores -----


@router.get("/cazadores")
def listar_cazadores() -> list[dict]:
    """Devuelve la lista de cazadores ordenada por id."""
    return _cazadores_lista


@router.get("/cazadores/{cazador_id}")
def obtener_cazador(cazador_id: str) -> dict:
    """Devuelve un cazador por su id o 404."""
    cazador = _cazadores_por_id.get(cazador_id)
    if cazador is None:
        raise HTTPException(status_code=404, detail=f"Cazador no encontrado: {cazador_id}")
    return cazador.model_dump()


# ----- Endpoints de griefbound -----


@router.get("/griefbound")
def listar_griefbound(
    tipo: TipoGriefbound | None = Query(default=None),  # noqa: B008
) -> list[dict]:
    """Devuelve la lista de griefbound, opcionalmente filtrada por tipo."""
    if tipo is None:
        return _griefbound_lista
    return [g for g in _griefbound_lista if g["tipo"] == tipo.value]


@router.get("/griefbound/{griefbound_id}")
def obtener_griefbound(griefbound_id: str) -> dict:
    """Devuelve un griefbound por su id o 404."""
    griefbound = _griefbound_por_id.get(griefbound_id)
    if griefbound is None:
        raise HTTPException(
            status_code=404, detail=f"Griefbound no encontrado: {griefbound_id}"
        )
    return griefbound.model_dump()
