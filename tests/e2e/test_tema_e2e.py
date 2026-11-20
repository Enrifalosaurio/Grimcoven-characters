"""Tests e2e de US-014: Tema visual en Chromium.

CA4: sin peticiones externas, body bg/color, font-family Spectral.
CA7: focus-visible con outline dorado.
CA8: viewport 360px sin overflow horizontal.

Siguen el patron GRIMCOVEN_REQUIRE_E2E: sin Playwright o Chromium se saltan;
con GRIMCOVEN_REQUIRE_E2E=1 fallan.
"""

from __future__ import annotations

from typing import Any

import pytest

# ===========================================================================
# CA4: sin peticiones externas, body bg/color, font-family
# ===========================================================================


@pytest.mark.e2e
def test_ca4_sin_peticiones_externas(servidor_e2e: str, pagina_e2e: Any) -> None:
    """CA4: al cargar '/' ninguna peticion va a un host distinto de 127.0.0.1."""
    from urllib.parse import urlsplit

    hosts_externos: list[str] = []

    def capturar_peticion(peticion: Any) -> None:
        host = urlsplit(peticion.url).hostname
        if host and host != "127.0.0.1":
            hosts_externos.append(peticion.url)

    pagina_e2e.on("request", capturar_peticion)
    pagina_e2e.goto(f"{servidor_e2e.rstrip('/')}/", wait_until="networkidle")

    assert hosts_externos == [], f"Peticiones a hosts externos: {hosts_externos}"


@pytest.mark.e2e
def test_ca4_body_background_color(servidor_e2e: str, pagina_e2e: Any) -> None:
    """CA4: body tiene background-color rgb(16, 15, 18) (#100F12 = --void)."""
    pagina_e2e.goto(f"{servidor_e2e.rstrip('/')}/", wait_until="networkidle")
    bg = pagina_e2e.evaluate("getComputedStyle(document.body).backgroundColor")
    assert bg == "rgb(16, 15, 18)", f"background-color inesperado: {bg}"


@pytest.mark.e2e
def test_ca4_body_color(servidor_e2e: str, pagina_e2e: Any) -> None:
    """CA4: body tiene color rgb(229, 223, 210) (#E5DFD2 = --ivory)."""
    pagina_e2e.goto(f"{servidor_e2e.rstrip('/')}/", wait_until="networkidle")
    color = pagina_e2e.evaluate("getComputedStyle(document.body).color")
    assert color == "rgb(229, 223, 210)", f"color inesperado: {color}"


@pytest.mark.e2e
def test_ca4_font_family_spectral(servidor_e2e: str, pagina_e2e: Any) -> None:
    """CA4: la font-family computada del body empieza por Spectral."""
    pagina_e2e.goto(f"{servidor_e2e.rstrip('/')}/", wait_until="networkidle")
    ff = pagina_e2e.evaluate("getComputedStyle(document.body).fontFamily")
    assert ff.lower().startswith("spectral"), (
        f"font-family no empieza por Spectral: {ff}"
    )


# ===========================================================================
# CA7: focus-visible outline
# ===========================================================================


@pytest.mark.e2e
def test_ca7_focus_visible_outline_style(servidor_e2e: str, pagina_e2e: Any) -> None:
    """CA7: al hacer Tab al primer enlace, tiene outline-style solid."""
    pagina_e2e.goto(f"{servidor_e2e.rstrip('/')}/", wait_until="networkidle")
    pagina_e2e.keyboard.press("Tab")
    estilo = pagina_e2e.evaluate("""
        (() => {
            const el = document.activeElement;
            return getComputedStyle(el).outlineStyle;
        })()
    """)
    assert estilo == "solid", f"outline-style inesperado: {estilo}"


@pytest.mark.e2e
def test_ca7_focus_visible_outline_color(servidor_e2e: str, pagina_e2e: Any) -> None:
    """CA7: al hacer Tab al primer enlace, tiene outline-color rgb(182, 154, 100) (--gold)."""
    pagina_e2e.goto(f"{servidor_e2e.rstrip('/')}/", wait_until="networkidle")
    pagina_e2e.keyboard.press("Tab")
    color = pagina_e2e.evaluate("""
        (() => {
            const el = document.activeElement;
            return getComputedStyle(el).outlineColor;
        })()
    """)
    assert color == "rgb(182, 154, 100)", f"outline-color inesperado: {color}"


# ===========================================================================
# CA8: viewport 360px
# ===========================================================================


@pytest.mark.e2e
def test_ca8_scroll_width_no_supera_360(servidor_e2e: str, navegador_e2e: Any) -> None:
    """CA8: con viewport de 360px, documentElement.scrollWidth no supera 360."""
    contexto = navegador_e2e.new_context(viewport={"width": 360, "height": 640})
    pagina = contexto.new_page()
    try:
        pagina.goto(f"{servidor_e2e.rstrip('/')}/", wait_until="networkidle")
        ancho = pagina.evaluate("document.documentElement.scrollWidth")
        assert ancho <= 360, (
            f"scrollWidth={ancho} supera 360px en viewport de 360px"
        )
    finally:
        contexto.close()
