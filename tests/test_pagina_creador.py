"""Tests de US-015: Pagina del creador de equipos con cartas de cazadores reales.

Cada test indica el criterio de aceptacion (CA<n>) que cubre.
Se usa fastapi.testclient.TestClient (basado en httpx) sin levantar servidor.
El catalogo se inyecta con create_app(catalogo=...) segun las convenciones del proyecto.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from grimcoven_equipos.app import create_app
from grimcoven_equipos.catalogo import Catalogo, Cazador, Fuente, Griefbound

# ---------------------------------------------------------------------------
# Datos de prueba para catalogos inyectados (CA7, CA8)
# ---------------------------------------------------------------------------

FICHERO_REGLAS = "GC_Rulebook_280x280mm_bleed3mm [36 pages]_[lowres]_compressed.pdf"


def _cazador(id_: str, nombre: str, **kwargs: object) -> Cazador:
    """Fabrica auxiliar de cazadores de prueba."""
    defaults: dict[str, object] = {
        "expansion": "base",
        "complejidad": "Media",
        "roles": ["dano"],
        "contrarresta": [],
        "vida": 10,
        "movimiento": 2,
        "fuente": Fuente(fichero=FICHERO_REGLAS, pagina=1),
    }
    defaults.update(kwargs)
    return Cazador(id=id_, nombre=nombre, **defaults)  # type: ignore[arg-type]


def _griefbound(id_: str, nombre: str) -> Griefbound:
    return Griefbound(
        id=id_,
        nombre=nombre,
        tipo="griefbound",
        expansion="base",
        amenazas=["prueba"],
        fuente=Fuente(fichero=FICHERO_REGLAS, pagina=2),
    )


# ---------------------------------------------------------------------------
# Fixtures: app con catalogo REAL (CA1-CA6, CA9, CA10)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app():
    """App con catalogo real (cargado desde data/)."""
    return create_app()


@pytest.fixture(scope="module")
def client(app) -> TestClient:
    """Cliente HTTP sincrono para la app real."""
    return TestClient(app)


@pytest.fixture(scope="module")
def html_creador(client: TestClient) -> str:
    """HTML de GET /creador con catalogo real (cacheado por modulo)."""
    resp = client.get("/creador")
    assert resp.status_code == 200
    return resp.text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extraer_carta(html: str, data_id: str) -> str | None:
    """Extrae el bloque HTML de un <article class='card' data-id='...'>
    hasta el siguiente </article>."""
    patron = re.compile(
        rf"<article[^>]*class=[\"'][^\"']*\bcard\b[^\"']*[\"'][^>]*data-id=[\"']{re.escape(data_id)}[\"'][^>]*>"
        r"(.*?)</article>",
        re.DOTALL | re.IGNORECASE,
    )
    # Tambien intentar con data-id antes de class
    match = patron.search(html)
    if not match:
        patron2 = re.compile(
            rf"<article[^>]*data-id=[\"']{re.escape(data_id)}[\"'][^>]*class=[\"'][^\"']*\bcard\b[^\"']*[\"'][^>]*>"
            r"(.*?)</article>",
            re.DOTALL | re.IGNORECASE,
        )
        match = patron2.search(html)
    if match:
        return match.group(0)
    return None


# ===========================================================================
# CA1: GET /creador -> 200, text/html, h1 'Forja tu hermandad', 8 cartas
# ===========================================================================


class TestCA1PaginaCreador:
    """CA1: GET /creador responde 200 con text/html, h1 'Forja tu hermandad' y
    exactamente 8 <article class='card'> con data-id, en orden alfabetico de id."""

    IDS_ESPERADOS = [
        "clockwork-giant",
        "death-jester",
        "duality",
        "gunslinger",
        "keeper",
        "mannequin",
        "technomancer",
        "twins",
    ]

    def test_ca1_status_200(self, client: TestClient) -> None:
        """CA1: GET /creador responde 200."""
        resp = client.get("/creador")
        assert resp.status_code == 200

    def test_ca1_content_type_html(self, client: TestClient) -> None:
        """CA1: GET /creador responde con content-type text/html."""
        resp = client.get("/creador")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_ca1_h1_forja_tu_hermandad(self, html_creador: str) -> None:
        """CA1: la pagina contiene un <h1> con el texto 'Forja tu hermandad'."""
        match = re.search(r"<h1[^>]*>\s*Forja tu hermandad\s*</h1>", html_creador, re.IGNORECASE)
        assert match is not None, "No se encontro <h1>Forja tu hermandad</h1>"

    def test_ca1_exactamente_8_cartas(self, html_creador: str) -> None:
        """CA1: la pagina contiene exactamente 8 <article class='card'>."""
        cartas = re.findall(
            r"<article[^>]*class=[\"'][^\"']*\bcard\b[^\"']*[\"']",
            html_creador,
            re.IGNORECASE,
        )
        assert len(cartas) == 8, f"Se esperaban 8 cartas, se encontraron {len(cartas)}"

    def test_ca1_todas_las_cartas_tienen_data_id(self, html_creador: str) -> None:
        """CA1: cada carta <article class='card'> tiene un atributo data-id."""
        cartas = re.findall(
            r"<article[^>]*class=[\"'][^\"']*\bcard\b[^\"']*[\"'][^>]*>",
            html_creador,
            re.IGNORECASE,
        )
        for carta in cartas:
            assert "data-id" in carta, f"Carta sin data-id: {carta[:100]}"

    def test_ca1_ids_en_orden_correcto(self, html_creador: str) -> None:
        """CA1: los data-id de las cartas estan en orden alfabetico."""
        ids = re.findall(
            r"<article[^>]*class=[\"'][^\"']*\bcard\b[^\"']*[\"'][^>]*data-id=[\"']([^\"']+)[\"']",
            html_creador,
            re.IGNORECASE,
        )
        # Intentar tambien con data-id antes de class
        if not ids:
            ids = re.findall(
                r"<article[^>]*data-id=[\"']([^\"']+)[\"'][^>]*class=[\"'][^\"']*\bcard\b",
                html_creador,
                re.IGNORECASE,
            )
        assert ids == self.IDS_ESPERADOS, (
            f"Los ids no coinciden. Esperado: {self.IDS_ESPERADOS}, obtenido: {ids}"
        )


# ===========================================================================
# CA2: Carta de Gunslinger (vida, movimiento, complejidad, roles, contrarresta)
# ===========================================================================


class TestCA2Gunslinger:
    """CA2: la carta de Gunslinger contiene Vida 13, Movimiento 2, Baja,
    Dano, Control y Contrarresta: enjambre."""

    def test_ca2_gunslinger_vida_13(self, html_creador: str) -> None:
        """CA2: la carta de Gunslinger contiene 'Vida' con 13."""
        carta = _extraer_carta(html_creador, "gunslinger")
        assert carta is not None, "No se encontro la carta de gunslinger"
        assert "Vida" in carta, "La carta de Gunslinger no contiene 'Vida'"
        assert "13" in carta, "La carta de Gunslinger no contiene '13'"

    def test_ca2_gunslinger_movimiento_2(self, html_creador: str) -> None:
        """CA2: la carta de Gunslinger contiene 'Movimiento' con 2."""
        carta = _extraer_carta(html_creador, "gunslinger")
        assert carta is not None
        assert "Movimiento" in carta, "La carta de Gunslinger no contiene 'Movimiento'"
        assert "2" in carta, "La carta de Gunslinger no contiene '2'"

    def test_ca2_gunslinger_complejidad_baja(self, html_creador: str) -> None:
        """CA2: la carta de Gunslinger contiene 'Baja'."""
        carta = _extraer_carta(html_creador, "gunslinger")
        assert carta is not None
        assert "Baja" in carta, "La carta de Gunslinger no contiene 'Baja'"

    def test_ca2_gunslinger_rol_dano(self, html_creador: str) -> None:
        """CA2: la carta de Gunslinger contiene el rol 'Dano' (o etiqueta equivalente)."""
        carta = _extraer_carta(html_creador, "gunslinger")
        assert carta is not None
        # La etiqueta del rol es 'Dano' (con tilde o sin, segun la convencion)
        assert re.search(r"Da[nñ]o", carta), "La carta de Gunslinger no contiene 'Dano'"

    def test_ca2_gunslinger_rol_control(self, html_creador: str) -> None:
        """CA2: la carta de Gunslinger contiene el rol 'Control'."""
        carta = _extraer_carta(html_creador, "gunslinger")
        assert carta is not None
        assert "Control" in carta, "La carta de Gunslinger no contiene 'Control'"

    def test_ca2_gunslinger_contrarresta_enjambre(self, html_creador: str) -> None:
        """CA2: la carta de Gunslinger contiene 'Contrarresta: enjambre'."""
        carta = _extraer_carta(html_creador, "gunslinger")
        assert carta is not None
        assert "Contrarresta" in carta
        assert "enjambre" in carta, "La carta de Gunslinger no contiene 'enjambre'"


# ===========================================================================
# CA3: Carta de Duality (vida y movimiento nulos, roles multiples)
# ===========================================================================


class TestCA3Duality:
    """CA3: la carta de Duality muestra vida y movimiento como emdash,
    complejidad Media y roles Dano, Tanque, Apoyo."""

    def test_ca3_duality_vida_emdash(self, html_creador: str) -> None:
        """CA3: la carta de Duality muestra un emdash como vida."""
        carta = _extraer_carta(html_creador, "duality")
        assert carta is not None, "No se encontro la carta de duality"
        # Buscar 'Vida' seguido (en el HTML) de un emdash
        assert "Vida" in carta
        # El emdash puede ser el caracter literal o la entidad &mdash;
        assert "\u2014" in carta or "&mdash;" in carta, (
            "La carta de Duality no muestra emdash como vida"
        )

    def test_ca3_duality_movimiento_emdash(self, html_creador: str) -> None:
        """CA3: la carta de Duality muestra un emdash como movimiento."""
        carta = _extraer_carta(html_creador, "duality")
        assert carta is not None
        assert "Movimiento" in carta
        # Debe haber al menos 2 emdash (vida y movimiento)
        emdash_count = carta.count("\u2014") + carta.count("&mdash;")
        assert emdash_count >= 2, (
            f"La carta de Duality solo tiene {emdash_count} emdash, se esperan al menos 2"
        )

    def test_ca3_duality_complejidad_media(self, html_creador: str) -> None:
        """CA3: la carta de Duality contiene 'Media'."""
        carta = _extraer_carta(html_creador, "duality")
        assert carta is not None
        assert "Media" in carta, "La carta de Duality no contiene 'Media'"

    def test_ca3_duality_rol_dano(self, html_creador: str) -> None:
        """CA3: la carta de Duality contiene 'Dano'."""
        carta = _extraer_carta(html_creador, "duality")
        assert carta is not None
        assert re.search(r"Da[nñ]o", carta), "La carta de Duality no contiene 'Dano'"

    def test_ca3_duality_rol_tanque(self, html_creador: str) -> None:
        """CA3: la carta de Duality contiene 'Tanque'."""
        carta = _extraer_carta(html_creador, "duality")
        assert carta is not None
        assert "Tanque" in carta, "La carta de Duality no contiene 'Tanque'"

    def test_ca3_duality_rol_apoyo(self, html_creador: str) -> None:
        """CA3: la carta de Duality contiene 'Apoyo'."""
        carta = _extraer_carta(html_creador, "duality")
        assert carta is not None
        assert "Apoyo" in carta, "La carta de Duality no contiene 'Apoyo'"


# ===========================================================================
# CA4: Mannequin no contrarresta nada -> 'Contrarresta: emdash'
# ===========================================================================


class TestCA4MannequinSinContrarresta:
    """CA4: la carta de Mannequin contiene 'Contrarresta: emdash'."""

    def test_ca4_mannequin_contrarresta_emdash(self, html_creador: str) -> None:
        """CA4: la carta de Mannequin muestra 'Contrarresta' seguido de emdash."""
        carta = _extraer_carta(html_creador, "mannequin")
        assert carta is not None, "No se encontro la carta de mannequin"
        assert "Contrarresta" in carta
        # Debe haber un emdash asociado a Contrarresta
        assert "\u2014" in carta or "&mdash;" in carta, (
            "La carta de Mannequin no contiene emdash en Contrarresta"
        )


# ===========================================================================
# CA5: SVG retrato con role='img' y aria-label, sin <img>, sin 'Resources'
# ===========================================================================


class TestCA5RetratosSVG:
    """CA5: cada carta tiene un <svg role='img'> con aria-label 'Retrato ilustrativo: <nombre>',
    la etiqueta 'Ilustrativo', y la pagina no contiene <img> ni 'Resources'."""

    def test_ca5_todas_las_cartas_tienen_svg_role_img(self, html_creador: str) -> None:
        """CA5: cada carta contiene un <svg role='img'>."""
        for cid in TestCA1PaginaCreador.IDS_ESPERADOS:
            carta = _extraer_carta(html_creador, cid)
            assert carta is not None, f"No se encontro la carta de {cid}"
            assert re.search(r"<svg[^>]*role=[\"']img[\"']", carta, re.IGNORECASE), (
                f"La carta de {cid} no contiene <svg role='img'>"
            )

    def test_ca5_aria_label_retrato_ilustrativo(self, html_creador: str) -> None:
        """CA5: el SVG de cada carta tiene aria-label 'Retrato ilustrativo: <nombre>'."""
        # Verificar al menos Gunslinger y Duality como muestra representativa
        carta_gunslinger = _extraer_carta(html_creador, "gunslinger")
        assert carta_gunslinger is not None
        assert re.search(
            r"aria-label=[\"']Retrato ilustrativo: Gunslinger[\"']",
            carta_gunslinger,
            re.IGNORECASE,
        ), "Gunslinger no tiene aria-label 'Retrato ilustrativo: Gunslinger'"

        carta_duality = _extraer_carta(html_creador, "duality")
        assert carta_duality is not None
        assert re.search(
            r"aria-label=[\"']Retrato ilustrativo: Duality[\"']",
            carta_duality,
            re.IGNORECASE,
        ), "Duality no tiene aria-label 'Retrato ilustrativo: Duality'"

    def test_ca5_etiqueta_ilustrativo(self, html_creador: str) -> None:
        """CA5: la pagina contiene la etiqueta 'Ilustrativo'."""
        assert "Ilustrativo" in html_creador or "ilustrativo" in html_creador, (
            "La pagina no contiene la etiqueta 'Ilustrativo'"
        )

    def test_ca5_sin_etiqueta_img(self, html_creador: str) -> None:
        """CA5: la pagina no contiene ninguna etiqueta <img>."""
        imgs = re.findall(r"<img\b", html_creador, re.IGNORECASE)
        assert len(imgs) == 0, (
            f"La pagina contiene {len(imgs)} etiqueta(s) <img> pero no deberia tener ninguna"
        )

    def test_ca5_sin_texto_resources(self, html_creador: str) -> None:
        """CA5: la pagina no contiene el texto 'Resources'."""
        assert "Resources" not in html_creador, (
            "La pagina contiene el texto 'Resources' pero no deberia"
        )


# ===========================================================================
# CA6: retrato_svg deterministico y unico por cazador
# ===========================================================================


class TestCA6RetratoSVGPuro:
    """CA6: retrato_svg devuelve el mismo texto para el mismo cazador y textos
    distintos para cazadores con id distinto."""

    def test_ca6_retrato_svg_deterministico(self) -> None:
        """CA6: retrato_svg con el mismo cazador devuelve el mismo SVG."""
        from grimcoven_equipos.retratos import retrato_svg

        caz = _cazador("alfa", "Alfa")
        svg1 = retrato_svg(caz)
        svg2 = retrato_svg(caz)
        assert svg1 == svg2, "retrato_svg no es deterministico"

    def test_ca6_retrato_svg_distinto_por_id(self) -> None:
        """CA6: retrato_svg devuelve textos distintos para cazadores con id distinto."""
        from grimcoven_equipos.retratos import retrato_svg

        caz_a = _cazador("alfa", "Alfa")
        caz_b = _cazador("beta", "Beta")
        svg_a = retrato_svg(caz_a)
        svg_b = retrato_svg(caz_b)
        assert svg_a != svg_b, "retrato_svg devuelve lo mismo para cazadores distintos"

    def test_ca6_retrato_svg_devuelve_string(self) -> None:
        """CA6: retrato_svg devuelve una cadena."""
        from grimcoven_equipos.retratos import retrato_svg

        caz = _cazador("gamma", "Gamma")
        svg = retrato_svg(caz)
        assert isinstance(svg, str)
        assert len(svg) > 0, "retrato_svg devuelve cadena vacia"


# ===========================================================================
# CA7: XSS con nombre '<script>alert(1)</script>'
# ===========================================================================


class TestCA7XSSEscaping:
    """CA7: un cazador con nombre '<script>alert(1)</script>' aparece escapado
    en el HTML y no como etiqueta ejecutable."""

    @pytest.fixture(scope="class")
    @classmethod
    def client_xss(cls) -> TestClient:
        """Cliente con catalogo que tiene un cazador con nombre malicioso."""
        catalogo = Catalogo(
            cazadores=(_cazador("xss", "<script>alert(1)</script>"),),
            griefbound=(_griefbound("gb-uno", "Griefbound Uno"),),
        )
        return TestClient(create_app(catalogo=catalogo))

    def test_ca7_no_contiene_script_literal(self, client_xss: TestClient) -> None:
        """CA7: el HTML no contiene '<script>alert(1)' literal."""
        resp = client_xss.get("/creador")
        assert resp.status_code == 200
        assert "<script>alert(1)" not in resp.text, (
            "El HTML contiene '<script>alert(1)' sin escapar"
        )

    def test_ca7_contiene_entidad_escapada(self, client_xss: TestClient) -> None:
        """CA7: el HTML contiene '&lt;script&gt;alert(1)' (escapado)."""
        resp = client_xss.get("/creador")
        assert resp.status_code == 200
        assert "&lt;script&gt;alert(1)" in resp.text, (
            "El HTML no contiene la version escapada del nombre"
        )


# ===========================================================================
# CA8: Catalogo vacio -> sin cartas, mensaje informativo
# ===========================================================================


class TestCA8CatalogoVacio:
    """CA8: con un catalogo sin cazadores, GET /creador responde 200 sin cartas
    y con el mensaje 'No hay cazadores en el catalogo.'."""

    @pytest.fixture(scope="class")
    @classmethod
    def client_vacio(cls) -> TestClient:
        """Cliente con catalogo sin cazadores."""
        catalogo = Catalogo(
            cazadores=(),
            griefbound=(_griefbound("gb-uno", "Griefbound Uno"),),
        )
        return TestClient(create_app(catalogo=catalogo))

    def test_ca8_status_200(self, client_vacio: TestClient) -> None:
        """CA8: responde 200 incluso sin cazadores."""
        resp = client_vacio.get("/creador")
        assert resp.status_code == 200

    def test_ca8_sin_cartas(self, client_vacio: TestClient) -> None:
        """CA8: no hay ninguna carta <article class='card'>."""
        resp = client_vacio.get("/creador")
        cartas = re.findall(
            r"<article[^>]*class=[\"'][^\"']*\bcard\b",
            resp.text,
            re.IGNORECASE,
        )
        assert len(cartas) == 0, f"Se encontraron {len(cartas)} cartas con catalogo vacio"

    def test_ca8_mensaje_no_hay_cazadores(self, client_vacio: TestClient) -> None:
        """CA8: la pagina muestra 'No hay cazadores en el catalogo.'."""
        resp = client_vacio.get("/creador")
        # Buscar el texto, con posible variacion de tilde
        assert "No hay cazadores en el cat" in resp.text, (
            "No se encontro el mensaje 'No hay cazadores en el catalogo.'"
        )


# ===========================================================================
# CA9: Navegacion: enlace 'Creador de equipos' con aria-current='page',
#      boton 'Forjar un aquelarre' con href='/creador',
#      a 800px el boton no es visible (e2e, aqui solo HTML)
# ===========================================================================


class TestCA9Navegacion:
    """CA9: la navegacion en /creador incluye 'Creador de equipos' con
    aria-current='page' y el boton 'Forjar un aquelarre' con href='/creador'."""

    def test_ca9_enlace_creador_en_nav(self, html_creador: str) -> None:
        """CA9: existe un enlace con texto 'Creador de equipos' que apunta a /creador."""
        assert re.search(
            r'<a[^>]*href=["\']\/creador["\'][^>]*>.*?Creador de equipos',
            html_creador,
            re.DOTALL | re.IGNORECASE,
        ) or re.search(
            r"Creador de equipos.*?href=[\"']/creador[\"']",
            html_creador,
            re.DOTALL | re.IGNORECASE,
        ), "No se encontro enlace 'Creador de equipos' con href='/creador'"

    def test_ca9_aria_current_page(self, html_creador: str) -> None:
        """CA9: el enlace de creador tiene aria-current='page'."""
        # Buscar un <a> que contenga href="/creador" y aria-current="page"
        assert re.search(
            r"""<a[^>]*href=[\"']/creador[\"'][^>]*aria-current=[\"']page[\"']""",
            html_creador,
            re.IGNORECASE,
        ) or re.search(
            r"""<a[^>]*aria-current=[\"']page[\"'][^>]*href=[\"']/creador[\"']""",
            html_creador,
            re.IGNORECASE,
        ), "El enlace de /creador no tiene aria-current='page'"

    def test_ca9_boton_forjar_aquelarre(self, html_creador: str) -> None:
        """CA9: existe un boton/enlace 'Forjar un aquelarre' con href='/creador'."""
        assert re.search(
            r"""<a[^>]*href=[\"']/creador[\"'][^>]*>.*?Forjar un aquelarre""",
            html_creador,
            re.DOTALL | re.IGNORECASE,
        ), "No se encontro boton 'Forjar un aquelarre' con href='/creador'"


# ===========================================================================
# CA10: openapi.json incluye /creador solo con GET; suite y lint pasan
# ===========================================================================


class TestCA10OpenAPI:
    """CA10: /openapi.json incluye /creador solo con el metodo get."""

    def test_ca10_openapi_incluye_creador(self, client: TestClient) -> None:
        """CA10: /openapi.json contiene la ruta /creador."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = set(resp.json()["paths"].keys())
        assert "/creador" in paths, f"/creador no esta en las rutas: {paths}"

    def test_ca10_creador_solo_get(self, client: TestClient) -> None:
        """CA10: /creador solo tiene el metodo 'get' en openapi.json."""
        resp = client.get("/openapi.json")
        metodos = resp.json()["paths"]["/creador"]
        assert set(metodos.keys()) == {"get"}, (
            f"/creador deberia tener solo 'get', tiene {set(metodos.keys())}"
        )


# ===========================================================================
# Casos limite adicionales
# ===========================================================================


class TestEdgeCases:
    """Casos limite no cubiertos directamente por los CAs."""

    def test_edge_pagina_extiende_base_html(self, client: TestClient) -> None:
        """Caso limite: la pagina del creador usa la plantilla base."""
        resp = client.get("/creador")
        assert resp.status_code == 200
        texto = resp.text.lower()
        assert "no oficial" in texto, "La pagina no hereda de base.html"

    def test_edge_enlaza_tema_css(self, client: TestClient) -> None:
        """Caso limite: la pagina enlaza /static/css/tema.css."""
        resp = client.get("/creador")
        assert "/static/css/tema.css" in resp.text

    def test_edge_html_lang_es(self, client: TestClient) -> None:
        """Caso limite: la pagina tiene <html lang='es'>."""
        resp = client.get("/creador")
        assert '<html lang="es">' in resp.text or "<html lang='es'>" in resp.text

    def test_edge_sin_estilos_en_linea(self, html_creador: str) -> None:
        """Caso limite: no hay atributos style= en el HTML de la pagina."""
        estilos_inline = re.findall(r'\bstyle\s*=\s*["\']', html_creador, re.IGNORECASE)
        assert len(estilos_inline) == 0, (
            f"Se encontraron {len(estilos_inline)} estilos en linea"
        )

    def test_edge_meta_row_texto(self, html_creador: str) -> None:
        """Caso limite: la pagina contiene el texto del meta-row."""
        # Notas tecnicas: 'Retratos ilustrativos . roles y contrarrestas inferidos del reglamento'
        assert "Retratos ilustrativos" in html_creador
        assert "inferidos del reglamento" in html_creador.lower()

    def test_edge_plantilla_creador_extiende_base(self) -> None:
        """Caso limite: creador.html contiene {% extends 'base.html' %}."""
        from pathlib import Path

        ruta = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "grimcoven_equipos"
            / "templates"
            / "creador.html"
        )
        assert ruta.exists(), f"No existe la plantilla {ruta}"
        contenido = ruta.read_text(encoding="utf-8")
        assert re.search(r"\{%\s*extends\s+['\"]base\.html['\"]\s*%\}", contenido), (
            "creador.html no extiende base.html"
        )

    def test_edge_plantilla_carta_existe(self) -> None:
        """Caso limite: existe la plantilla _carta.html."""
        from pathlib import Path

        ruta = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "grimcoven_equipos"
            / "templates"
            / "_carta.html"
        )
        assert ruta.exists(), f"No existe la plantilla {ruta}"

    def test_edge_no_contiene_placeholder_ni_not_official(self, html_creador: str) -> None:
        """Caso limite (notas tecnicas): el HTML no contiene 'Placeholder' ni
        'not official game data'."""
        assert "Placeholder" not in html_creador
        assert "not official game data" not in html_creador.lower()

    def test_edge_todas_las_cartas_muestran_nombre(self, html_creador: str) -> None:
        """Caso limite: cada carta muestra el nombre del cazador."""
        nombres_esperados = {
            "clockwork-giant": "Clockwork Giant",
            "death-jester": "Death Jester",
            "duality": "Duality",
            "gunslinger": "Gunslinger",
            "keeper": "Keeper",
            "mannequin": "Mannequin",
            "technomancer": "Technomancer",
            "twins": "Twins",
        }
        for cid, nombre in nombres_esperados.items():
            carta = _extraer_carta(html_creador, cid)
            assert carta is not None, f"No se encontro la carta de {cid}"
            assert nombre in carta, f"La carta de {cid} no contiene el nombre '{nombre}'"

    def test_edge_etiquetas_roles_en_espanol(self, html_creador: str) -> None:
        """Caso limite (notas tecnicas): las etiquetas de roles son Tanque, Dano, Apoyo, Control."""
        for etiqueta in ["Tanque", "Apoyo", "Control"]:
            assert etiqueta in html_creador, (
                f"No se encontro la etiqueta de rol '{etiqueta}' en la pagina"
            )
        # Dano puede ser 'Dano' o 'Daño'
        assert re.search(r"Da[nñ]o", html_creador), (
            "No se encontro la etiqueta de rol 'Dano' en la pagina"
        )

    def test_edge_api_sigue_funcionando(self, client: TestClient) -> None:
        """Caso limite: los endpoints de la API siguen respondiendo correctamente."""
        resp = client.get("/api/cazadores")
        assert resp.status_code == 200
        resp2 = client.get("/api/equipos/aleatorio", params={"tamano": 3, "semilla": 1})
        assert resp2.status_code == 200

    def test_edge_modulo_retratos_existe(self) -> None:
        """Caso limite: el modulo grimcoven_equipos.retratos existe."""
        import importlib

        mod = importlib.import_module("grimcoven_equipos.retratos")
        assert hasattr(mod, "retrato_svg")


# ===========================================================================
# Tests e2e (CA9 parcial): boton 'Forjar un aquelarre' no visible a 800px
# -> Movido a tests/e2e/test_creador_e2e.py para evitar conflicto entre
#    Playwright Sync API y el event loop de asyncio que crea TestClient.
# ===========================================================================
