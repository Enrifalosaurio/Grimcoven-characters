"""Test de humo en navegador real (US-013, CA3)."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.mark.e2e
def test_ca3_portada_con_titulo_y_sin_errores_js(servidor_e2e: str, pagina_e2e: Any) -> None:
    """CA3: '/' tiene 'Grimcoven' en el titulo y no emite console.error ni pageerror."""
    errores: list[str] = []

    def anotar_consola(mensaje: Any) -> None:
        if mensaje.type == "error":
            errores.append(f"console.error: {mensaje.text}")

    # Los manejadores van antes de goto para no perder los errores de la carga inicial.
    pagina_e2e.on("console", anotar_consola)
    pagina_e2e.on("pageerror", lambda error: errores.append(f"pageerror: {error}"))

    pagina_e2e.goto(f"{servidor_e2e.rstrip('/')}/")

    assert "Grimcoven" in pagina_e2e.title()
    assert errores == []
