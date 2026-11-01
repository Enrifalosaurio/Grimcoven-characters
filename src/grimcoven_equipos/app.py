"""Aplicacion FastAPI de Grimcoven Equipos.

Carga el catalogo de cazadores y Griefbound una sola vez al crear la app (o usa el
inyectado), lo guarda en ``app.state.catalogo`` y expone los endpoints bajo /api.
Sirve las paginas HTML y los ficheros estaticos (CSS).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from grimcoven_equipos.api.catalogo import router as catalogo_router
from grimcoven_equipos.api.equipos import router as equipos_router
from grimcoven_equipos.catalogo import Catalogo, cargar_cazadores, cargar_griefbound
from grimcoven_equipos.paginas import router as paginas_router

_STATIC_DIR = Path(__file__).resolve().parent / "static"


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

    # Ficheros estaticos (CSS, fuentes, etc.)
    application.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # Routers de la API bajo /api
    application.include_router(catalogo_router, prefix="/api")
    application.include_router(equipos_router, prefix="/api")

    # Router de paginas HTML (raiz)
    application.include_router(paginas_router)

    return application


app = create_app()
