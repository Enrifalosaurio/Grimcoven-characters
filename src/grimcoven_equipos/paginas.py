"""Router de paginas HTML de Grimcoven Equipos.

Sirve las vistas renderizadas con plantillas Jinja2. Las plantillas se
encuentran en ``src/grimcoven_equipos/templates/``.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
def inicio(request: Request) -> HTMLResponse:
    """Pagina de inicio con enlaces a /aleatorio y /recomendador."""
    return templates.TemplateResponse(request, "inicio.html")
