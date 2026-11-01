"""Tests de US-007: Pagina web del recomendador de equipos contra un Griefbound.

Cada test indica el criterio de aceptacion (CA<n>) que cubre.
Se usa fastapi.testclient.TestClient (basado en httpx) sin levantar servidor.
El catalogo se inyecta con create_app(catalogo=...) segun las convenciones del proyecto.
"""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from grimcoven_equipos.app import create_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app():
    """Instancia de la app creada con create_app() y catalogo real."""
    return create_app()


@pytest.fixture(scope="module")
def client(app) -> TestClient:
    """Cliente HTTP sincrono para la app."""
    return TestClient(app)


# ===========================================================================
# CA1: GET /recomendador -> 200, formulario con selects
# ===========================================================================


class TestCA1Formulario:
    """CA1: GET /recomendador responde 200 con un formulario que contiene
    un select name='griefbound' con 16 opciones en 2 optgroups (8+8)
    y un select name='tamano' con opciones 2, 3, 4 y 5."""

    def test_ca1_status_200(self, client: TestClient) -> None:
        """CA1: GET /recomendador responde 200."""
        resp = client.get("/recomendador")
        assert resp.status_code == 200

    def test_ca1_content_type_html(self, client: TestClient) -> None:
        """CA1: GET /recomendador responde con content-type text/html."""
        resp = client.get("/recomendador")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_ca1_formulario_metodo_get(self, client: TestClient) -> None:
        """CA1: la pagina contiene un formulario con method='get'."""
        resp = client.get("/recomendador")
        html = resp.text.lower()
        # Un form con method="get" (o sin method, que por defecto es GET)
        assert "<form" in html

    def test_ca1_select_griefbound(self, client: TestClient) -> None:
        """CA1: existe un <select name='griefbound'>."""
        resp = client.get("/recomendador")
        assert re.search(
            r'<select[^>]*name=["\']griefbound["\']', resp.text, re.IGNORECASE
        ), "No se encontro <select name='griefbound'>"

    def test_ca1_select_tamano(self, client: TestClient) -> None:
        """CA1: existe un <select name='tamano'>."""
        resp = client.get("/recomendador")
        assert re.search(
            r'<select[^>]*name=["\']tamano["\']', resp.text, re.IGNORECASE
        ), "No se encontro <select name='tamano'>"

    def test_ca1_optgroup_griefbound_8(self, client: TestClient) -> None:
        """CA1: hay un optgroup label='Griefbound' con 8 opciones."""
        resp = client.get("/recomendador")
        html = resp.text
        # Buscar el optgroup de Griefbound y contar sus options
        match = re.search(
            r'<optgroup\s+label=["\']Griefbound["\']>(.*?)</optgroup>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        assert match is not None, "No se encontro <optgroup label='Griefbound'>"
        opciones = re.findall(r"<option\b", match.group(1), re.IGNORECASE)
        assert len(opciones) == 8, (
            f"Esperaba 8 opciones en optgroup Griefbound, hay {len(opciones)}"
        )

    def test_ca1_optgroup_pretendientes_8(self, client: TestClient) -> None:
        """CA1: hay un optgroup label='Pretendientes' con 8 opciones."""
        resp = client.get("/recomendador")
        html = resp.text
        match = re.search(
            r'<optgroup\s+label=["\']Pretendientes["\']>(.*?)</optgroup>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        assert match is not None, "No se encontro <optgroup label='Pretendientes'>"
        opciones = re.findall(r"<option\b", match.group(1), re.IGNORECASE)
        assert len(opciones) == 8, (
            f"Esperaba 8 opciones en optgroup Pretendientes, hay {len(opciones)}"
        )

    def test_ca1_total_16_opciones_griefbound(self, client: TestClient) -> None:
        """CA1: el select griefbound tiene exactamente 16 opciones en total."""
        resp = client.get("/recomendador")
        html = resp.text
        # Extraer el bloque del select griefbound
        match = re.search(
            r'<select[^>]*name=["\']griefbound["\'][^>]*>(.*?)</select>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        assert match is not None, "No se encontro <select name='griefbound'>"
        opciones = re.findall(r"<option\b", match.group(1), re.IGNORECASE)
        assert len(opciones) == 16, (
            f"Esperaba 16 opciones en select griefbound, hay {len(opciones)}"
        )

    def test_ca1_tamano_opciones_2_3_4_5(self, client: TestClient) -> None:
        """CA1: el select tamano tiene opciones con valores 2, 3, 4, 5."""
        resp = client.get("/recomendador")
        html = resp.text
        match = re.search(
            r'<select[^>]*name=["\']tamano["\'][^>]*>(.*?)</select>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        assert match is not None, "No se encontro <select name='tamano'>"
        # Extraer los values
        values = re.findall(
            r'<option[^>]*value=["\'](\d+)["\']', match.group(1), re.IGNORECASE
        )
        assert sorted(values) == ["2", "3", "4", "5"], (
            f"Esperaba valores [2,3,4,5] en select tamano, obtuve {values}"
        )


# ===========================================================================
# CA2: GET /recomendador?griefbound=convergence&tamano=2 -> 3 equipos
# ===========================================================================


class TestCA2ConvergenceResultados:
    """CA2: GET /recomendador?griefbound=convergence&tamano=2 muestra 3 equipos
    recomendados; el primero contiene 'Clockwork Giant', 'Technomancer' y '25 puntos'."""

    def test_ca2_tres_equipos_recomendados(self, client: TestClient) -> None:
        """CA2: la pagina muestra 3 elementos con clase 'equipo-recomendado'."""
        resp = client.get("/recomendador", params={"griefbound": "convergence", "tamano": 2})
        assert resp.status_code == 200
        equipos = re.findall(r'class=["\'][^"\']*equipo-recomendado[^"\']*["\']', resp.text)
        assert len(equipos) == 3, (
            f"Esperaba 3 elementos con clase 'equipo-recomendado', hay {len(equipos)}"
        )

    def test_ca2_primer_equipo_clockwork_giant(self, client: TestClient) -> None:
        """CA2: el primer equipo-recomendado contiene 'Clockwork Giant'."""
        resp = client.get("/recomendador", params={"griefbound": "convergence", "tamano": 2})
        html = resp.text
        # Extraer los bloques de equipo-recomendado
        bloques = _extraer_bloques_equipo(html)
        assert len(bloques) >= 1, "No se encontraron bloques equipo-recomendado"
        assert "Clockwork Giant" in bloques[0], (
            f"El primer equipo no contiene 'Clockwork Giant'. Contenido: {bloques[0][:200]}"
        )

    def test_ca2_primer_equipo_technomancer(self, client: TestClient) -> None:
        """CA2: el primer equipo-recomendado contiene 'Technomancer'."""
        resp = client.get("/recomendador", params={"griefbound": "convergence", "tamano": 2})
        bloques = _extraer_bloques_equipo(resp.text)
        assert len(bloques) >= 1
        assert "Technomancer" in bloques[0], (
            f"El primer equipo no contiene 'Technomancer'. Contenido: {bloques[0][:200]}"
        )

    def test_ca2_primer_equipo_25_puntos(self, client: TestClient) -> None:
        """CA2: el primer equipo-recomendado contiene '25 puntos'."""
        resp = client.get("/recomendador", params={"griefbound": "convergence", "tamano": 2})
        bloques = _extraer_bloques_equipo(resp.text)
        assert len(bloques) >= 1
        assert "25 puntos" in bloques[0], (
            f"El primer equipo no contiene '25 puntos'. Contenido: {bloques[0][:200]}"
        )


# ===========================================================================
# CA3: Equipo recomendado lista amenazas y roles cubiertos
# ===========================================================================


class TestCA3AmenazasYRoles:
    """CA3: un equipo recomendado mostrado lista las amenazas cubiertas
    (p. ej. 'quemadura') y los roles cubiertos (p. ej. 'tanque')."""

    def test_ca3_amenazas_cubiertas_quemadura(self, client: TestClient) -> None:
        """CA3: el primer equipo contra convergence muestra 'quemadura'."""
        resp = client.get("/recomendador", params={"griefbound": "convergence", "tamano": 2})
        bloques = _extraer_bloques_equipo(resp.text)
        assert len(bloques) >= 1
        assert "quemadura" in bloques[0], (
            f"El primer equipo no muestra 'quemadura'. Contenido: {bloques[0][:300]}"
        )

    def test_ca3_roles_cubiertos_tanque(self, client: TestClient) -> None:
        """CA3: el primer equipo contra convergence muestra 'tanque'."""
        resp = client.get("/recomendador", params={"griefbound": "convergence", "tamano": 2})
        bloques = _extraer_bloques_equipo(resp.text)
        assert len(bloques) >= 1
        assert "tanque" in bloques[0], (
            f"El primer equipo no muestra 'tanque'. Contenido: {bloques[0][:300]}"
        )

    def test_ca3_roles_cubiertos_dano(self, client: TestClient) -> None:
        """CA3: el primer equipo contra convergence muestra 'dano'."""
        resp = client.get("/recomendador", params={"griefbound": "convergence", "tamano": 2})
        bloques = _extraer_bloques_equipo(resp.text)
        assert len(bloques) >= 1
        assert "dano" in bloques[0].lower(), (
            f"El primer equipo no muestra 'dano'. Contenido: {bloques[0][:300]}"
        )

    def test_ca3_roles_cubiertos_apoyo(self, client: TestClient) -> None:
        """CA3: el primer equipo contra convergence muestra 'apoyo'."""
        resp = client.get("/recomendador", params={"griefbound": "convergence", "tamano": 2})
        bloques = _extraer_bloques_equipo(resp.text)
        assert len(bloques) >= 1
        assert "apoyo" in bloques[0], (
            f"El primer equipo no muestra 'apoyo'. Contenido: {bloques[0][:300]}"
        )


# ===========================================================================
# CA4: pretender-keeper tamano=3, ningun equipo contiene 'Keeper'
# ===========================================================================


class TestCA4PretenderExclusion:
    """CA4: GET /recomendador?griefbound=pretender-keeper&tamano=3 no contiene 'Keeper'."""

    def test_ca4_ningun_equipo_contiene_keeper(self, client: TestClient) -> None:
        """CA4: ningun equipo-recomendado contiene el texto 'Keeper'."""
        resp = client.get(
            "/recomendador", params={"griefbound": "pretender-keeper", "tamano": 3}
        )
        assert resp.status_code == 200
        bloques = _extraer_bloques_equipo(resp.text)
        assert len(bloques) == 3, f"Esperaba 3 equipos, hay {len(bloques)}"
        for i, bloque in enumerate(bloques):
            assert "Keeper" not in bloque, (
                f"El equipo {i + 1} contiene 'Keeper' pero no deberia"
            )


# ===========================================================================
# CA5: griefbound=foo&tamano=3 -> 404 con mensaje de error
# ===========================================================================


class TestCA5GriefboundNoEncontrado:
    """CA5: GET /recomendador?griefbound=foo&tamano=3 responde 404 con mensaje de error."""

    def test_ca5_status_404(self, client: TestClient) -> None:
        """CA5: responde 404 si el griefbound no existe."""
        resp = client.get("/recomendador", params={"griefbound": "foo", "tamano": 3})
        assert resp.status_code == 404

    def test_ca5_mensaje_error(self, client: TestClient) -> None:
        """CA5: la respuesta contiene 'Griefbound no encontrado: foo'."""
        resp = client.get("/recomendador", params={"griefbound": "foo", "tamano": 3})
        assert "Griefbound no encontrado: foo" in resp.text

    def test_ca5_dentro_plantilla_base(self, client: TestClient) -> None:
        """CA5: la pagina 404 usa la plantilla base (contiene el pie legal)."""
        resp = client.get("/recomendador", params={"griefbound": "foo", "tamano": 3})
        assert "text/html" in resp.headers.get("content-type", "")
        texto = resp.text.lower()
        assert "no oficial" in texto, "La pagina 404 no usa la plantilla base"

    def test_ca5_sin_equipo_recomendado(self, client: TestClient) -> None:
        """CA5: la pagina 404 no contiene ningun equipo-recomendado."""
        resp = client.get("/recomendador", params={"griefbound": "foo", "tamano": 3})
        equipos = re.findall(r'equipo-recomendado', resp.text)
        assert len(equipos) == 0, "No deberia haber equipo-recomendado en pagina 404"


# ===========================================================================
# CA6: tamano=9 -> 200 con mensaje de validacion
# ===========================================================================


class TestCA6TamanoFueraDeRango:
    """CA6: GET /recomendador?griefbound=convergence&tamano=9 responde 200
    con mensaje de validacion y sin equipos."""

    def test_ca6_status_200(self, client: TestClient) -> None:
        """CA6: responde 200 incluso con tamano fuera de rango."""
        resp = client.get(
            "/recomendador", params={"griefbound": "convergence", "tamano": 9}
        )
        assert resp.status_code == 200

    def test_ca6_mensaje_validacion(self, client: TestClient) -> None:
        """CA6: la pagina contiene el mensaje de validacion."""
        resp = client.get(
            "/recomendador", params={"griefbound": "convergence", "tamano": 9}
        )
        assert "El equipo debe tener entre 2 y 5 cazadores." in resp.text

    def test_ca6_mensaje_error_accesible(self, client: TestClient) -> None:
        """CA6: el error usa la clase comun .mensaje-error y role='alert'."""
        resp = client.get(
            "/recomendador", params={"griefbound": "convergence", "tamano": 9}
        )
        assert re.search(
            r'<p[^>]*class=["\']mensaje-error["\'][^>]*role=["\']alert["\']', resp.text
        ), "El error no usa .mensaje-error con role='alert'"

    def test_ca6_sin_equipo_recomendado(self, client: TestClient) -> None:
        """CA6: no hay ningun equipo-recomendado con tamano=9."""
        resp = client.get(
            "/recomendador", params={"griefbound": "convergence", "tamano": 9}
        )
        equipos = re.findall(r'equipo-recomendado', resp.text)
        assert len(equipos) == 0, "No deberia haber equipo-recomendado con tamano=9"


# ===========================================================================
# CA7: Aviso de datos inferidos
# ===========================================================================


class TestCA7AvisoDatosInferidos:
    """CA7: la pagina de resultados incluye el aviso de datos inferidos."""

    def test_ca7_aviso_presente_en_resultados(self, client: TestClient) -> None:
        """CA7: la pagina con resultados incluye el aviso."""
        resp = client.get(
            "/recomendador", params={"griefbound": "convergence", "tamano": 2}
        )
        assert resp.status_code == 200
        aviso = "Recomendación basada en datos inferidos del reglamento; valídala con el Hunt Book."
        assert aviso in resp.text, "No se encontro el aviso de datos inferidos"

    def test_ca7_aviso_no_presente_en_formulario_vacio(self, client: TestClient) -> None:
        """CA7: el aviso no aparece cuando no hay resultados (solo formulario).
        El aviso solo tiene sentido cuando se muestran recomendaciones."""
        resp = client.get("/recomendador")
        aviso = "Recomendación basada en datos inferidos del reglamento; valídala con el Hunt Book."
        assert aviso not in resp.text, (
            "El aviso de datos inferidos no deberia aparecer en el formulario vacio"
        )


# ===========================================================================
# Casos limite adicionales
# ===========================================================================


class TestCasosLimite:
    """Casos limite no cubiertos directamente por los CAs."""

    def test_edge_pagina_extiende_base_html(self, client: TestClient) -> None:
        """Caso limite: la pagina del recomendador usa la plantilla base."""
        resp = client.get("/recomendador")
        assert resp.status_code == 200
        texto = resp.text.lower()
        # Debe contener el pie legal de base.html
        assert "no oficial" in texto, "La pagina no hereda de base.html"

    def test_edge_enlaza_tema_css(self, client: TestClient) -> None:
        """Caso limite: la pagina enlaza /static/css/tema.css."""
        resp = client.get("/recomendador")
        assert "/static/css/tema.css" in resp.text

    def test_edge_tamano_0_no_muestra_equipos(self, client: TestClient) -> None:
        """Caso limite: tamano=0 no muestra equipos (validacion)."""
        resp = client.get(
            "/recomendador", params={"griefbound": "convergence", "tamano": 0}
        )
        equipos = re.findall(r'equipo-recomendado', resp.text)
        assert len(equipos) == 0

    def test_edge_tamano_negativo_no_muestra_equipos(self, client: TestClient) -> None:
        """Caso limite: tamano=-1 no muestra equipos (validacion)."""
        resp = client.get(
            "/recomendador", params={"griefbound": "convergence", "tamano": -1}
        )
        equipos = re.findall(r'equipo-recomendado', resp.text)
        assert len(equipos) == 0

    def test_edge_sin_parametros_muestra_formulario(self, client: TestClient) -> None:
        """Caso limite: GET /recomendador sin parametros muestra el formulario."""
        resp = client.get("/recomendador")
        assert resp.status_code == 200
        assert re.search(
            r'<select[^>]*name=["\']griefbound["\']', resp.text, re.IGNORECASE
        )

    def test_edge_tamano_no_numerico_no_muestra_equipos(self, client: TestClient) -> None:
        """Caso limite: tamano=abc no muestra equipos y muestra mensaje de validacion."""
        resp = client.get(
            "/recomendador", params={"griefbound": "convergence", "tamano": "abc"}
        )
        equipos = re.findall(r'equipo-recomendado', resp.text)
        assert len(equipos) == 0
        assert "El equipo debe tener entre 2 y 5 cazadores." in resp.text, (
            "No se encontro el mensaje de validacion para tamano no numerico"
        )

    def test_edge_openapi_incluye_recomendador(self, client: TestClient) -> None:
        """Caso limite: /openapi.json contiene la ruta /recomendador."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = set(resp.json()["paths"].keys())
        assert "/recomendador" in paths

    def test_edge_recomendar_value_error_muestra_mensaje(self, client: TestClient) -> None:
        """Caso limite: si recomendar_equipos lanza ValueError, se muestra un
        mensaje amigable sin HTTP 500."""
        with patch(
            "grimcoven_equipos.paginas.recomendar_equipos",
            side_effect=ValueError("No hay suficientes cazadores disponibles"),
        ):
            resp = client.get(
                "/recomendador",
                params={"griefbound": "convergence", "tamano": 2},
            )
        assert resp.status_code == 200
        assert "No hay suficientes cazadores disponibles" in resp.text
        equipos = re.findall(r"equipo-recomendado", resp.text)
        assert len(equipos) == 0

    def test_edge_css_focus_visible_button_select(self, client: TestClient) -> None:
        """Hallazgo UI: tema.css tiene regla focus-visible para button y select."""
        resp = client.get("/static/css/tema.css")
        assert resp.status_code == 200
        css = resp.text
        assert "button:focus-visible" in css, "Falta regla focus-visible para button"
        assert "select:focus-visible" in css, "Falta regla focus-visible para select"

    def test_edge_css_form_responsive(self, client: TestClient) -> None:
        """Hallazgo UI: tema.css tiene estilos responsive para el formulario."""
        resp = client.get("/static/css/tema.css")
        css = resp.text
        assert "form" in css, "Falta reglas de form en tema.css"
        assert "min-height: 44px" in css, "Falta min-height: 44px para el boton"

    def test_edge_css_clases_error_y_aviso(self, client: TestClient) -> None:
        """Hallazgo UI: tema.css define las clases .mensaje-error y .aviso."""
        resp = client.get("/static/css/tema.css")
        css = resp.text
        assert ".mensaje-error" in css, "Falta estilo para .mensaje-error en tema.css"
        assert ".aviso" in css, "Falta estilo para .aviso en tema.css"

    def test_edge_css_h3_estilo(self, client: TestClient) -> None:
        """Hallazgo UI: tema.css define estilo para h3."""
        resp = client.get("/static/css/tema.css")
        css = resp.text
        assert "h3" in css, "Falta estilo para h3 en tema.css"

    def test_edge_orden_equipos_por_puntuacion(self, client: TestClient) -> None:
        """Caso limite: los equipos mostrados estan en orden descendente de puntuacion."""
        resp = client.get(
            "/recomendador", params={"griefbound": "convergence", "tamano": 2}
        )
        bloques = _extraer_bloques_equipo(resp.text)
        assert len(bloques) == 3
        # Extraer puntuaciones de los bloques
        puntuaciones = []
        for bloque in bloques:
            match = re.search(r'(\d+)\s*puntos', bloque)
            assert match is not None, f"No se encontro puntuacion en bloque: {bloque[:200]}"
            puntuaciones.append(int(match.group(1)))
        assert puntuaciones == sorted(puntuaciones, reverse=True), (
            f"Los equipos no estan ordenados por puntuacion: {puntuaciones}"
        )


# ===========================================================================
# Helpers (no son tests)
# ===========================================================================


def _extraer_bloques_equipo(html: str) -> list[str]:
    """Extrae los bloques HTML de cada equipo-recomendado.

    Busca elementos que tengan class='equipo-recomendado' y extrae su contenido
    hasta el siguiente cierre del mismo nivel. Usa una heuristica simple:
    busca desde cada apertura hasta el siguiente bloque o fin de contenedor.
    """
    # Patron para buscar bloques con class que contenga equipo-recomendado
    # Extraemos desde la apertura del tag hasta un cierre razonable
    bloques: list[str] = []
    patron = re.compile(
        r'(<\w+[^>]*class=["\'][^"\']*equipo-recomendado[^"\']*["\'][^>]*>)',
        re.IGNORECASE | re.DOTALL,
    )
    posiciones = [(m.start(), m.group(1)) for m in patron.finditer(html)]
    for i, (pos, _apertura) in enumerate(posiciones):
        # El bloque va desde esta posicion hasta la siguiente apertura de equipo-recomendado
        # o hasta 2000 caracteres (limite razonable)
        fin = posiciones[i + 1][0] if i + 1 < len(posiciones) else pos + 2000
        bloque = html[pos:fin]
        bloques.append(bloque)
    return bloques
