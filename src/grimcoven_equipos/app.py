"""Aplicacion FastAPI de Grimcoven Equipos.

Carga el catalogo de cazadores y Griefbound una sola vez al crear la app (o usa el
inyectado), lo guarda en ``app.state.catalogo`` y expone los endpoints bajo /api.
"""

from __future__ import annotations

from fastapi import FastAPI

from grimcoven_equipos.api.catalogo import router as catalogo_router
from grimcoven_equipos.api.equipos import router as equipos_router
from grimcoven_equipos.catalogo import Catalogo, cargar_cazadores, cargar_griefbound


def create_app(catalogo: Catalogo | None = None) -> FastAPI:
    """Crea y configura la aplicacion FastAPI.

    Si no se inyecta ``catalogo``, se carga desde los ficheros de ``data/``; un
    ``ValueError`` de carga se propaga (la app no arranca con datos invalidos).
    """
    if catalogo is None:
        catalogo = Catalogo(
            cazadores=tuple(cargar_cazadores()),
            griefbound=tuple(cargar_griefbound()),
        )

    application = FastAPI(title="Grimcoven Equipos")
    application.state.catalogo = catalogo

    # Montar todos los routers bajo /api
    application.include_router(catalogo_router, prefix="/api")
    application.include_router(equipos_router, prefix="/api")

    return application


app = create_app()
