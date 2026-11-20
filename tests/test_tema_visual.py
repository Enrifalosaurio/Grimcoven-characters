"""Tests de US-014: Tema visual del diseno con fuentes locales, navegacion y pie.

Cada test indica el criterio de aceptacion (CA<n>) que cubre.
Se usa fastapi.testclient.TestClient (basado en httpx) sin levantar servidor.
Los tests e2e (CA4, CA7, CA8) estan en tests/e2e/test_tema_e2e.py.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from grimcoven_equipos.app import create_app

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------

_RAIZ = Path(__file__).resolve().parent.parent
_DIR_STATIC = _RAIZ / "src" / "grimcoven_equipos" / "static"
_DIR_CSS = _DIR_STATIC / "css"
_DIR_FONTS = _DIR_STATIC / "fonts"
_DIR_TEMPLATES = _RAIZ / "src" / "grimcoven_equipos" / "templates"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app() -> FastAPI:
    """Instancia de la app creada con create_app()."""
    return create_app()


@pytest.fixture(scope="module")
def client(app) -> TestClient:
    """Cliente HTTP sincrono para la app."""
    return TestClient(app)


@pytest.fixture(scope="module")
def css_texto(client: TestClient) -> str:
    """Texto completo de tema.css."""
    resp = client.get("/static/css/tema.css")
    assert resp.status_code == 200
    return resp.text


@pytest.fixture(scope="module")
def html_inicio(client: TestClient) -> str:
    """HTML de la pagina de inicio."""
    resp = client.get("/")
    assert resp.status_code == 200
    return resp.text


# ===========================================================================
# CA1: GET /static/css/tema.css -> 200, text/css, variables CSS nuevas,
#      sin MedievalSharp, --color-pergamino, @import ni googleapis
# ===========================================================================


class TestCA1TokensCSS:
    """CA1: tema.css define los tokens del nuevo tema y no tiene restos del viejo."""

    def test_ca1_status_200_y_content_type(self, client: TestClient) -> None:
        """CA1: GET /static/css/tema.css responde 200 con text/css."""
        resp = client.get("/static/css/tema.css")
        assert resp.status_code == 200
        assert "text/css" in resp.headers.get("content-type", "")

    @pytest.mark.parametrize(
        "variable, valor",
        [
            ("--void", "#100F12"),
            ("--char", "#19171C"),
            ("--char-2", "#211E25"),
            ("--blood", "#8F3035"),
            ("--blood-hi", "#B0434A"),
            ("--gold", "#B69A64"),
            ("--ivory", "#E5DFD2"),
            ("--ash", "#969099"),
            ("--parch", "#2A2420"),
            ("--parch-ink", "#D9CDB4"),
        ],
    )
    def test_ca1_variable_css(self, css_texto: str, variable: str, valor: str) -> None:
        """CA1: tema.css define la variable con su valor esperado."""
        patron = rf"{re.escape(variable)}\s*:\s*{re.escape(valor)}"
        assert re.search(patron, css_texto, re.IGNORECASE), (
            f"No se encontro {variable}: {valor} en tema.css"
        )

    def test_ca1_sin_medievalsharp(self, css_texto: str) -> None:
        """CA1: tema.css no contiene 'MedievalSharp'."""
        assert "MedievalSharp" not in css_texto

    def test_ca1_sin_color_pergamino(self, css_texto: str) -> None:
        """CA1: tema.css no contiene '--color-pergamino'."""
        assert "--color-pergamino" not in css_texto

    def test_ca1_sin_import(self, css_texto: str) -> None:
        """CA1: tema.css no contiene '@import'."""
        assert "@import" not in css_texto

    def test_ca1_sin_googleapis(self, css_texto: str) -> None:
        """CA1: tema.css no contiene 'googleapis'."""
        assert "googleapis" not in css_texto


# ===========================================================================
# CA2: @font-face para 5 familias con font-display: swap, URLs responden 200
# ===========================================================================

_FUENTES_REQUERIDAS = [
    "UnifrakturMaguntia",
    "IM Fell English SC",
    "IM Fell English",
    "Spectral",
    "Cinzel",
]


class TestCA2FontFace:
    """CA2: tema.css tiene @font-face para cada familia con font-display: swap."""

    @pytest.mark.parametrize("familia", _FUENTES_REQUERIDAS)
    def test_ca2_font_face_existe(self, css_texto: str, familia: str) -> None:
        """CA2: hay un @font-face con font-family que incluye la familia."""
        patron = rf"@font-face\s*\{{[^}}]*font-family\s*:\s*['\"]?{re.escape(familia)}['\"]?\s*;"
        assert re.search(patron, css_texto, re.IGNORECASE | re.DOTALL), (
            f"No se encontro @font-face para '{familia}'"
        )

    @pytest.mark.parametrize("familia", _FUENTES_REQUERIDAS)
    def test_ca2_font_display_swap(self, css_texto: str, familia: str) -> None:
        """CA2: el @font-face de la familia incluye font-display: swap."""
        # Extraer el bloque @font-face que contenga la familia
        esc = re.escape(familia)
        patron = rf"@font-face\s*\{{([^}}]*font-family\s*:\s*['\"]?{esc}['\"]?\s*;[^}}]*)\}}"
        match = re.search(patron, css_texto, re.IGNORECASE | re.DOTALL)
        assert match is not None, f"No se encontro @font-face para '{familia}'"
        bloque = match.group(1)
        assert re.search(r"font-display\s*:\s*swap", bloque, re.IGNORECASE), (
            f"El @font-face de '{familia}' no tiene font-display: swap"
        )

    def test_ca2_urls_de_fuentes_responden_200(
        self, client: TestClient, css_texto: str
    ) -> None:
        """CA2: cada url('/static/fonts/...') en los @font-face responde 200."""
        urls = re.findall(r"url\(\s*['\"]?(/static/fonts/[^'\")\s]+)", css_texto)
        assert len(urls) > 0, "No se encontraron urls de fuentes en tema.css"
        for url in urls:
            resp = client.get(url)
            assert resp.status_code == 200, f"La fuente {url} no responde 200"


# ===========================================================================
# CA3: Licencias OFL en static/fonts/
# ===========================================================================

_FAMILIAS_LICENCIA = [
    "UnifrakturMaguntia",
    "IM_Fell_English_SC",
    "IM_Fell_English",
    "Spectral",
    "Cinzel",
]


class TestCA3Licencias:
    """CA3: hay un fichero de licencia por familia con 'SIL OPEN FONT LICENSE'."""

    def test_ca3_directorio_fonts_existe(self) -> None:
        """CA3: existe el directorio static/fonts/."""
        assert _DIR_FONTS.exists(), f"No existe {_DIR_FONTS}"

    def test_ca3_al_menos_5_licencias(self) -> None:
        """CA3: hay al menos 5 ficheros de licencia (uno por familia)."""
        licencias = list(_DIR_FONTS.rglob("*LICENSE*")) + list(
            _DIR_FONTS.rglob("*license*")
        ) + list(_DIR_FONTS.rglob("*OFL*"))
        # Deduplicar
        licencias_unicas = {str(p) for p in licencias}
        assert len(licencias_unicas) >= 5, (
            f"Se esperaban al menos 5 ficheros de licencia, se encontraron {len(licencias_unicas)}"
        )

    def test_ca3_licencias_contienen_ofl(self) -> None:
        """CA3: cada fichero de licencia contiene 'SIL OPEN FONT LICENSE'."""
        licencias = list(_DIR_FONTS.rglob("*LICENSE*")) + list(
            _DIR_FONTS.rglob("*license*")
        ) + list(_DIR_FONTS.rglob("*OFL*"))
        licencias_unicas = list({str(p): p for p in licencias}.values())
        assert len(licencias_unicas) > 0, "No se encontraron ficheros de licencia"
        for lic in licencias_unicas:
            contenido = lic.read_text(encoding="utf-8", errors="replace").upper()
            assert "SIL OPEN FONT LICENSE" in contenido, (
                f"El fichero {lic.name} no contiene 'SIL OPEN FONT LICENSE'"
            )


# ===========================================================================
# CA4: E2E en Chromium -> tests en tests/e2e/test_tema_e2e.py
# ===========================================================================


# ===========================================================================
# CA5: HTML estructura: html lang=es, header.nav, a.mark, aria-current=page
# ===========================================================================


class TestCA5Estructura:
    """CA5: GET / tiene la estructura de navegacion correcta."""

    def test_ca5_html_lang_es(self, html_inicio: str) -> None:
        """CA5: hay <html lang='es'>."""
        assert re.search(r"<html[^>]*\slang=['\"]es['\"]", html_inicio), (
            "No se encontro <html lang='es'>"
        )

    def test_ca5_header_class_nav(self, html_inicio: str) -> None:
        """CA5: hay un <header class='nav'>."""
        assert re.search(
            r"<header[^>]*\bclass=['\"][^'\"]*\bnav\b", html_inicio, re.IGNORECASE
        ), "No se encontro <header class='nav'>"

    def test_ca5_mark_href_inicio(self, html_inicio: str) -> None:
        """CA5: hay un <a class='mark' href='/'>."""
        assert re.search(
            r"<a[^>]*\bclass=['\"][^'\"]*\bmark\b[^'\"]*['\"][^>]*\bhref=['\"]/?['\"]",
            html_inicio,
            re.IGNORECASE,
        ), "No se encontro <a class='mark' href='/'>"

    def test_ca5_mark_contiene_grimcoven(self, html_inicio: str) -> None:
        """CA5: el enlace .mark contiene 'Grimcoven'."""
        # Extraer el contenido del enlace .mark
        match = re.search(
            r"<a[^>]*\bclass=['\"][^'\"]*\bmark\b[^'\"]*['\"][^>]*>(.*?)</a>",
            html_inicio,
            re.IGNORECASE | re.DOTALL,
        )
        assert match is not None, "No se encontro <a class='mark'>"
        contenido = match.group(1)
        assert "Grimcoven" in contenido, (
            f"El enlace .mark no contiene 'Grimcoven': {contenido[:200]}"
        )

    def test_ca5_mark_contiene_codice_de_fans(self, html_inicio: str) -> None:
        """CA5: el enlace .mark contiene 'Codice de fans'."""
        match = re.search(
            r"<a[^>]*\bclass=['\"][^'\"]*\bmark\b[^'\"]*['\"][^>]*>(.*?)</a>",
            html_inicio,
            re.IGNORECASE | re.DOTALL,
        )
        assert match is not None, "No se encontro <a class='mark'>"
        contenido = match.group(1)
        assert "dice de fans" in contenido.lower(), (
            f"El enlace .mark no contiene 'Codice de fans': {contenido[:200]}"
        )

    def test_ca5_unico_aria_current_page(self, html_inicio: str) -> None:
        """CA5: hay un unico aria-current='page' en la pagina."""
        ocurrencias = re.findall(r"aria-current=['\"]page['\"]", html_inicio)
        assert len(ocurrencias) == 1, (
            f"Se esperaba 1 aria-current='page', se encontraron {len(ocurrencias)}"
        )

    def test_ca5_aria_current_en_enlace_inicio(self, html_inicio: str) -> None:
        """CA5: el aria-current='page' esta en el enlace 'Inicio'."""
        match = re.search(
            r"<a[^>]*aria-current=['\"]page['\"][^>]*>(.*?)</a>",
            html_inicio,
            re.IGNORECASE | re.DOTALL,
        )
        assert match is not None, "No se encontro enlace con aria-current='page'"
        assert "Inicio" in match.group(1), (
            f"El aria-current='page' no esta en el enlace 'Inicio': {match.group(1)}"
        )

    def test_ca5_aria_current_en_aleatorio(self, client: TestClient) -> None:
        """CA5: en GET /aleatorio, aria-current='page' esta en 'Equipo aleatorio'."""
        resp = client.get("/aleatorio")
        html = resp.text
        ocurrencias = re.findall(r"aria-current=['\"]page['\"]", html)
        assert len(ocurrencias) == 1, (
            f"Se esperaba 1 aria-current='page' en /aleatorio, se encontraron {len(ocurrencias)}"
        )
        match = re.search(
            r"<a[^>]*aria-current=['\"]page['\"][^>]*>(.*?)</a>",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        assert match is not None, "No se encontro enlace con aria-current='page' en /aleatorio"
        assert "Equipo aleatorio" in match.group(1), (
            f"aria-current='page' no esta en 'Equipo aleatorio': {match.group(1)}"
        )

    def test_ca5_aria_current_en_recomendador(self, client: TestClient) -> None:
        """CA5: en GET /recomendador, aria-current='page' esta en 'Recomendador'."""
        resp = client.get("/recomendador")
        html = resp.text
        ocurrencias = re.findall(r"aria-current=['\"]page['\"]", html)
        assert len(ocurrencias) == 1, (
            f"Se esperaba 1 aria-current='page' en /recomendador, se encontraron {len(ocurrencias)}"
        )
        match = re.search(
            r"<a[^>]*aria-current=['\"]page['\"][^>]*>(.*?)</a>",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        assert match is not None, "No se encontro enlace con aria-current='page' en /recomendador"
        assert "Recomendador" in match.group(1), (
            f"aria-current='page' no esta en 'Recomendador': {match.group(1)}"
        )

    def test_ca5_header_nav_landmark(self, html_inicio: str) -> None:
        """CA5 fix iter2: el header contiene un <nav aria-label='Principal'>."""
        assert re.search(
            r"<header[^>]*>.*?<nav[^>]*\baria-label=['\"]Principal['\"]",
            html_inicio,
            re.IGNORECASE | re.DOTALL,
        ), "No se encontro <nav aria-label='Principal'> dentro del header"

    def test_ca5_inicio_nav_aria_label(self, html_inicio: str) -> None:
        """CA5 fix iter2: el nav de herramientas de inicio tiene aria-label."""
        # El nav del contenido principal debe tener aria-label
        # Buscar un nav con aria-label='Herramientas' (distinto del nav 'Pie' y 'Principal')
        assert re.search(
            r"<nav[^>]*\baria-label=['\"]Herramientas['\"]",
            html_inicio,
            re.IGNORECASE,
        ), "No se encontro <nav aria-label='Herramientas'> en la pagina de inicio"


# ===========================================================================
# CA6: Pie de pagina
# ===========================================================================


class TestCA6Footer:
    """CA6: GET / tiene el pie de pagina con el contenido correcto."""

    @pytest.mark.parametrize(
        "texto",
        [
            "Proyecto no oficial creado por fans",
            "Grimcoven pertenece a sus respectivos propietarios",
            "no está afiliado a Awaken Realms",
            "Hecho por un fan, para la mesa.",
            "Solo importa la cacería.",
        ],
    )
    def test_ca6_pie_contiene_texto(self, html_inicio: str, texto: str) -> None:
        """CA6: el pie contiene el texto esperado."""
        # Normalizar para comparacion (el HTML puede tener entities)
        assert texto in html_inicio, (
            f"No se encontro '{texto}' en la pagina de inicio"
        )

    def test_ca6_nav_aria_label_pie(self, html_inicio: str) -> None:
        """CA6: hay un <nav aria-label='Pie'> en el footer."""
        assert re.search(
            r"<nav[^>]*\baria-label=['\"]Pie['\"]", html_inicio, re.IGNORECASE
        ), "No se encontro <nav aria-label='Pie'>"

    def test_ca6_nav_pie_tiene_enlaces_navegacion(self, html_inicio: str) -> None:
        """CA6: el nav del pie tiene los mismos enlaces que la navegacion principal."""
        # Extraer los enlaces del nav aria-label='Pie'
        match = re.search(
            r"<nav[^>]*\baria-label=['\"]Pie['\"][^>]*>(.*?)</nav>",
            html_inicio,
            re.IGNORECASE | re.DOTALL,
        )
        assert match is not None, "No se encontro <nav aria-label='Pie'>"
        nav_pie = match.group(1)
        # Debe contener enlaces a /, /aleatorio y /recomendador
        assert 'href="/"' in nav_pie or "href='/'" in nav_pie, (
            "El nav del pie no tiene enlace a /"
        )
        assert "/aleatorio" in nav_pie, "El nav del pie no tiene enlace a /aleatorio"
        assert "/recomendador" in nav_pie, "El nav del pie no tiene enlace a /recomendador"


# ===========================================================================
# CA7: prefers-reduced-motion (no e2e; focus-visible e2e en tests/e2e/test_tema_e2e.py)
# ===========================================================================


class TestCA7ReducedMotion:
    """CA7: tema.css incluye regla reduced-motion."""

    def test_ca7_css_reduced_motion(self, css_texto: str) -> None:
        """CA7: tema.css incluye una regla @media (prefers-reduced-motion:reduce)."""
        patron = r"@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)"
        assert re.search(patron, css_texto), (
            "No se encontro @media (prefers-reduced-motion:reduce) en tema.css"
        )


# ===========================================================================
# CA8: viewport 360px -> tests en tests/e2e/test_tema_e2e.py
# ===========================================================================


# ===========================================================================
# CA9: /aleatorio y /recomendador siguen respondiendo 200 con el tema nuevo
# ===========================================================================


class TestCA9Compatibilidad:
    """CA9: las paginas existentes siguen funcionando con el tema nuevo."""

    def test_ca9_aleatorio_status_200(self, client: TestClient) -> None:
        """CA9: GET /aleatorio responde 200."""
        resp = client.get("/aleatorio")
        assert resp.status_code == 200

    def test_ca9_aleatorio_enlaza_tema_css(self, client: TestClient) -> None:
        """CA9: GET /aleatorio enlaza /static/css/tema.css."""
        resp = client.get("/aleatorio")
        assert "/static/css/tema.css" in resp.text

    def test_ca9_recomendador_status_200(self, client: TestClient) -> None:
        """CA9: GET /recomendador responde 200."""
        resp = client.get("/recomendador")
        assert resp.status_code == 200

    def test_ca9_recomendador_enlaza_tema_css(self, client: TestClient) -> None:
        """CA9: GET /recomendador enlaza /static/css/tema.css."""
        resp = client.get("/recomendador")
        assert "/static/css/tema.css" in resp.text

    def test_ca9_aleatorio_formulario_presente(self, client: TestClient) -> None:
        """CA9: /aleatorio mantiene el formulario con sus clases."""
        resp = client.get("/aleatorio")
        html = resp.text
        assert re.search(
            r"<form[^>]*method=['\"]get['\"]", html, re.IGNORECASE
        ), "No se encontro <form method='get'> en /aleatorio"

    def test_ca9_aleatorio_clases_heredadas(self, client: TestClient) -> None:
        """CA9: /aleatorio con resultado mantiene las clases existentes."""
        resp = client.get("/aleatorio", params={"tamano": 3, "semilla": 42})
        html = resp.text
        assert re.search(r"\bcarta-cazador\b", html), "Falta clase carta-cazador"
        assert re.search(r"\bnombre-cazador\b", html), "Falta clase nombre-cazador"
        assert re.search(r"\broles-cazador\b", html), "Falta clase roles-cazador"

    def test_ca9_aleatorio_mensaje_error_presente(self, client: TestClient) -> None:
        """CA9: /aleatorio con tamano invalido mantiene .mensaje-error."""
        resp = client.get("/aleatorio", params={"tamano": 7})
        html = resp.text
        assert re.search(r"\bmensaje-error\b", html), "Falta clase mensaje-error"

    def test_ca9_recomendador_formulario_presente(self, client: TestClient) -> None:
        """CA9: /recomendador mantiene el formulario con sus clases."""
        resp = client.get("/recomendador")
        html = resp.text
        assert re.search(
            r"<form[^>]*class=['\"][^'\"]*form-recomendador", html, re.IGNORECASE
        ), "No se encontro <form class='form-recomendador'>"

    def test_ca9_recomendador_resultados_clases(self, client: TestClient) -> None:
        """CA9: /recomendador con resultado mantiene equipo-recomendado."""
        resp = client.get(
            "/recomendador", params={"griefbound": "convergence", "tamano": 2}
        )
        html = resp.text
        assert re.search(r"\bequipo-recomendado\b", html), (
            "Falta clase equipo-recomendado en resultados"
        )

    def test_ca9_recomendador_mensaje_error(self, client: TestClient) -> None:
        """CA9: /recomendador con tamano invalido mantiene .mensaje-error."""
        resp = client.get(
            "/recomendador", params={"griefbound": "convergence", "tamano": 9}
        )
        html = resp.text
        assert re.search(r"\bmensaje-error\b", html), "Falta clase mensaje-error"

    def test_ca9_css_clases_heredadas_definidas(self, css_texto: str) -> None:
        """CA9: tema.css sigue definiendo las clases usadas por aleatorio y recomendador."""
        clases_requeridas = [
            "carta-cazador",
            "nombre-cazador",
            "roles-cazador",
            "equipo",
            "mensaje-error",
            "boton-secundario",
            "aviso",
            "equipo-recomendado",
            "form-recomendador",
        ]
        for clase in clases_requeridas:
            assert re.search(rf"\.{re.escape(clase)}\b", css_texto), (
                f"La clase '.{clase}' no esta definida en tema.css"
            )


# ===========================================================================
# Casos limite adicionales
# ===========================================================================


class TestEdgeCases:
    """Casos limite que complementan los criterios de aceptacion."""

    def test_edge_base_html_tiene_main(self) -> None:
        """Caso limite: base.html envuelve el contenido en un <main>."""
        ruta = _DIR_TEMPLATES / "base.html"
        assert ruta.exists(), f"No existe {ruta}"
        contenido = ruta.read_text(encoding="utf-8")
        assert "<main" in contenido, "base.html no tiene un elemento <main>"

    def test_edge_base_html_tiene_header_nav(self) -> None:
        """Caso limite: base.html tiene la estructura de navegacion header.nav."""
        ruta = _DIR_TEMPLATES / "base.html"
        contenido = ruta.read_text(encoding="utf-8")
        assert re.search(
            r"<header[^>]*\bclass=['\"][^'\"]*\bnav\b", contenido, re.IGNORECASE
        ), "base.html no tiene <header class='nav'>"

    def test_edge_tema_css_selectores_accesibilidad(self, css_texto: str) -> None:
        """Caso limite: tema.css tiene selectores explicitos para a:hover, a:focus-visible,
        button:focus-visible y select:focus-visible."""
        for selector in [
            "a:hover",
            "a:focus-visible",
            "button:focus-visible",
            "select:focus-visible",
        ]:
            assert selector in css_texto, f"Falta selector '{selector}' en tema.css"

    def test_edge_focus_visible_outline_gold(self, css_texto: str) -> None:
        """Caso limite (CA7): a:focus-visible tiene outline con --gold."""
        # Verificar que el bloque a:focus-visible contiene outline y --gold
        assert re.search(
            r"a:focus-visible\s*\{[^}]*outline[^}]*--gold", css_texto, re.DOTALL
        ), "a:focus-visible no tiene outline con --gold en tema.css"

    def test_edge_api_sigue_funcionando(self, client: TestClient) -> None:
        """Caso limite: los endpoints de la API siguen respondiendo 200."""
        resp = client.get("/api/cazadores")
        assert resp.status_code == 200
        resp2 = client.get(
            "/api/equipos/aleatorio", params={"tamano": 3, "semilla": 1}
        )
        assert resp2.status_code == 200

    def test_edge_html_charset_utf8(self, html_inicio: str) -> None:
        """Caso limite: la pagina de inicio declara charset utf-8."""
        texto = html_inicio.lower()
        assert "utf-8" in texto or "utf8" in texto

    def test_edge_orn_symbol_en_base(self) -> None:
        """Caso limite: base.html define el simbolo SVG #orn para <use href='#orn'>."""
        ruta = _DIR_TEMPLATES / "base.html"
        contenido = ruta.read_text(encoding="utf-8")
        assert 'id="orn"' in contenido or "id='orn'" in contenido, (
            "base.html no define el simbolo SVG #orn"
        )

    def test_edge_no_estilos_inline_inicio(self, html_inicio: str) -> None:
        """Caso limite: la pagina de inicio no tiene estilos en linea."""
        # Permitir style en SVGs (como style="position:absolute")
        # Solo buscar en tags no-SVG
        estilos = re.findall(
            r"<(?!svg\b)[a-z][^>]*\bstyle\s*=\s*['\"]", html_inicio, re.IGNORECASE
        )
        assert len(estilos) == 0, f"Se encontraron {len(estilos)} estilos en linea"

    def test_edge_fuentes_woff2_no_placeholder(self) -> None:
        """Caso limite: los ficheros woff2 son fuentes reales (>1000 bytes)."""
        woff2_files = list(_DIR_FONTS.glob("*.woff2"))
        assert len(woff2_files) >= 10, (
            f"Se esperaban al menos 10 fuentes woff2, se encontraron {len(woff2_files)}"
        )
        for f in woff2_files:
            size = f.stat().st_size
            assert size > 1000, (
                f"{f.name} parece un placeholder ({size} bytes, se esperan >1000)"
            )

    def test_edge_mensaje_error_contraste(self, css_texto: str) -> None:
        """Caso limite: .mensaje-error no usa --blood-hi (contraste insuficiente)."""
        # Extraer el bloque .mensaje-error
        match = re.search(
            r"\.mensaje-error\s*\{([^}]*)\}", css_texto, re.DOTALL
        )
        assert match is not None, "No se encontro bloque .mensaje-error en tema.css"
        bloque = match.group(1)
        # El color de texto no debe ser --blood-hi (ratio ~2.97:1 < 3:1)
        assert "--blood-hi" not in bloque, (
            ".mensaje-error usa --blood-hi que tiene contraste insuficiente (~2.97:1)"
        )
        # Tampoco debe usar #D4686F (ratio ~3.6:1 < 4.5:1 sobre fondo efectivo)
        assert "#D4686F" not in bloque.upper().replace(" ", ""), (
            ".mensaje-error usa #D4686F que tiene contraste insuficiente (~3.6:1)"
        )

    def test_edge_sr_only_definida(self, css_texto: str) -> None:
        """Caso limite: tema.css define .sr-only con el patron visually-hidden."""
        assert re.search(r"\.sr-only\s*\{", css_texto), (
            "No se encontro la clase .sr-only en tema.css"
        )

    def test_edge_body_flex_sticky_footer(self, css_texto: str) -> None:
        """Caso limite: body tiene display: flex y flex-direction: column (sticky footer)."""
        # Buscar el bloque body
        match = re.search(r"\bbody\s*\{([^}]*)\}", css_texto, re.DOTALL)
        assert match is not None, "No se encontro bloque body en tema.css"
        bloque = match.group(1)
        assert re.search(r"display\s*:\s*flex", bloque), (
            "body no tiene display: flex"
        )
        assert re.search(r"flex-direction\s*:\s*column", bloque), (
            "body no tiene flex-direction: column"
        )

    def test_edge_nav_links_no_usan_ash_directo(self, css_texto: str) -> None:
        """Caso limite: .nav ul a usa --ash-text (>=4.5:1) en lugar de --ash."""
        match = re.search(
            r"\.nav\s+ul\s+a\s*\{([^}]*)\}", css_texto, re.DOTALL
        )
        assert match is not None, "No se encontro bloque .nav ul a en tema.css"
        bloque = match.group(1)
        # Debe usar --ash-text, no --ash a secas
        color_match = re.search(r"color\s*:\s*var\(([^)]+)\)", bloque)
        assert color_match is not None, ".nav ul a no tiene color con var()"
        variable = color_match.group(1).strip()
        assert variable == "--ash-text", (
            f".nav ul a usa var({variable}), deberia usar var(--ash-text) para contraste WCAG AA"
        )
