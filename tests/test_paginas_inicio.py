"""Tests de US-005: Tema visual de fantasia oscura y pagina de inicio.

Cada test indica el criterio de aceptacion (CA<n>) que cubre.
Se usa fastapi.testclient.TestClient (basado en httpx) sin levantar servidor.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from grimcoven_equipos.app import create_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app():
    """Instancia de la app creada con create_app()."""
    return create_app()


@pytest.fixture(scope="module")
def client(app) -> TestClient:
    """Cliente HTTP sincrono para la app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# CA1: GET / -> 200, text/html, <html lang="es">, <h1>Grimcoven, enlaces
# ---------------------------------------------------------------------------


def test_ca1_get_inicio_status_200(client: TestClient) -> None:
    """CA1: GET / responde 200."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_ca1_get_inicio_content_type_html(client: TestClient) -> None:
    """CA1: GET / responde con content-type text/html."""
    resp = client.get("/")
    assert "text/html" in resp.headers.get("content-type", "")


def test_ca1_get_inicio_html_lang_es(client: TestClient) -> None:
    """CA1: GET / contiene <html lang='es'>."""
    resp = client.get("/")
    assert '<html lang="es">' in resp.text or "<html lang='es'>" in resp.text


def test_ca1_get_inicio_h1_grimcoven(client: TestClient) -> None:
    """CA1: GET / contiene un <h1> con el texto 'Grimcoven'."""
    resp = client.get("/")
    # Buscar <h1...>Grimcoven</h1> permitiendo atributos en el h1
    match = re.search(r"<h1[^>]*>\s*Grimcoven\s*</h1>", resp.text, re.IGNORECASE)
    assert match is not None, "No se encontro <h1>Grimcoven</h1> en la respuesta"


def test_ca1_get_inicio_enlace_aleatorio(client: TestClient) -> None:
    """CA1: GET / contiene un enlace a /aleatorio."""
    resp = client.get("/")
    assert 'href="/aleatorio"' in resp.text or "href='/aleatorio'" in resp.text


def test_ca1_get_inicio_enlace_recomendador(client: TestClient) -> None:
    """CA1: GET / contiene un enlace a /recomendador."""
    resp = client.get("/")
    assert 'href="/recomendador"' in resp.text or "href='/recomendador'" in resp.text


# ---------------------------------------------------------------------------
# CA2: GET /static/css/tema.css -> 200, text/css, variables CSS
# ---------------------------------------------------------------------------


def test_ca2_get_tema_css_status_200(client: TestClient) -> None:
    """CA2: GET /static/css/tema.css responde 200."""
    resp = client.get("/static/css/tema.css")
    assert resp.status_code == 200


def test_ca2_get_tema_css_content_type(client: TestClient) -> None:
    """CA2: GET /static/css/tema.css responde con content-type text/css."""
    resp = client.get("/static/css/tema.css")
    assert "text/css" in resp.headers.get("content-type", "")


def test_ca2_variable_color_pergamino(client: TestClient) -> None:
    """CA2: tema.css define --color-pergamino: #e8d8b0."""
    resp = client.get("/static/css/tema.css")
    assert "--color-pergamino:" in resp.text
    # Verificar el valor exacto (permitiendo espacios)
    match = re.search(r"--color-pergamino:\s*#e8d8b0", resp.text, re.IGNORECASE)
    assert match is not None, "No se encontro --color-pergamino: #e8d8b0"


def test_ca2_variable_color_ocre(client: TestClient) -> None:
    """CA2: tema.css define --color-ocre: #b5832a."""
    resp = client.get("/static/css/tema.css")
    match = re.search(r"--color-ocre:\s*#b5832a", resp.text, re.IGNORECASE)
    assert match is not None, "No se encontro --color-ocre: #b5832a"


def test_ca2_variable_color_granate(client: TestClient) -> None:
    """CA2: tema.css define --color-granate: #6e1414."""
    resp = client.get("/static/css/tema.css")
    match = re.search(r"--color-granate:\s*#6e1414", resp.text, re.IGNORECASE)
    assert match is not None, "No se encontro --color-granate: #6e1414"


def test_ca2_variable_color_tinta(client: TestClient) -> None:
    """CA2: tema.css define --color-tinta: #2a1a12."""
    resp = client.get("/static/css/tema.css")
    match = re.search(r"--color-tinta:\s*#2a1a12", resp.text, re.IGNORECASE)
    assert match is not None, "No se encontro --color-tinta: #2a1a12"


# ---------------------------------------------------------------------------
# CA3: body usa pergamino/tinta; h1, h2 usan MedievalSharp...serif
# ---------------------------------------------------------------------------


def test_ca3_body_fondo_pergamino(client: TestClient) -> None:
    """CA3: body usa var(--color-pergamino) como fondo."""
    resp = client.get("/static/css/tema.css")
    css = resp.text
    # Buscar background (o background-color) con var(--color-pergamino) dentro de body
    body_block = _extraer_bloque_css(css, "body")
    assert body_block is not None, "No se encontro el bloque 'body' en tema.css"
    assert "var(--color-pergamino)" in body_block, (
        "body no usa var(--color-pergamino) como fondo"
    )


def test_ca3_body_color_tinta(client: TestClient) -> None:
    """CA3: body usa var(--color-tinta) como color de texto."""
    resp = client.get("/static/css/tema.css")
    css = resp.text
    body_block = _extraer_bloque_css(css, "body")
    assert body_block is not None, "No se encontro el bloque 'body' en tema.css"
    # Buscar 'color:' (no 'background-color:') con var(--color-tinta)
    # Usamos regex para que no matchee background-color
    match = re.search(r"(?<!-)color\s*:\s*var\(--color-tinta\)", body_block)
    assert match is not None, "body no usa var(--color-tinta) como color de texto"


def test_ca3_h1_font_family_medievalsharp(client: TestClient) -> None:
    """CA3: h1 declara un font-family que empieza por 'MedievalSharp'."""
    resp = client.get("/static/css/tema.css")
    css = resp.text
    h1_block = _extraer_bloque_css_selector(css, "h1")
    assert h1_block is not None, "No se encontro selector que incluya 'h1' en tema.css"
    match = re.search(r"font-family\s*:\s*['\"]?MedievalSharp", h1_block)
    assert match is not None, "h1 no tiene font-family que empiece por 'MedievalSharp'"


def test_ca3_h1_font_family_termina_serif(client: TestClient) -> None:
    """CA3: h1 declara un font-family que termina en serif."""
    resp = client.get("/static/css/tema.css")
    css = resp.text
    h1_block = _extraer_bloque_css_selector(css, "h1")
    assert h1_block is not None, "No se encontro selector que incluya 'h1' en tema.css"
    match = re.search(r"font-family\s*:[^;]*,\s*serif\s*;", h1_block)
    assert match is not None, "h1 font-family no termina en serif"


def test_ca3_h2_font_family_medievalsharp(client: TestClient) -> None:
    """CA3: h2 declara un font-family que empieza por 'MedievalSharp'."""
    resp = client.get("/static/css/tema.css")
    css = resp.text
    h2_block = _extraer_bloque_css_selector(css, "h2")
    assert h2_block is not None, "No se encontro selector que incluya 'h2' en tema.css"
    match = re.search(r"font-family\s*:\s*['\"]?MedievalSharp", h2_block)
    assert match is not None, "h2 no tiene font-family que empiece por 'MedievalSharp'"


def test_ca3_h2_font_family_termina_serif(client: TestClient) -> None:
    """CA3: h2 declara un font-family que termina en serif."""
    resp = client.get("/static/css/tema.css")
    css = resp.text
    h2_block = _extraer_bloque_css_selector(css, "h2")
    assert h2_block is not None, "No se encontro selector que incluya 'h2' en tema.css"
    match = re.search(r"font-family\s*:[^;]*,\s*serif\s*;", h2_block)
    assert match is not None, "h2 font-family no termina en serif"


# ---------------------------------------------------------------------------
# CA4: paginas HTML extienden base.html, enlazan tema.css, pie legal
# ---------------------------------------------------------------------------


def test_ca4_inicio_enlaza_tema_css(client: TestClient) -> None:
    """CA4: la pagina de inicio enlaza /static/css/tema.css."""
    resp = client.get("/")
    assert "/static/css/tema.css" in resp.text


def test_ca4_inicio_pie_legal(client: TestClient) -> None:
    """CA4: la pagina de inicio incluye el texto legal en el pie."""
    resp = client.get("/")
    # Normalizar acentos: la app puede usar tildes o no en 'Aplicacion'
    texto_normalizado = resp.text.lower()
    assert "no oficial" in texto_normalizado, (
        "No se encontro el texto del pie legal"
    )
    assert "grimcoven pertenece a sus respectivos" in texto_normalizado, (
        "No se encontro la atribucion de Grimcoven en el pie"
    )


def test_ca4_plantilla_base_existe() -> None:
    """CA4: existe la plantilla base.html en templates/."""
    from pathlib import Path

    ruta_base = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "grimcoven_equipos"
        / "templates"
        / "base.html"
    )
    assert ruta_base.exists(), f"No existe {ruta_base}"


def test_ca4_inicio_hereda_base_html() -> None:
    """CA4: inicio.html extiende base.html (contiene extends 'base.html')."""
    from pathlib import Path

    ruta_inicio = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "grimcoven_equipos"
        / "templates"
        / "inicio.html"
    )
    assert ruta_inicio.exists(), f"No existe {ruta_inicio}"
    contenido = ruta_inicio.read_text(encoding="utf-8")
    assert "base.html" in contenido, "inicio.html no extiende base.html"
    # Verificar que usa {% extends %}
    assert re.search(r"\{%\s*extends\s+['\"]base\.html['\"]\s*%\}", contenido), (
        "inicio.html no contiene {% extends 'base.html' %}"
    )


def test_ca4_base_html_enlaza_tema_css() -> None:
    """CA4: base.html enlaza /static/css/tema.css."""
    from pathlib import Path

    ruta_base = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "grimcoven_equipos"
        / "templates"
        / "base.html"
    )
    contenido = ruta_base.read_text(encoding="utf-8")
    assert "/static/css/tema.css" in contenido or "tema.css" in contenido, (
        "base.html no enlaza tema.css"
    )


def test_ca4_base_html_pie_legal() -> None:
    """CA4: base.html incluye el texto legal en el pie."""
    from pathlib import Path

    ruta_base = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "grimcoven_equipos"
        / "templates"
        / "base.html"
    )
    contenido = ruta_base.read_text(encoding="utf-8").lower()
    assert "no oficial" in contenido
    assert "grimcoven pertenece a sus respectivos" in contenido


# ---------------------------------------------------------------------------
# CA5: la pagina / no referencia 'Resources' ni imagenes oficiales
# ---------------------------------------------------------------------------


def test_ca5_inicio_sin_referencia_resources(client: TestClient) -> None:
    """CA5: GET / no referencia ninguna ruta que contenga 'Resources'."""
    resp = client.get("/")
    assert "Resources" not in resp.text, (
        "La pagina de inicio referencia 'Resources'"
    )
    texto_sin_legal = resp.text.lower().replace(
        "grimcoven pertenece a sus respectivos propietarios", ""
    )
    assert "resources" not in texto_sin_legal, (
        "La pagina de inicio referencia 'resources' (case-insensitive)"
    )


def test_ca5_inicio_sin_imagenes_oficiales(client: TestClient) -> None:
    """CA5: GET / no contiene referencias a imagenes oficiales del juego."""
    resp = client.get("/")
    texto = resp.text.lower()
    # No debe haber imagenes con rutas a Resources o ficheros del juego
    assert "resources/" not in texto, "La pagina referencia un directorio Resources/"
    # No debe haber tags <img> con fuentes del juego (PDFs u oficiales)
    imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)', resp.text)
    for src in imgs:
        assert "resources" not in src.lower(), (
            f"Imagen con referencia a resources: {src}"
        )
        assert ".pdf" not in src.lower(), (
            f"Imagen con referencia a PDF: {src}"
        )


# ---------------------------------------------------------------------------
# Casos limite adicionales
# ---------------------------------------------------------------------------


def test_edge_css_cuatro_variables_en_root(client: TestClient) -> None:
    """Caso limite: las 4 variables CSS estan en :root."""
    resp = client.get("/static/css/tema.css")
    css = resp.text
    root_block = _extraer_bloque_css(css, ":root")
    assert root_block is not None, "No se encontro :root en tema.css"
    assert "--color-pergamino" in root_block
    assert "--color-ocre" in root_block
    assert "--color-granate" in root_block
    assert "--color-tinta" in root_block


def test_edge_api_sigue_funcionando(client: TestClient) -> None:
    """Caso limite: los endpoints de la API siguen respondiendo 200."""
    resp = client.get("/api/cazadores")
    assert resp.status_code == 200
    resp2 = client.get("/api/equipos/aleatorio", params={"tamano": 3, "semilla": 1})
    assert resp2.status_code == 200


def test_edge_html_charset_utf8(client: TestClient) -> None:
    """Caso limite: la pagina de inicio declara charset utf-8."""
    resp = client.get("/")
    texto = resp.text.lower()
    assert "utf-8" in texto or "utf8" in texto, (
        "La pagina de inicio no declara charset utf-8"
    )


# ---------------------------------------------------------------------------
# Fix iter2: a:hover no debe usar var(--color-ocre) sobre fondo pergamino
# (contraste insuficiente ~1.74:1, WCAG 2.2 AA exige >= 4.5:1)
# ---------------------------------------------------------------------------


def test_fix_hover_no_usa_ocre_crudo(client: TestClient) -> None:
    """Fix iter2-P1: a:hover no debe usar var(--color-ocre) como color de texto."""
    resp = client.get("/static/css/tema.css")
    css = resp.text
    hover_block = _extraer_bloque_css_selector(css, "a:hover")
    # Solo comprobamos el bloque generico a:hover, no nav a:hover
    assert hover_block is not None, "No se encontro bloque a:hover en tema.css"
    # El color NO debe ser var(--color-ocre) (ratio ~1.74:1 sobre pergamino)
    match = re.search(r"(?<!-)color\s*:\s*var\(--color-ocre\)", hover_block)
    assert match is None, (
        "a:hover sigue usando var(--color-ocre) como color, contraste insuficiente"
    )


def test_fix_hover_tiene_color_con_contraste(client: TestClient) -> None:
    """Fix iter2-P1: a:hover define un color distinto de --color-ocre."""
    resp = client.get("/static/css/tema.css")
    css = resp.text
    hover_block = _extraer_bloque_css_selector(css, "a:hover")
    assert hover_block is not None, "No se encontro bloque a:hover en tema.css"
    # Debe haber una propiedad 'color' definida (no solo border-color)
    match = re.search(r"(?<!-)color\s*:", hover_block)
    assert match is not None, "a:hover no define color de texto"


# ---------------------------------------------------------------------------
# Fix iter2: debe existir regla a:focus-visible con outline visible
# (WCAG 2.4.11 Focus Appearance)
# ---------------------------------------------------------------------------


def test_fix_focus_visible_existe(client: TestClient) -> None:
    """Fix iter2-P2: tema.css contiene una regla a:focus-visible."""
    resp = client.get("/static/css/tema.css")
    css = resp.text
    assert "a:focus-visible" in css, (
        "No se encontro regla a:focus-visible en tema.css"
    )


def test_fix_focus_visible_tiene_outline(client: TestClient) -> None:
    """Fix iter2-P2: a:focus-visible define outline para indicar el foco."""
    resp = client.get("/static/css/tema.css")
    css = resp.text
    focus_block = _extraer_bloque_css_selector(css, "a:focus-visible")
    assert focus_block is not None, "No se encontro bloque a:focus-visible"
    assert "outline" in focus_block, (
        "a:focus-visible no define outline"
    )


# ---------------------------------------------------------------------------
# Helpers para parsear bloques CSS (no son tests)
# ---------------------------------------------------------------------------


def _extraer_bloque_css(css: str, selector: str) -> str | None:
    """Extrae el contenido del bloque CSS para un selector exacto.

    Busca ``selector {`` y devuelve todo hasta el ``}`` de cierre.
    Retorna None si no se encuentra.
    """
    # Escapar caracteres especiales del selector para regex
    selector_escaped = re.escape(selector)
    pattern = rf"{selector_escaped}\s*\{{([^}}]*)\}}"
    match = re.search(pattern, css, re.DOTALL)
    if match:
        return match.group(1)
    return None


def _extraer_bloque_css_selector(css: str, tag: str) -> str | None:
    """Extrae el contenido del bloque CSS para un selector que incluya ``tag``.

    Soporta selectores compuestos como ``h1, h2`` buscando el tag en la parte
    del selector. Retorna None si no se encuentra.
    """
    # Buscar selectores que contengan el tag (ej: "h1, h2 {" o "h1 {")
    pattern = rf"([^{{}}]*\b{re.escape(tag)}\b[^{{}}]*)\{{([^}}]*)\}}"
    match = re.search(pattern, css, re.DOTALL)
    if match:
        return match.group(2)
    return None
