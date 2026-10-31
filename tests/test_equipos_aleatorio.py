"""Tests de US-003: API del selector aleatorio de equipos.

Cada test indica el criterio de aceptacion (CA<n>) que cubre.
"""

from __future__ import annotations

import random
from collections import Counter
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from grimcoven_equipos.app import create_app
from grimcoven_equipos.catalogo import Cazador, cargar_cazadores
from grimcoven_equipos.equipos.aleatorio import generar_equipo_aleatorio

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

IDS_CATALOGO = [
    "duality",
    "gunslinger",
    "keeper",
    "technomancer",
    "mannequin",
    "death-jester",
    "clockwork-giant",
    "twins",
]


@pytest.fixture(scope="module")
def catalogo() -> list[Cazador]:
    """Catalogo completo de 8 cazadores."""
    return cargar_cazadores()


@pytest.fixture(scope="module")
def app():
    """Instancia de la app FastAPI."""
    return create_app()


@pytest.fixture(scope="module")
def client(app) -> TestClient:
    """Cliente HTTP sincrono para la app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# CA1: GET /api/equipos/aleatorio?tamano=3 -> 200 con 3 cazadores distintos
# ---------------------------------------------------------------------------


def test_ca1_equipo_aleatorio_tamano_3(client) -> None:
    """CA1: tamano=3 devuelve 200, 3 cazadores distintos del catalogo."""
    resp = client.get("/api/equipos/aleatorio", params={"tamano": 3})
    assert resp.status_code == 200

    body = resp.json()
    assert body["tamano"] == 3
    assert "semilla" in body
    assert isinstance(body["cazadores"], list)
    assert len(body["cazadores"]) == 3

    ids = [c["id"] for c in body["cazadores"]]
    assert len(set(ids)) == 3, "Los 3 ids deben ser distintos"
    for c in body["cazadores"]:
        assert c["id"] in IDS_CATALOGO
        assert "nombre" in c
        assert "roles" in c and isinstance(c["roles"], list)


# ---------------------------------------------------------------------------
# CA2: tamano=2 y tamano=5 (limites) responden 200
# ---------------------------------------------------------------------------


def test_ca2_equipo_aleatorio_tamano_2(client) -> None:
    """CA2: tamano=2 (limite inferior) devuelve 200 con 2 cazadores distintos."""
    resp = client.get("/api/equipos/aleatorio", params={"tamano": 2})
    assert resp.status_code == 200

    body = resp.json()
    assert body["tamano"] == 2
    assert len(body["cazadores"]) == 2
    ids = [c["id"] for c in body["cazadores"]]
    assert len(set(ids)) == 2


def test_ca2_equipo_aleatorio_tamano_5(client) -> None:
    """CA2: tamano=5 (limite superior) devuelve 200 con 5 cazadores distintos."""
    resp = client.get("/api/equipos/aleatorio", params={"tamano": 5})
    assert resp.status_code == 200

    body = resp.json()
    assert body["tamano"] == 5
    assert len(body["cazadores"]) == 5
    ids = [c["id"] for c in body["cazadores"]]
    assert len(set(ids)) == 5


# ---------------------------------------------------------------------------
# CA3: tamano invalido (1, 6, abc, ausente) -> 422
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "params,descripcion",
    [
        pytest.param({"tamano": 1}, "tamano=1 (bajo el limite)", id="tamano-1"),
        pytest.param({"tamano": 6}, "tamano=6 (sobre el limite)", id="tamano-6"),
        pytest.param({"tamano": "abc"}, "tamano=abc (no numerico)", id="tamano-abc"),
        pytest.param({}, "sin parametro tamano", id="sin-tamano"),
    ],
)
def test_ca3_tamano_invalido_devuelve_422(client, params, descripcion) -> None:
    """CA3: valores invalidos de tamano devuelven 422."""
    resp = client.get("/api/equipos/aleatorio", params=params)
    assert resp.status_code == 422, f"Esperaba 422 para {descripcion}, obtuve {resp.status_code}"


# ---------------------------------------------------------------------------
# CA4: semilla=42 produce resultados reproducibles
# ---------------------------------------------------------------------------


def test_ca4_semilla_reproduce_resultado(client) -> None:
    """CA4: dos peticiones con tamano=4&semilla=42 devuelven la misma lista."""
    params = {"tamano": 4, "semilla": 42}
    resp1 = client.get("/api/equipos/aleatorio", params=params)
    resp2 = client.get("/api/equipos/aleatorio", params=params)
    assert resp1.status_code == 200
    assert resp2.status_code == 200

    body1 = resp1.json()
    body2 = resp2.json()
    assert body1["cazadores"] == body2["cazadores"]
    assert body1["semilla"] == 42
    assert body2["semilla"] == 42


# ---------------------------------------------------------------------------
# CA5: 200 peticiones sin semilla cubren los 8 cazadores, sin ids repetidos
# ---------------------------------------------------------------------------


def test_ca5_aleatoriedad_sin_semilla(client) -> None:
    """CA5: 200 peticiones con tamano=5 sin semilla: ids unicos y cobertura total."""
    todos_los_ids: Counter[str] = Counter()
    for _ in range(200):
        resp = client.get("/api/equipos/aleatorio", params={"tamano": 5})
        assert resp.status_code == 200
        body = resp.json()
        ids = [c["id"] for c in body["cazadores"]]
        assert len(set(ids)) == 5, "No debe haber ids repetidos en una respuesta"
        todos_los_ids.update(ids)

    # Cada uno de los 8 cazadores debe aparecer al menos una vez
    for id_ in IDS_CATALOGO:
        assert todos_los_ids[id_] > 0, f"El cazador {id_!r} no aparecio en 200 peticiones"


# ---------------------------------------------------------------------------
# CA6: generar_equipo_aleatorio con catalogo insuficiente lanza ValueError
# ---------------------------------------------------------------------------


def test_ca6_error_si_no_hay_suficientes_cazadores(catalogo) -> None:
    """CA6: generar_equipo_aleatorio lanza ValueError si tamano > len(cazadores)."""
    subcatalogo = catalogo[:3]
    rng = random.Random(0)
    with pytest.raises(ValueError, match="No hay suficientes cazadores para un equipo de 4"):
        generar_equipo_aleatorio(subcatalogo, 4, rng)


def test_ca6_error_mensaje_contiene_tamano(catalogo) -> None:
    """CA6: el mensaje de error incluye el tamano solicitado."""
    rng = random.Random(0)
    with pytest.raises(ValueError) as exc_info:
        generar_equipo_aleatorio(catalogo[:2], 5, rng)
    assert "5" in str(exc_info.value)


# ---------------------------------------------------------------------------
# CA7: generar_equipo_aleatorio con misma semilla produce misma lista
# ---------------------------------------------------------------------------


def test_ca7_misma_semilla_produce_misma_lista(catalogo) -> None:
    """CA7: dos llamadas con Random(7) devuelven la misma lista."""
    rng1 = random.Random(7)
    rng2 = random.Random(7)
    equipo1 = generar_equipo_aleatorio(catalogo, 4, rng1)
    equipo2 = generar_equipo_aleatorio(catalogo, 4, rng2)
    assert [c.id for c in equipo1] == [c.id for c in equipo2]


def test_ca7_resultado_son_cazadores_validos(catalogo) -> None:
    """CA7: la funcion devuelve objetos Cazador del catalogo."""
    rng = random.Random(7)
    equipo = generar_equipo_aleatorio(catalogo, 3, rng)
    assert len(equipo) == 3
    ids_catalogo = {c.id for c in catalogo}
    for cazador in equipo:
        assert isinstance(cazador, Cazador)
        assert cazador.id in ids_catalogo


def test_ca7_sin_repetidos(catalogo) -> None:
    """CA7: la funcion nunca devuelve cazadores repetidos."""
    rng = random.Random(7)
    equipo = generar_equipo_aleatorio(catalogo, 5, rng)
    ids = [c.id for c in equipo]
    assert len(set(ids)) == 5


# ---------------------------------------------------------------------------
# Casos limite adicionales
# ---------------------------------------------------------------------------


def test_limite_tamano_2_con_funcion_pura(catalogo) -> None:
    """Caso limite: tamano minimo (2) funciona correctamente."""
    rng = random.Random(99)
    equipo = generar_equipo_aleatorio(catalogo, 2, rng)
    assert len(equipo) == 2
    assert equipo[0].id != equipo[1].id


def test_limite_tamano_igual_a_catalogo(catalogo) -> None:
    """Caso limite: tamano igual al numero de cazadores disponibles."""
    rng = random.Random(0)
    equipo = generar_equipo_aleatorio(catalogo, len(catalogo), rng)
    assert len(equipo) == len(catalogo)
    assert len({c.id for c in equipo}) == len(catalogo)


def test_limite_respuesta_incluye_semilla_null_sin_semilla(client) -> None:
    """Caso limite: la respuesta sin semilla incluye semilla como null o int."""
    resp = client.get("/api/equipos/aleatorio", params={"tamano": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert "semilla" in body
    assert body["semilla"] is None or isinstance(body["semilla"], int)


# ---------------------------------------------------------------------------
# Hallazgo 1: ValueError de generar_equipo_aleatorio -> HTTP 409
# ---------------------------------------------------------------------------


def test_valor_error_equipo_insuficiente_devuelve_409(client, catalogo) -> None:
    """Hallazgo 1: si el catalogo tiene menos cazadores que tamano, devuelve 409."""
    # Inyectamos un catalogo con un solo cazador para forzar el ValueError.
    subcatalogo = catalogo[:1]
    with patch(
        "grimcoven_equipos.api.equipos.cargar_cazadores",
        return_value=subcatalogo,
    ):
        resp = client.get("/api/equipos/aleatorio", params={"tamano": 2})
    assert resp.status_code == 409
    body = resp.json()
    assert "No hay suficientes cazadores" in body["detail"]


# ---------------------------------------------------------------------------
# Hallazgo 2: cargar_cazadores falla -> error HTTP sin filtrar detalles
# ---------------------------------------------------------------------------


def test_cargar_cazadores_falla_devuelve_500_sin_detalles_internos(client) -> None:
    """Hallazgo 2: si cargar_cazadores lanza ValueError, responde 500 sin info interna."""
    with patch(
        "grimcoven_equipos.api.equipos.cargar_cazadores",
        side_effect=ValueError("/ruta/secreta/cazadores.json: JSON invalido"),
    ):
        resp = client.get("/api/equipos/aleatorio", params={"tamano": 3})
    assert resp.status_code == 500
    body = resp.json()
    # No debe filtrar la ruta interna ni el detalle del ValueError original
    assert "/ruta/secreta" not in body.get("detail", "")
    assert "JSON invalido" not in body.get("detail", "")
    # Debe tener un mensaje generico
    assert "catalogo" in body["detail"].lower()


# ---------------------------------------------------------------------------
# Hallazgo 5: semilla=0 (entero falsy) es reproducible
# ---------------------------------------------------------------------------


def test_ca4_semilla_cero_es_reproducible(client) -> None:
    """Hallazgo 5: semilla=0 produce resultados reproducibles y distintos de sin semilla."""
    params_cero = {"tamano": 4, "semilla": 0}
    resp1 = client.get("/api/equipos/aleatorio", params=params_cero)
    resp2 = client.get("/api/equipos/aleatorio", params=params_cero)
    assert resp1.status_code == 200
    assert resp2.status_code == 200

    body1 = resp1.json()
    body2 = resp2.json()
    # Reproducibilidad: misma semilla=0 -> misma lista
    assert body1["cazadores"] == body2["cazadores"]
    assert body1["semilla"] == 0
    assert body2["semilla"] == 0

    # Distinto de semilla=None (con alta probabilidad, verificamos que semilla=0 no es ignorada)
    resp_sin = client.get("/api/equipos/aleatorio", params={"tamano": 4})
    body_sin = resp_sin.json()
    assert body_sin["semilla"] is None
    # No podemos garantizar al 100% que sean distintas, pero si semilla=0 se trata
    # correctamente, al menos confirmamos que la semilla se guarda como 0
    assert body1["semilla"] == 0
