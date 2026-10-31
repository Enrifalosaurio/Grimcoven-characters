"""Aplicacion FastAPI de Grimcoven Equipos.

Carga el catalogo de cazadores y Griefbound una sola vez al arrancar
y expone los endpoints bajo /api.
"""

from fastapi import FastAPI

from grimcoven_equipos.api.catalogo import init_catalogo
from grimcoven_equipos.api.catalogo import router as catalogo_router
from grimcoven_equipos.api.equipos import router as equipos_router
from grimcoven_equipos.catalogo import cargar_cazadores, cargar_griefbound


def create_app() -> FastAPI:
    """Crea y configura la aplicacion FastAPI con el catalogo cargado."""
    application = FastAPI(title="Grimcoven Equipos")

    # Cargar datos una sola vez
    cazadores = cargar_cazadores()
    griefbound = cargar_griefbound()
    init_catalogo(cazadores, griefbound)

    # Montar todos los routers bajo /api
    application.include_router(catalogo_router, prefix="/api")
    application.include_router(equipos_router, prefix="/api")

    return application


app = create_app()
