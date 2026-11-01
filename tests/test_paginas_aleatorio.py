"""Tests de US-006: Pagina web del selector aleatorio de equipos.

Cada test indica el criterio de aceptacion (CA<n>) que cubre.
Se usa fastapi.testclient.TestClient (basado en httpx) sin levantar servidor.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from grimcoven_equipos.app import create_app
from grimcoven_equipos.catalogo import Catalogo, Cazador, Fuente, Griefbound

# ---------------------------------------------------------------------------
# Datos de prueba
# ---------------------------------------------------------------------------

FICHERO_REGLAS = "GC_Rulebook_280x280mm_bleed3mm [36 pages]_[lowres]_compressed.pdf"


def _cazador(id_: str, nombre: str, roles: list[str] | None = None) -> Cazador:
    """Fabrica auxiliar de cazadores de prueba."""
    return Cazador(
        id=id_,
        nombre=nombre,
        expansion="base",
        complejidad="baja",
        roles=roles or ["dano"],
        contrarresta=[],
        vida=5,
        movimiento=3,
        fuente=Fuente(fichero=FICHERO_REGLAS, pagina=1),
    )


def _griefbound(id_: str, nombre: str) -> Griefbound:
    return Griefbound(
        id=id_,
        nombre=nombre,
        tipo="griefbound",
        expansion="base",
        amenazas=["prueba"],
        fuente=Fuente(fichero=FICHERO_REGLAS, pagina=2),
    )


# Catalogo con 6 cazadores (suficientes para tamano 2-5, insuficientes para 7)
CAZADORES_PRUEBA = (
    _cazador("alfa", "Alfa", ["tanque", "apoyo"]),
    _cazador("beta", "Beta", ["dano"]),
    _cazador("gamma", "Gamma", ["control", "dano"]),
    _cazador("delta", "Delta", ["apoyo"]),
    _cazador("epsilon", "Epsilon", ["tanque"]),
    _cazador("zeta", "Zeta", ["dano", "control"]),
)

GRIEFBOUND_PRUEBA = (_griefbound("gb-uno", "Griefbound Uno"),)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def catalogo_prueba() -> Catalogo:
    """Catalogo inyectable con 6 cazadores y 1 Griefbound."""
    return Catalogo(cazadores=CAZADORES_PRUEBA, griefbound=GRIEFBOUND_PRUEBA)


@pytest.fixture(scope="module")
def app(catalogo_prueba: Catalogo):
    """App con catalogo de prueba inyectado."""
    return create_app(catalogo=catalogo_prueba)


@pytest.fixture(scope="module")
def client(app) -> TestClient:
    """Cliente HTTP sincrono sobre la app de prueba."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Fixture auxiliar: respuesta de la API JSON para comparar con la pagina HTML
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_aleatorio_3_42(client: TestClient) -> dict:
    """Respuesta JSON de GET /api/equipos/aleatorio?tamano=3&semilla=42."""
    resp = client.get("/api/equipos/aleatorio", params={"tamano": 3, "semilla": 42})
    assert resp.status_code == 200, f"La API fallo: {resp.status_code}"
    return resp.json()


# ---------------------------------------------------------------------------
# CA1: GET /aleatorio -> 200, formulario GET, select tamano con 4 opciones,
#      boton 'Invocar equipo'
# ---------------------------------------------------------------------------


class TestCA1FormularioAleatorio:
    """CA1: la pagina /aleatorio muestra el formulario de seleccion."""

    def test_ca1_get_aleatorio_status_200(self, client: TestClient) -> None:
        """CA1: GET /aleatorio responde 200."""
        resp = client.get("/aleatorio")
        assert resp.status_code == 200

    def test_ca1_content_type_html(self, client: TestClient) -> None:
        """CA1: GET /aleatorio responde con content-type text/html."""
        resp = client.get("/aleatorio")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_ca1_formulario_get(self, client: TestClient) -> None:
        """CA1: la pagina contiene un <form method='get'>."""
        resp = client.get("/aleatorio")
        html = resp.text.lower()
        # El form debe tener method=get (explicito o implicito -- pero pedimos explicito)
        assert "<form" in html
        assert 'method="get"' in html or "method='get'" in html

    def test_ca1_select_name_tamano(self, client: TestClient) -> None:
        """CA1: el formulario contiene un <select name='tamano'>."""
        resp = client.get("/aleatorio")
        html = resp.text
        assert re.search(r'<select[^>]*name=["\']tamano["\']', html, re.IGNORECASE), (
            "No se encontro <select name='tamano'>"
        )

    def test_ca1_select_tiene_4_opciones(self, client: TestClient) -> None:
        """CA1: el select tamano tiene exactamente 4 opciones (2, 3, 4, 5)."""
        resp = client.get("/aleatorio")
        html = resp.text
        # Extraer el bloque <select name="tamano">...</select>
        select_match = re.search(
            r'<select[^>]*name=["\']tamano["\'][^>]*>(.*?)</select>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        assert select_match is not None, "No se encontro <select name='tamano'>...</select>"
        select_body = select_match.group(1)
        opciones = re.findall(r'<option[^>]*value=["\'](\d+)["\']', select_body, re.IGNORECASE)
        assert opciones == ["2", "3", "4", "5"], (
            f"Las opciones del select deben ser [2, 3, 4, 5], se encontraron {opciones}"
        )

    def test_ca1_boton_invocar_equipo(self, client: TestClient) -> None:
        """CA1: hay un boton de envio con el texto 'Invocar equipo'."""
        resp = client.get("/aleatorio")
        html = resp.text
        # Puede ser <button type="submit">Invocar equipo</button>
        # o <input type="submit" value="Invocar equipo">
        tiene_button = re.search(
            r"<button[^>]*type=[\"']submit[\"'][^>]*>\s*Invocar equipo\s*</button>",
            html,
            re.IGNORECASE,
        )
        tiene_input = re.search(
            r"<input[^>]*type=[\"']submit[\"'][^>]*value=[\"']Invocar equipo[\"']",
            html,
            re.IGNORECASE,
        )
        assert tiene_button or tiene_input, (
            "No se encontro un boton de envio con el texto 'Invocar equipo'"
        )


# ---------------------------------------------------------------------------
# CA2: GET /aleatorio?tamano=3&semilla=42 -> 3 cartas .carta-cazador con
#      nombre y roles, en el mismo orden que la API
# ---------------------------------------------------------------------------


class TestCA2CartasCazador:
    """CA2: la pagina muestra cartas de cazadores con nombre y roles."""

    def test_ca2_tres_cartas_cazador(self, client: TestClient) -> None:
        """CA2: con tamano=3&semilla=42, la pagina contiene 3 elementos .carta-cazador."""
        resp = client.get("/aleatorio", params={"tamano": 3, "semilla": 42})
        assert resp.status_code == 200
        cartas = re.findall(r'class=["\'][^"\']*\bcarta-cazador\b', resp.text, re.IGNORECASE)
        assert len(cartas) == 3, (
            f"Se esperaban 3 cartas .carta-cazador, se encontraron {len(cartas)}"
        )

    def test_ca2_nombres_coinciden_con_api(
        self, client: TestClient, api_aleatorio_3_42: dict
    ) -> None:
        """CA2: los nombres de las cartas coinciden con los de la API, en orden."""
        nombres_api = [c["nombre"] for c in api_aleatorio_3_42["cazadores"]]

        resp = client.get("/aleatorio", params={"tamano": 3, "semilla": 42})
        html = resp.text

        for nombre in nombres_api:
            assert nombre in html, f"El nombre '{nombre}' no aparece en la pagina"

        # Extraer los nombres de .nombre-cazador en orden de aparicion en el HTML
        nombres_html = re.findall(
            r'class=["\'][^"\']*\bnombre-cazador\b[^"\']*["\'][^>]*>([^<]+)<',
            html,
            re.IGNORECASE,
        )
        # Normalizar espacios en blanco
        nombres_html = [n.strip() for n in nombres_html]
        assert nombres_html == nombres_api, (
            f"Los nombres no coinciden en orden. API: {nombres_api}, HTML: {nombres_html}"
        )

    def test_ca2_roles_presentes_en_cartas(
        self, client: TestClient, api_aleatorio_3_42: dict
    ) -> None:
        """CA2: cada carta muestra los roles del cazador."""
        resp = client.get("/aleatorio", params={"tamano": 3, "semilla": 42})
        html = resp.text
        for cazador in api_aleatorio_3_42["cazadores"]:
            for rol in cazador["roles"]:
                assert rol in html, (
                    f"El rol '{rol}' del cazador '{cazador['nombre']}' no aparece en la pagina"
                )


# ---------------------------------------------------------------------------
# CA3: resultado con tamano=4 -> enlace 'Volver a tirar' a /aleatorio?tamano=4
#      (sin semilla) y opcion 4 selected
# ---------------------------------------------------------------------------


class TestCA3VolverATirar:
    """CA3: boton/enlace 'Volver a tirar' y opcion tamano seleccionada."""

    def test_ca3_enlace_volver_a_tirar_presente(self, client: TestClient) -> None:
        """CA3: con tamano=4&semilla=1, existe un enlace/boton 'Volver a tirar'."""
        resp = client.get("/aleatorio", params={"tamano": 4, "semilla": 1})
        assert resp.status_code == 200
        html = resp.text
        assert "Volver a tirar" in html, "No se encontro 'Volver a tirar' en la pagina"

    def test_ca3_enlace_volver_a_tirar_url_correcta(self, client: TestClient) -> None:
        """CA3: el enlace 'Volver a tirar' apunta a /aleatorio?tamano=4 sin semilla."""
        resp = client.get("/aleatorio", params={"tamano": 4, "semilla": 1})
        html = resp.text
        # Buscar cualquier <a> que contenga "Volver a tirar" y extraer su href
        enlace_match = re.search(
            r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>[^<]*Volver a tirar',
            html,
            re.IGNORECASE,
        )
        assert enlace_match is not None, "No se encontro enlace con 'Volver a tirar'"
        url = enlace_match.group(1)
        assert "/aleatorio" in url, f"La URL no contiene /aleatorio: {url}"
        assert "tamano=4" in url, f"La URL no contiene tamano=4: {url}"
        assert "semilla" not in url, f"La URL no debe contener semilla: {url}"

    def test_ca3_opcion_4_selected(self, client: TestClient) -> None:
        """CA3: en el select, la opcion 4 aparece como selected."""
        resp = client.get("/aleatorio", params={"tamano": 4, "semilla": 1})
        html = resp.text
        # Buscar <option value="4" selected> o <option selected value="4">
        opcion_4_selected = re.search(
            r'<option[^>]*value=["\']4["\'][^>]*selected[^>]*>',
            html,
            re.IGNORECASE,
        )
        if not opcion_4_selected:
            opcion_4_selected = re.search(
                r'<option[^>]*selected[^>]*value=["\']4["\'][^>]*>',
                html,
                re.IGNORECASE,
            )
        assert opcion_4_selected is not None, (
            "La opcion 4 del select no tiene el atributo 'selected'"
        )

    def test_ca3_opcion_3_no_selected_cuando_tamano_4(self, client: TestClient) -> None:
        """CA3 (caso limite): con tamano=4, la opcion 3 NO esta seleccionada."""
        resp = client.get("/aleatorio", params={"tamano": 4, "semilla": 1})
        html = resp.text
        # Comprobar que la opcion 3 no tiene selected
        opcion_3_selected = re.search(
            r'<option[^>]*value=["\']3["\'][^>]*selected',
            html,
            re.IGNORECASE,
        )
        assert opcion_3_selected is None, "La opcion 3 no deberia tener 'selected' con tamano=4"


# ---------------------------------------------------------------------------
# CA4: GET /aleatorio?tamano=7 -> 200, mensaje de error, sin cartas
# ---------------------------------------------------------------------------


class TestCA4TamanoInvalido:
    """CA4: tamano fuera de rango muestra error sin cartas."""

    def test_ca4_tamano_7_status_200(self, client: TestClient) -> None:
        """CA4: GET /aleatorio?tamano=7 responde 200 (no 4xx)."""
        resp = client.get("/aleatorio", params={"tamano": 7})
        assert resp.status_code == 200

    def test_ca4_tamano_7_mensaje_error(self, client: TestClient) -> None:
        """CA4: con tamano=7, la pagina muestra el mensaje de error esperado."""
        resp = client.get("/aleatorio", params={"tamano": 7})
        assert "El equipo debe tener entre 2 y 5 cazadores." in resp.text

    def test_ca4_tamano_7_sin_cartas(self, client: TestClient) -> None:
        """CA4: con tamano=7, no hay elementos .carta-cazador."""
        resp = client.get("/aleatorio", params={"tamano": 7})
        cartas = re.findall(r'class=["\'][^"\']*\bcarta-cazador\b', resp.text, re.IGNORECASE)
        assert len(cartas) == 0, f"Se encontraron {len(cartas)} cartas con tamano invalido"

    def test_ca4_tamano_1_mensaje_error(self, client: TestClient) -> None:
        """CA4 (caso limite): tamano=1 tambien muestra el mensaje de error."""
        resp = client.get("/aleatorio", params={"tamano": 1})
        assert resp.status_code == 200
        assert "El equipo debe tener entre 2 y 5 cazadores." in resp.text

    def test_ca4_tamano_0_mensaje_error(self, client: TestClient) -> None:
        """CA4 (caso limite): tamano=0 muestra error."""
        resp = client.get("/aleatorio", params={"tamano": 0})
        assert resp.status_code == 200
        assert "El equipo debe tener entre 2 y 5 cazadores." in resp.text

    def test_ca4_tamano_negativo(self, client: TestClient) -> None:
        """CA4 (caso limite): tamano=-1 muestra error."""
        resp = client.get("/aleatorio", params={"tamano": -1})
        assert resp.status_code == 200
        assert "El equipo debe tener entre 2 y 5 cazadores." in resp.text
        cartas = re.findall(r'class=["\'][^"\']*\bcarta-cazador\b', resp.text, re.IGNORECASE)
        assert len(cartas) == 0


# ---------------------------------------------------------------------------
# CA5: aleatorio.html extiende base.html, usa clases de tema.css, sin
#      estilos en linea
# ---------------------------------------------------------------------------


class TestCA5PlantillaYTema:
    """CA5: la pagina extiende base.html, usa tema.css, sin estilos inline."""

    def test_ca5_enlaza_tema_css(self, client: TestClient) -> None:
        """CA5: la pagina enlaza /static/css/tema.css (heredado de base.html)."""
        resp = client.get("/aleatorio")
        assert "/static/css/tema.css" in resp.text

    def test_ca5_hereda_pie_legal_de_base(self, client: TestClient) -> None:
        """CA5: la pagina incluye el pie legal de base.html."""
        resp = client.get("/aleatorio")
        texto = resp.text.lower()
        assert "no oficial" in texto
        assert "grimcoven pertenece a sus respectivos" in texto

    def test_ca5_html_lang_es(self, client: TestClient) -> None:
        """CA5: la pagina tiene <html lang='es'> (heredado de base.html)."""
        resp = client.get("/aleatorio")
        assert '<html lang="es">' in resp.text or "<html lang='es'>" in resp.text

    def test_ca5_sin_estilos_en_linea(self, client: TestClient) -> None:
        """CA5: no hay atributos style= en el HTML de la pagina."""
        resp = client.get("/aleatorio")
        # Buscar style="..." o style='...' en cualquier etiqueta
        estilos_inline = re.findall(r'\bstyle\s*=\s*["\']', resp.text, re.IGNORECASE)
        assert len(estilos_inline) == 0, (
            f"Se encontraron {len(estilos_inline)} estilos en linea"
        )

    def test_ca5_sin_estilos_en_linea_con_resultado(self, client: TestClient) -> None:
        """CA5: tampoco hay estilos inline cuando se muestran cartas."""
        resp = client.get("/aleatorio", params={"tamano": 3, "semilla": 1})
        estilos_inline = re.findall(r'\bstyle\s*=\s*["\']', resp.text, re.IGNORECASE)
        assert len(estilos_inline) == 0, (
            f"Se encontraron {len(estilos_inline)} estilos en linea con resultado"
        )

    def test_ca5_plantilla_aleatorio_extiende_base(self) -> None:
        """CA5: aleatorio.html contiene {% extends 'base.html' %}."""
        from pathlib import Path

        ruta = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "grimcoven_equipos"
            / "templates"
            / "aleatorio.html"
        )
        assert ruta.exists(), f"No existe la plantilla {ruta}"
        contenido = ruta.read_text(encoding="utf-8")
        assert re.search(r"\{%\s*extends\s+['\"]base\.html['\"]\s*%\}", contenido), (
            "aleatorio.html no extiende base.html"
        )

    def test_ca5_clases_definidas_en_tema_css(self) -> None:
        """CA5: las clases usadas en aleatorio.html estan definidas en tema.css."""
        from pathlib import Path

        ruta_css = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "grimcoven_equipos"
            / "static"
            / "css"
            / "tema.css"
        )
        assert ruta_css.exists(), f"No existe tema.css en {ruta_css}"
        css = ruta_css.read_text(encoding="utf-8")
        clases_requeridas = [
            "carta-cazador",
            "nombre-cazador",
            "roles-cazador",
            "equipo",
            "mensaje-error",
            "boton-secundario",
        ]
        for clase in clases_requeridas:
            assert re.search(rf"\.{clase}\b", css), (
                f"La clase '.{clase}' no esta definida en tema.css"
            )

    def test_ca5_error_tiene_role_alert(self, client: TestClient) -> None:
        """CA5: el mensaje de error tiene role='alert' (WCAG 4.1.3)."""
        resp = client.get("/aleatorio", params={"tamano": 7})
        assert 'role="alert"' in resp.text or "role='alert'" in resp.text

    def test_ca5_focus_visible_en_tema_css(self) -> None:
        """CA5: tema.css define :focus-visible para button y select."""
        from pathlib import Path

        ruta_css = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "grimcoven_equipos"
            / "static"
            / "css"
            / "tema.css"
        )
        css = ruta_css.read_text(encoding="utf-8")
        assert re.search(r"button:focus-visible", css), (
            "tema.css no define button:focus-visible"
        )
        assert re.search(r"select:focus-visible", css), (
            "tema.css no define select:focus-visible"
        )


# ---------------------------------------------------------------------------
# Casos limite adicionales
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Casos limite que complementan los criterios de aceptacion."""

    def test_edge_tamano_2_funciona(self, client: TestClient) -> None:
        """Caso limite: tamano=2 (minimo valido) genera 2 cartas."""
        resp = client.get("/aleatorio", params={"tamano": 2, "semilla": 99})
        assert resp.status_code == 200
        cartas = re.findall(r'class=["\'][^"\']*\bcarta-cazador\b', resp.text, re.IGNORECASE)
        assert len(cartas) == 2

    def test_edge_tamano_5_funciona(self, client: TestClient) -> None:
        """Caso limite: tamano=5 (maximo valido) genera 5 cartas."""
        resp = client.get("/aleatorio", params={"tamano": 5, "semilla": 99})
        assert resp.status_code == 200
        cartas = re.findall(r'class=["\'][^"\']*\bcarta-cazador\b', resp.text, re.IGNORECASE)
        assert len(cartas) == 5

    def test_edge_semilla_0_funciona(self, client: TestClient) -> None:
        """Caso limite (MEMORY): semilla=0 (falsy) no se trata como None."""
        resp = client.get("/aleatorio", params={"tamano": 3, "semilla": 0})
        assert resp.status_code == 200
        cartas = re.findall(r'class=["\'][^"\']*\bcarta-cazador\b', resp.text, re.IGNORECASE)
        assert len(cartas) == 3

    def test_edge_sin_semilla_funciona(self, client: TestClient) -> None:
        """Caso limite: sin semilla, la pagina genera un equipo (aleatorio real)."""
        resp = client.get("/aleatorio", params={"tamano": 3})
        assert resp.status_code == 200
        cartas = re.findall(r'class=["\'][^"\']*\bcarta-cazador\b', resp.text, re.IGNORECASE)
        assert len(cartas) == 3

    def test_edge_sin_parametros_no_muestra_cartas(self, client: TestClient) -> None:
        """Caso limite: GET /aleatorio sin parametros muestra el formulario sin cartas."""
        resp = client.get("/aleatorio")
        assert resp.status_code == 200
        cartas = re.findall(r'class=["\'][^"\']*\bcarta-cazador\b', resp.text, re.IGNORECASE)
        assert len(cartas) == 0

    def test_edge_semilla_reproductible(self, client: TestClient) -> None:
        """Caso limite: la misma semilla produce el mismo resultado dos veces."""
        resp1 = client.get("/aleatorio", params={"tamano": 3, "semilla": 77})
        resp2 = client.get("/aleatorio", params={"tamano": 3, "semilla": 77})
        assert resp1.text == resp2.text

    def test_edge_opcion_2_selected_con_tamano_2(self, client: TestClient) -> None:
        """Caso limite: con tamano=2, la opcion 2 del select aparece como selected."""
        resp = client.get("/aleatorio", params={"tamano": 2, "semilla": 1})
        html = resp.text
        opcion_2_selected = re.search(
            r'<option[^>]*value=["\']2["\'][^>]*selected',
            html,
            re.IGNORECASE,
        ) or re.search(
            r'<option[^>]*selected[^>]*value=["\']2["\']',
            html,
            re.IGNORECASE,
        )
        assert opcion_2_selected is not None, (
            "La opcion 2 deberia tener 'selected' con tamano=2"
        )

    def test_edge_tamano_no_entero_devuelve_422(self, client: TestClient) -> None:
        """Caso limite: tamano=abc (no entero) devuelve 422 de FastAPI."""
        resp = client.get("/aleatorio", params={"tamano": "abc"})
        assert resp.status_code == 422

    def test_edge_api_sigue_funcionando(self, client: TestClient) -> None:
        """Caso limite: los endpoints de la API siguen respondiendo correctamente."""
        resp = client.get("/api/equipos/aleatorio", params={"tamano": 3, "semilla": 1})
        assert resp.status_code == 200
        resp2 = client.get("/api/cazadores")
        assert resp2.status_code == 200

    def test_edge_catalogo_insuficiente_mensaje_distinto(self) -> None:
        """Caso limite: catalogo con 1 cazador y tamano=2 muestra mensaje de catalogo
        insuficiente, distinto al mensaje de rango invalido."""
        catalogo_pequeno = Catalogo(
            cazadores=(_cazador("unico", "Unico"),),
            griefbound=GRIEFBOUND_PRUEBA,
        )
        app_pequena = create_app(catalogo=catalogo_pequeno)
        client_pequeno = TestClient(app_pequena)
        resp = client_pequeno.get("/aleatorio", params={"tamano": 2, "semilla": 1})
        assert resp.status_code == 200
        # El mensaje debe referirse al catalogo, no al rango
        assert "catalogo" in resp.text.lower(), (
            "El mensaje de error debe mencionar el catalogo insuficiente"
        )
        # No debe mostrar el mensaje de rango invalido
        assert "El equipo debe tener entre 2 y 5 cazadores." not in resp.text
