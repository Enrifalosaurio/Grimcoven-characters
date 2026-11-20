"""Tests e2e de US-015: Pagina del creador de equipos en Chromium.

CA9: con viewport de 800px el boton 'Forjar un aquelarre' no es visible.

Siguen el patron GRIMCOVEN_REQUIRE_E2E: sin Playwright o Chromium se saltan;
con GRIMCOVEN_REQUIRE_E2E=1 fallan.
"""

from __future__ import annotations

from typing import Any

import pytest

# ===========================================================================
# CA9: boton 'Forjar un aquelarre' no visible a 800px
# ===========================================================================


@pytest.mark.e2e
def test_ca9_boton_forjar_no_visible_800px(servidor_e2e: str, navegador_e2e: Any) -> None:
    """CA9 (e2e): con un viewport de 800px, el boton 'Forjar un aquelarre' no es visible."""
    contexto = navegador_e2e.new_context(viewport={"width": 800, "height": 600})
    pagina = contexto.new_page()
    try:
        pagina.goto(f"{servidor_e2e.rstrip('/')}/creador", wait_until="networkidle")
        # Buscar el boton/enlace 'Forjar un aquelarre'
        boton = pagina.locator("text='Forjar un aquelarre'")
        assert boton.count() > 0, "No se encontro el boton 'Forjar un aquelarre'"
        assert not boton.first.is_visible(), (
            "El boton 'Forjar un aquelarre' deberia estar oculto a 800px"
        )
    finally:
        contexto.close()
