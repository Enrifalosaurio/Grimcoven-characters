"""Router de paginas HTML de Grimcoven Equipos.

Sirve las vistas renderizadas con plantillas Jinja2. Las plantillas se
encuentran en ``src/grimcoven_equipos/templates/``.

Rutas:
- GET / — pagina de inicio
- GET /aleatorio — selector aleatorio de equipos
- GET /recomendador — recomendador de equipos contra un Griefbound
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from grimcoven_equipos.api.dependencias import obtener_catalogo
from grimcoven_equipos.catalogo import Catalogo, Cazador, Griefbound
from grimcoven_equipos.equipos.aleatorio import generar_equipo_aleatorio
from grimcoven_equipos.equipos.recomendador import recomendar_equipos

logger = logging.getLogger(__name__)

router = APIRouter()

_TAMANO_MIN = 2
_TAMANO_MAX = 5
_ERROR_TAMANO = "El equipo debe tener entre 2 y 5 cazadores."

_AVISO_INFERIDOS = (
    "Recomendación basada en datos inferidos del reglamento; "
    "valídala con el Hunt Book."
)

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _tamano_valido(tamano: int) -> bool:
    """Indica si ``tamano`` esta en el rango permitido de cazadores."""
    return _TAMANO_MIN <= tamano <= _TAMANO_MAX


@router.get("/", response_class=HTMLResponse)
def inicio(request: Request) -> HTMLResponse:
    """Pagina de inicio con enlaces a /aleatorio y /recomendador."""
    return templates.TemplateResponse(request, "inicio.html")


@router.get("/aleatorio", response_class=HTMLResponse)
def aleatorio(
    request: Request,
    tamano: int | None = Query(None, description="Numero de cazadores (2-5)"),  # noqa: B008
    semilla: int | None = Query(None, description="Semilla para reproducibilidad"),  # noqa: B008
    catalogo: Catalogo = Depends(obtener_catalogo),  # noqa: B008
) -> HTMLResponse:
    """Pagina del selector aleatorio de equipos.

    Muestra un formulario para elegir el tamano del equipo. Si se proporciona
    ``tamano``, genera el equipo y lo muestra como cartas de cazador.
    """
    cazadores: list[Cazador] = []
    error: str | None = None

    if tamano is not None:
        if not _tamano_valido(tamano):
            error = _ERROR_TAMANO
        else:
            rng = random.Random(semilla)
            try:
                cazadores = generar_equipo_aleatorio(
                    list(catalogo.cazadores), tamano, rng
                )
            except ValueError as exc:
                logger.warning("Error generando equipo: %s", exc)
                error = "No hay suficientes cazadores en el catalogo para ese tamano de equipo."

    return templates.TemplateResponse(
        request,
        "aleatorio.html",
        {
            "tamano": tamano,
            "semilla": semilla,
            "cazadores": cazadores,
            "error": error,
        },
    )


@router.get("/recomendador", response_class=HTMLResponse)
def recomendador(
    request: Request,
    griefbound: str | None = Query(None),  # noqa: B008
    tamano: str | None = Query(None),  # noqa: B008
    catalogo: Catalogo = Depends(obtener_catalogo),  # noqa: B008
) -> HTMLResponse:
    """Pagina del recomendador de equipos contra un Griefbound.

    Muestra un formulario para elegir griefbound y tamano del equipo, y si se
    proporcionan parametros validos, renderiza los 3 mejores equipos.
    ``tamano`` se recibe como texto para mostrar un error en la pagina (y no
    un 422) cuando no es numerico.
    """
    # Separar griefbound por tipo para los optgroups del select
    griefbound_lista: list[Griefbound] = []
    pretendientes_lista: list[Griefbound] = []
    for g in catalogo.griefbound:
        if g.tipo == "griefbound":
            griefbound_lista.append(g)
        elif g.tipo == "pretender":
            pretendientes_lista.append(g)

    contexto: dict[str, object] = {
        "griefbound_lista": griefbound_lista,
        "pretendientes_lista": pretendientes_lista,
        "equipos": [],
        "error": None,
        "griefbound_id": griefbound,
        "tamano_valor": tamano,
    }

    # Si no hay parametros, solo mostrar el formulario
    if griefbound is None or tamano is None:
        return templates.TemplateResponse(request, "recomendador.html", contexto)

    # Validar tamano: numerico y dentro de rango
    tamano_int: int | None
    try:
        tamano_int = int(tamano)
    except ValueError:
        tamano_int = None
    if tamano_int is None or not _tamano_valido(tamano_int):
        contexto["error"] = _ERROR_TAMANO
        return templates.TemplateResponse(request, "recomendador.html", contexto)

    # Buscar el griefbound
    gb = catalogo.griefbound_por_id(griefbound)
    if gb is None:
        contexto["error"] = f"Griefbound no encontrado: {griefbound}"
        return templates.TemplateResponse(
            request, "recomendador.html", contexto, status_code=404
        )

    # Obtener recomendaciones
    try:
        resultado = recomendar_equipos(
            gb,
            list(catalogo.cazadores),
            tamano=tamano_int,
        )
    except ValueError as exc:
        contexto["error"] = str(exc)
        return templates.TemplateResponse(request, "recomendador.html", contexto)

    # Enriquecer los equipos con los nombres de los cazadores
    equipos_enriquecidos = []
    for equipo in resultado:
        cazadores_info = []
        for cid in cast(list[str], equipo["cazadores"]):
            cazador = catalogo.cazador(cid)
            nombre = cazador.nombre if cazador else cid
            cazadores_info.append({"id": cid, "nombre": nombre})
        desglose = cast(dict[str, list[str]], equipo["desglose"])
        equipos_enriquecidos.append({
            "cazadores": cazadores_info,
            "puntuacion": equipo["puntuacion"],
            "amenazas_cubiertas": desglose["amenazas_cubiertas"],
            "roles_cubiertos": desglose["roles_cubiertos"],
        })

    contexto["equipos"] = equipos_enriquecidos
    contexto["aviso"] = _AVISO_INFERIDOS
    return templates.TemplateResponse(request, "recomendador.html", contexto)
