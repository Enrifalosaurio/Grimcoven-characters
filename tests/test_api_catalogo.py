"""Tests de US-002: API de consulta del catalogo de cazadores y Griefbound.

Cada test indica el criterio de aceptacion (CA<n>) que cubre.
Se usa fastapi.testclient.TestClient (basado en httpx) sin levantar servidor.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from grimcoven_equipos.app import create_app

# ---- fixtures


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Cliente de test para la app creada con create_app()."""
    app = create_app()
    return TestClient(app)


# ---- CA1: GET /api/cazadores -> 200, 8 objetos ordenados por id


CAMPOS_CAZADOR = {
    "id", "nombre", "expansion", "complejidad", "roles",
    "contrarresta", "vida", "movimiento", "fuente",
}


def test_ca1_get_cazadores_status_200(client: TestClient) -> None:
    """CA1: GET /api/cazadores responde 200."""
    response = client.get("/api/cazadores")
    assert response.status_code == 200


def test_ca1_get_cazadores_devuelve_8_objetos(client: TestClient) -> None:
    """CA1: GET /api/cazadores devuelve una lista de 8 objetos."""
    data = client.get("/api/cazadores").json()
    assert isinstance(data, list)
    assert len(data) == 8


def test_ca1_get_cazadores_ordenados_por_id(client: TestClient) -> None:
    """CA1: la lista esta ordenada por id."""
    data = client.get("/api/cazadores").json()
    ids = [c["id"] for c in data]
    assert ids == sorted(ids)


def test_ca1_get_cazadores_campos_completos(client: TestClient) -> None:
    """CA1: cada objeto tiene todos los campos requeridos."""
    data = client.get("/api/cazadores").json()
    for cazador in data:
        assert CAMPOS_CAZADOR <= set(cazador.keys()), (
            f"Faltan campos en cazador {cazador.get('id', '?')}"
        )


# ---- CA2: GET /api/cazadores/keeper -> 200, nombre y complejidad


def test_ca2_get_cazador_por_id_keeper(client: TestClient) -> None:
    """CA2: GET /api/cazadores/keeper responde 200 con nombre y complejidad."""
    response = client.get("/api/cazadores/keeper")
    assert response.status_code == 200
    data = response.json()
    assert data["nombre"] == "Keeper"
    assert data["complejidad"] == "Baja-Media"


def test_ca2_get_cazador_por_id_tiene_todos_los_campos(client: TestClient) -> None:
    """CA2: el detalle de un cazador incluye todos los campos."""
    data = client.get("/api/cazadores/keeper").json()
    assert CAMPOS_CAZADOR <= set(data.keys())


# ---- CA3: GET /api/cazadores/nope -> 404


def test_ca3_get_cazador_inexistente_404(client: TestClient) -> None:
    """CA3: GET /api/cazadores/nope responde 404 con detail correcto."""
    response = client.get("/api/cazadores/nope")
    assert response.status_code == 404
    assert response.json()["detail"] == "Cazador no encontrado: nope"


def test_ca3_get_cazador_inexistente_otro_id(client: TestClient) -> None:
    """CA3 (caso limite): otro id inexistente tambien da 404 con el id en el mensaje."""
    response = client.get("/api/cazadores/no-existe")
    assert response.status_code == 404
    assert "no-existe" in response.json()["detail"]


# ---- CA4: GET /api/griefbound -> 200, 16 objetos; filtro por tipo


def test_ca4_get_griefbound_status_200(client: TestClient) -> None:
    """CA4: GET /api/griefbound responde 200."""
    response = client.get("/api/griefbound")
    assert response.status_code == 200


def test_ca4_get_griefbound_devuelve_16_objetos(client: TestClient) -> None:
    """CA4: GET /api/griefbound devuelve 16 objetos."""
    data = client.get("/api/griefbound").json()
    assert isinstance(data, list)
    assert len(data) == 16


def test_ca4_get_griefbound_filtro_tipo_griefbound(client: TestClient) -> None:
    """CA4: GET /api/griefbound?tipo=griefbound devuelve 8 objetos."""
    data = client.get("/api/griefbound", params={"tipo": "griefbound"}).json()
    assert isinstance(data, list)
    assert len(data) == 8
    assert all(g["tipo"] == "griefbound" for g in data)


def test_ca4_get_griefbound_filtro_tipo_pretender(client: TestClient) -> None:
    """CA4: GET /api/griefbound?tipo=pretender devuelve 8 objetos."""
    data = client.get("/api/griefbound", params={"tipo": "pretender"}).json()
    assert isinstance(data, list)
    assert len(data) == 8
    assert all(g["tipo"] == "pretender" for g in data)


def test_ca4_griefbound_sin_filtro_suma_tipos(client: TestClient) -> None:
    """CA4 (caso limite): los 16 objetos sin filtro son la union de griefbound + pretender."""
    data = client.get("/api/griefbound").json()
    tipos = {g["tipo"] for g in data}
    assert tipos == {"griefbound", "pretender"}
    n_griefbound = sum(1 for g in data if g["tipo"] == "griefbound")
    n_pretender = sum(1 for g in data if g["tipo"] == "pretender")
    assert n_griefbound == 8
    assert n_pretender == 8


# ---- CA5: GET /api/griefbound?tipo=xyz -> 422


def test_ca5_get_griefbound_tipo_invalido_422(client: TestClient) -> None:
    """CA5: GET /api/griefbound?tipo=xyz responde 422."""
    response = client.get("/api/griefbound", params={"tipo": "xyz"})
    assert response.status_code == 422


def test_ca5_get_griefbound_tipo_invalido_otro_valor(client: TestClient) -> None:
    """CA5 (caso limite): otro tipo invalido tambien da 422."""
    response = client.get("/api/griefbound", params={"tipo": "boss"})
    assert response.status_code == 422


# ---- CA6: GET /api/griefbound/convergence -> 200


def test_ca6_get_griefbound_convergence(client: TestClient) -> None:
    """CA6: GET /api/griefbound/convergence responde 200, tipo y amenazas."""
    response = client.get("/api/griefbound/convergence")
    assert response.status_code == 200
    data = response.json()
    assert data["tipo"] == "griefbound"
    assert data["amenazas"] == ["quemadura"]


def test_ca6_get_griefbound_convergence_campos(client: TestClient) -> None:
    """CA6 (complemento): convergence tiene todos los campos esperados de un griefbound."""
    data = client.get("/api/griefbound/convergence").json()
    campos_griefbound = {"id", "nombre", "tipo", "expansion", "amenazas", "fuente"}
    assert campos_griefbound <= set(data.keys())


# ---- CA7: GET /api/griefbound/pretender-keeper -> 200


def test_ca7_get_griefbound_pretender_keeper(client: TestClient) -> None:
    """CA7: GET pretender-keeper responde 200, tipo y cazador_origen."""
    response = client.get("/api/griefbound/pretender-keeper")
    assert response.status_code == 200
    data = response.json()
    assert data["tipo"] == "pretender"
    assert data["cazador_origen"] == "keeper"


def test_ca7_pretender_keeper_tiene_nombre(client: TestClient) -> None:
    """CA7 (complemento): pretender-keeper tiene nombre."""
    data = client.get("/api/griefbound/pretender-keeper").json()
    assert data["nombre"] == "Pretender Keeper"


# ---- CA8: GET /api/griefbound/foo -> 404


def test_ca8_get_griefbound_inexistente_404(client: TestClient) -> None:
    """CA8: GET /api/griefbound/foo responde 404 con detail correcto."""
    response = client.get("/api/griefbound/foo")
    assert response.status_code == 404
    assert response.json()["detail"] == "Griefbound no encontrado: foo"


def test_ca8_get_griefbound_inexistente_otro_id(client: TestClient) -> None:
    """CA8 (caso limite): otro id inexistente tambien da 404 con el id en el mensaje."""
    response = client.get("/api/griefbound/no-existe")
    assert response.status_code == 404
    assert "no-existe" in response.json()["detail"]


# ---- Casos limite adicionales


def test_edge_cazadores_cada_objeto_tiene_id_unico(client: TestClient) -> None:
    """Caso limite: los 8 cazadores tienen ids unicos."""
    data = client.get("/api/cazadores").json()
    ids = [c["id"] for c in data]
    assert len(ids) == len(set(ids))


def test_edge_griefbound_cada_objeto_tiene_id_unico(client: TestClient) -> None:
    """Caso limite: los 16 griefbound tienen ids unicos."""
    data = client.get("/api/griefbound").json()
    ids = [g["id"] for g in data]
    assert len(ids) == len(set(ids))


def test_edge_get_cazador_duality_tiene_datos_correctos(client: TestClient) -> None:
    """Caso limite: verificar otro cazador (duality) ademas de keeper."""
    response = client.get("/api/cazadores/duality")
    assert response.status_code == 200
    data = response.json()
    assert data["nombre"] == "Duality"
    assert data["expansion"] == "base"
    assert data["complejidad"] == "Media"


def test_edge_griefbound_swarm_mistress(client: TestClient) -> None:
    """Caso limite: verificar otro griefbound (swarm-mistress)."""
    response = client.get("/api/griefbound/swarm-mistress")
    assert response.status_code == 200
    data = response.json()
    assert data["tipo"] == "griefbound"
    assert data["amenazas"] == ["enjambre"]


def test_edge_pretender_tiene_cazador_origen(client: TestClient) -> None:
    """Caso limite: todos los pretender en la lista tienen cazador_origen."""
    data = client.get("/api/griefbound", params={"tipo": "pretender"}).json()
    for p in data:
        assert "cazador_origen" in p, f"pretender {p.get('id')} sin cazador_origen"
        assert p["cazador_origen"] is not None


def test_edge_griefbound_no_pretender_sin_cazador_origen(client: TestClient) -> None:
    """Caso limite: los griefbound (no pretender) no tienen cazador_origen o es None."""
    data = client.get("/api/griefbound", params={"tipo": "griefbound"}).json()
    for g in data:
        assert g.get("cazador_origen") is None, (
            f"griefbound {g.get('id')} no deberia tener cazador_origen"
        )
