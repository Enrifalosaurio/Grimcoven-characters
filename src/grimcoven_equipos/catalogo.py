"""Catálogo de cazadores y Griefbound de Grimcoven.

Los datos viven en ``data/cazadores.json`` y ``data/griefbound.json`` (una lista de objetos
en la raíz). Este módulo los valida con modelos pydantic y lanza ``ValueError`` ante
cualquier dato inválido.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, model_validator

DIRECTORIO_DATOS = Path(__file__).resolve().parents[2] / "data"
RUTA_CAZADORES = DIRECTORIO_DATOS / "cazadores.json"
RUTA_GRIEFBOUND = DIRECTORIO_DATOS / "griefbound.json"

Rol = Literal["tanque", "dano", "apoyo", "control"]


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Fuente(_Modelo):
    """Referencia al reglamento: fichero de ``Resources/`` y página impresa."""

    fichero: str = Field(min_length=1)
    pagina: StrictInt = Field(ge=1)


class Cazador(_Modelo):
    id: str = Field(min_length=1)
    nombre: str = Field(min_length=1)
    expansion: Literal["base", "hunters"]
    complejidad: str = Field(min_length=1)
    roles: list[Rol] = Field(min_length=1)
    contrarresta: list[str]
    vida: StrictInt | None
    movimiento: StrictInt | None
    fuente: Fuente


class Griefbound(_Modelo):
    id: str = Field(min_length=1)
    nombre: str = Field(min_length=1)
    tipo: Literal["griefbound", "pretender"]
    expansion: Literal["base", "hunters", "forgotten-entities"]
    amenazas: list[str]
    fuente: Fuente
    cazador_origen: str | None = None

    @model_validator(mode="after")
    def _validar_pretender(self) -> Griefbound:
        if self.tipo == "pretender":
            if not self.cazador_origen:
                raise ValueError("un pretender necesita 'cazador_origen'")
            if self.id != f"pretender-{self.cazador_origen}":
                raise ValueError(
                    f"el id de un pretender debe ser 'pretender-{self.cazador_origen}'"
                )
        elif self.cazador_origen is not None:
            raise ValueError("solo los pretender pueden tener 'cazador_origen'")
        return self


_M = TypeVar("_M", bound=_Modelo)


def _leer_lista(ruta: Path) -> list[Any]:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{ruta}: JSON inválido: {error}") from error
    if not isinstance(datos, list):
        raise ValueError(f"{ruta}: la raíz del JSON debe ser una lista de objetos")
    return datos


def _validar_entradas(ruta: Path, modelo: type[_M], tipo: str) -> list[_M]:
    """Valida cada entrada con ``modelo`` y comprueba que los ids no se repiten."""
    resultado: list[_M] = []
    vistos: set[str] = set()
    for posicion, entrada in enumerate(_leer_lista(ruta)):
        id_ = entrada.get("id") if isinstance(entrada, dict) else None
        etiqueta = repr(id_) if id_ is not None else f"en la posición {posicion}"
        try:
            item = modelo.model_validate(entrada)
        except ValidationError as error:
            raise ValueError(f"{ruta}: {tipo} {etiqueta} inválido: {error}") from error
        if item.id in vistos:
            raise ValueError(f"{ruta}: id duplicado {item.id!r}")
        vistos.add(item.id)
        resultado.append(item)
    return resultado


def cargar_cazadores(ruta: Path | str | None = None) -> list[Cazador]:
    """Carga y valida los cazadores desde ``ruta`` (por defecto ``data/cazadores.json``)."""
    return _validar_entradas(Path(ruta) if ruta else RUTA_CAZADORES, Cazador, "cazador")


def cargar_griefbound(
    ruta: Path | str | None = None,
    ruta_cazadores: Path | str | None = None,
) -> list[Griefbound]:
    """Carga y valida los Griefbound desde ``ruta`` (por defecto ``data/griefbound.json``).

    Los ``cazador_origen`` de los pretenders se comprueban contra los cazadores de
    ``ruta_cazadores`` (por defecto ``data/cazadores.json``).
    """
    ruta_g = Path(ruta) if ruta else RUTA_GRIEFBOUND
    griefbound = _validar_entradas(ruta_g, Griefbound, "griefbound")
    origenes = {g.cazador_origen for g in griefbound if g.cazador_origen is not None}
    if origenes:
        ids_cazadores = {c.id for c in cargar_cazadores(ruta_cazadores)}
        for g in griefbound:
            if g.cazador_origen is not None and g.cazador_origen not in ids_cazadores:
                raise ValueError(
                    f"{ruta_g}: el pretender {g.id!r} tiene un cazador_origen "
                    f"desconocido: {g.cazador_origen!r}"
                )
    return griefbound
