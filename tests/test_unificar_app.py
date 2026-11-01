"""Tests de US-008: Unificar la aplicacion FastAPI en una sola fabrica create_app.

Cada test indica el criterio de aceptacion (CA<n>) que cubre.
"""

from __future__ import annotations

import importlib

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
    """Cliente HTTP sincrono para la app unificada."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# CA1: GET /api/cazadores y GET /api/equipos/aleatorio sobre la MISMA instancia
# ---------------------------------------------------------------------------


def test_ca1_cazadores_y_equipos_en_misma_instancia(client: TestClient) -> None:
    """CA1: ambas rutas responden 200 sobre la misma instancia de app."""
    resp_cazadores = client.get("/api/cazadores")
    assert resp_cazadores.status_code == 200

    resp_equipos = client.get("/api/equipos/aleatorio", params={"tamano": 3, "semilla": 42})
    assert resp_equipos.status_code == 200


def test_ca1_cazadores_devuelve_8(client: TestClient) -> None:
    """CA1: GET /api/cazadores devuelve lista de 8 cazadores."""
    data = client.get("/api/cazadores").json()
    assert isinstance(data, list)
    assert len(data) == 8


def test_ca1_equipos_aleatorio_tamano_3_semilla_42(client: TestClient) -> None:
    """CA1: GET /api/equipos/aleatorio?tamano=3&semilla=42 devuelve 3 ids distintos."""
    resp = client.get("/api/equipos/aleatorio", params={"tamano": 3, "semilla": 42})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tamano"] == 3
    assert body["semilla"] == 42
    assert len(body["cazadores"]) == 3
    ids = [c["id"] for c in body["cazadores"]]
    assert len(set(ids)) == 3, "Los 3 cazadores deben tener ids distintos"


# ---------------------------------------------------------------------------
# CA2: GET /openapi.json tiene exactamente las rutas esperadas con solo GET
# ---------------------------------------------------------------------------

RUTAS_ESPERADAS = {
    "/",
    "/api/cazadores",
    "/api/cazadores/{cazador_id}",
    "/api/griefbound",
    "/api/griefbound/{griefbound_id}",
    "/api/equipos/aleatorio",
}


def test_ca2_openapi_paths_exactas(client: TestClient) -> None:
    """CA2: /openapi.json contiene exactamente las rutas de RUTAS_ESPERADAS."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = set(resp.json()["paths"].keys())
    assert paths == RUTAS_ESPERADAS


def test_ca2_openapi_solo_metodo_get(client: TestClient) -> None:
    """CA2: cada ruta en /openapi.json solo tiene el metodo 'get'."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    for ruta, metodos in paths.items():
        assert set(metodos.keys()) == {"get"}, (
            f"La ruta {ruta} deberia tener solo 'get', tiene {set(metodos.keys())}"
        )


# ---------------------------------------------------------------------------
# CA3: Rutas sin /api o con /api duplicado devuelven 404
# ---------------------------------------------------------------------------


def test_ca3_sin_prefijo_api_devuelve_404(client: TestClient) -> None:
    """CA3: GET /equipos/aleatorio?tamano=3 (sin /api) devuelve 404."""
    resp = client.get("/equipos/aleatorio", params={"tamano": 3})
    assert resp.status_code == 404


def test_ca3_prefijo_api_duplicado_devuelve_404(client: TestClient) -> None:
    """CA3: GET /api/api/equipos/aleatorio?tamano=3 devuelve 404."""
    resp = client.get("/api/api/equipos/aleatorio", params={"tamano": 3})
    assert resp.status_code == 404


def test_ca3_cazadores_sin_prefijo_api_devuelve_404(client: TestClient) -> None:
    """CA3 (caso limite): GET /cazadores sin /api tambien devuelve 404."""
    resp = client.get("/cazadores")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# CA4: Los routers no declaran /api en su prefijo
# ---------------------------------------------------------------------------


def test_ca4_router_catalogo_prefix_vacio() -> None:
    """CA4: grimcoven_equipos.api.catalogo.router.prefix es ''."""
    from grimcoven_equipos.api.catalogo import router as catalogo_router

    assert catalogo_router.prefix == ""


def test_ca4_router_equipos_prefix_equipos() -> None:
    """CA4: grimcoven_equipos.api.equipos.router.prefix es '/equipos'."""
    from grimcoven_equipos.api.equipos import router as equipos_router

    assert equipos_router.prefix == "/equipos"


# ---------------------------------------------------------------------------
# CA5: grimcoven_equipos.api.app ya no existe (ModuleNotFoundError)
# ---------------------------------------------------------------------------


def test_ca5_api_app_modulo_eliminado() -> None:
    """CA5: importlib.import_module('grimcoven_equipos.api.app') lanza ModuleNotFoundError."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("grimcoven_equipos.api.app")


# ---------------------------------------------------------------------------
# CA6: Los tests existentes importan create_app desde grimcoven_equipos.app
# ---------------------------------------------------------------------------


def test_ca6_test_api_catalogo_importa_desde_app() -> None:
    """CA6: tests/test_api_catalogo.py importa create_app desde grimcoven_equipos.app."""
    from pathlib import Path

    ruta = Path(__file__).resolve().parent / "test_api_catalogo.py"
    contenido = ruta.read_text(encoding="utf-8")
    assert "from grimcoven_equipos.app import create_app" in contenido


def test_ca6_test_equipos_aleatorio_importa_desde_app() -> None:
    """CA6: tests/test_equipos_aleatorio.py importa create_app desde grimcoven_equipos.app."""
    from pathlib import Path

    ruta = Path(__file__).resolve().parent / "test_equipos_aleatorio.py"
    contenido = ruta.read_text(encoding="utf-8")
    assert "from grimcoven_equipos.app import create_app" in contenido


# ---------------------------------------------------------------------------
# Casos limite adicionales
# ---------------------------------------------------------------------------


def test_edge_app_modulo_tiene_instancia_app() -> None:
    """Caso limite: grimcoven_equipos.app.app existe como instancia a nivel de modulo."""
    from fastapi import FastAPI

    from grimcoven_equipos.app import app

    assert isinstance(app, FastAPI)


def test_edge_misma_instancia_modulo_responde_cazadores() -> None:
    """Caso limite: la instancia grimcoven_equipos.app.app responde en /api/cazadores."""
    from grimcoven_equipos.app import app

    c = TestClient(app)
    resp = c.get("/api/cazadores")
    assert resp.status_code == 200


def test_edge_misma_instancia_modulo_responde_equipos() -> None:
    """Caso limite: la instancia grimcoven_equipos.app.app responde en /api/equipos/aleatorio."""
    from grimcoven_equipos.app import app

    c = TestClient(app)
    resp = c.get("/api/equipos/aleatorio", params={"tamano": 3, "semilla": 42})
    assert resp.status_code == 200


def test_edge_griefbound_disponible_en_app_unificada(client: TestClient) -> None:
    """Caso limite: GET /api/griefbound sigue respondiendo 200 en la app unificada."""
    resp = client.get("/api/griefbound")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 16


def test_edge_griefbound_por_id_en_app_unificada(client: TestClient) -> None:
    """Caso limite: GET /api/griefbound/convergence sigue respondiendo 200."""
    resp = client.get("/api/griefbound/convergence")
    assert resp.status_code == 200
    assert resp.json()["tipo"] == "griefbound"
