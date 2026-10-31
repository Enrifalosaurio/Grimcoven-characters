"""Fabrica de la aplicacion FastAPI de Grimcoven."""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Crea y configura la app FastAPI."""
    from grimcoven_equipos.api.equipos import router as equipos_router

    app = FastAPI(title="Grimcoven Equipos")
    app.include_router(equipos_router)
    return app
