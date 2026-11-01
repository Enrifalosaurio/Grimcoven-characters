"""Dependencias comunes de FastAPI para los routers de la API."""

from __future__ import annotations

from fastapi import Request

from grimcoven_equipos.catalogo import Catalogo


def obtener_catalogo(request: Request) -> Catalogo:
    """Devuelve el catálogo compartido de la app (``request.app.state.catalogo``).

    ``create_app`` lo carga una sola vez (o recibe uno inyectado) y lo guarda en
    ``app.state``; los routers lo declaran con ``Depends(obtener_catalogo)``.
    """
    return request.app.state.catalogo
