"""Router de paginas HTML de Grimcoven Equipos.

Sirve las vistas renderizadas con plantillas Jinja2. Las plantillas se
encuentran en ``src/grimcoven_equipos/templates/``.

Rutas:
- GET / — pagina de inicio
- GET /aleatorio — selector aleatorio de equipos
"""

from __future__ import annotations

import logging
import random
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from grimcoven_equipos.api.dependencias import obtener_catalogo
from grimcoven_equipos.catalogo import Catalogo, Cazador
from grimcoven_equipos.equipos.aleatorio import generar_equipo_aleatorio

logger = logging.getLogger(__name__)

router = APIRouter()

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


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
        if tamano < 2 or tamano > 5:
            error = "El equipo debe tener entre 2 y 5 cazadores."
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
