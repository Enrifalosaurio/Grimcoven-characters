"""Tests de US-009: catalogo compartido cargado una vez e inyectable en los endpoints.

Cada test indica el criterio de aceptacion (CA<n>) que cubre.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

import grimcoven_equipos.app as app_mod
import grimcoven_equipos.catalogo as catalogo_mod
from grimcoven_equipos.api.dependencias import obtener_catalogo
from grimcoven_equipos.app import create_app
from grimcoven_equipos.catalogo import (
    Catalogo,
    Cazador,
    Fuente,
    Griefbound,
    cargar_cazadores,
    cargar_griefbound,
)

RAIZ = Path(__file__).resolve().parents[1]
DIRECTORIO_API = RAIZ / "src" / "grimcoven_equipos" / "api"
FICHERO_REGLAS = "GC_Rulebook_280x280mm_bleed3mm [36 pages]_[lowres]_compressed.pdf"

# Ids devueltos por main (antes de US-009) para GET /api/equipos/aleatorio?tamano=4&semilla=42,
# capturados ejecutando el codigo de main. El selector recibia los cazadores en el orden del
# JSON; si los recibiera ordenados por id el resultado seria
# ['death-jester', 'clockwork-giant', 'mannequin', 'duality'].
IDS_SEMILLA_42_TAMANO_4 = ["gunslinger", "duality", "death-jester", "keeper"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _cazador(id_: str, nombre: str) -> Cazador:
    return Cazador(
        id=id_,
        nombre=nombre,
        expansion="base",
        complejidad="baja",
        roles=["dano"],
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


@pytest.fixture
def catalogo_prueba() -> Catalogo:
    """Catalogo de prueba con 3 cazadores (desordenados por id) y 2 Griefbound."""
    return Catalogo(
        cazadores=(
            _cazador("zeta", "Zeta"),
            _cazador("alfa", "Alfa"),
            _cazador("media", "Media"),
        ),
        griefbound=(
            _griefbound("gb-uno", "Griefbound Uno"),
            _griefbound("gb-dos", "Griefbound Dos"),
        ),
    )


@pytest.fixture
def client_prueba(catalogo_prueba: Catalogo) -> TestClient:
    """Cliente sobre una app creada con el catalogo de prueba inyectado."""
    return TestClient(create_app(catalogo=catalogo_prueba))


# ---------------------------------------------------------------------------
# CA1: el catalogo se carga una sola vez, en create_app, y nunca por peticion
# ---------------------------------------------------------------------------


def test_ca1_cargadores_se_invocan_una_vez_en_create_app_y_cero_en_peticiones() -> None:
    """CA1: cargar_cazadores/cargar_griefbound 1 vez en create_app y 0 en 5 peticiones."""
    with (
        patch.object(app_mod, "cargar_cazadores", wraps=cargar_cazadores) as mock_cz,
        patch.object(app_mod, "cargar_griefbound", wraps=cargar_griefbound) as mock_gb,
    ):
        app = create_app()
        assert mock_cz.call_count == 1
        assert mock_gb.call_count == 1

        client = TestClient(app)
        for _ in range(3):
            resp = client.get("/api/equipos/aleatorio", params={"tamano": 3})
            assert resp.status_code == 200
        for _ in range(2):
            resp = client.get("/api/cazadores")
            assert resp.status_code == 200

        assert mock_cz.call_count == 1, "cargar_cazadores no debe llamarse durante peticiones"
        assert mock_gb.call_count == 1, "cargar_griefbound no debe llamarse durante peticiones"


def test_ca1_ninguna_peticion_lee_json_del_catalogo(monkeypatch: pytest.MonkeyPatch) -> None:
    """CA1: tras create_app, ninguna peticion vuelve a leer un JSON del catalogo.

    Se espia el lector de bajo nivel para cubrir cualquier referencia a los cargadores
    (incluidas las importadas por nombre en los routers).
    """
    client = TestClient(create_app())

    lecturas: list[Path] = []
    lector_original = catalogo_mod._leer_lista

    def _espia(ruta: Path) -> list:
        lecturas.append(ruta)
        return lector_original(ruta)

    monkeypatch.setattr(catalogo_mod, "_leer_lista", _espia)

    for _ in range(3):
        assert client.get("/api/equipos/aleatorio", params={"tamano": 3}).status_code == 200
    for _ in range(2):
        assert client.get("/api/cazadores").status_code == 200
    assert client.get("/api/griefbound").status_code == 200
    assert client.get("/api/cazadores/keeper").status_code == 200

    assert lecturas == [], f"Se releyo el catalogo durante las peticiones: {lecturas}"


# ---------------------------------------------------------------------------
# CA2: create_app(catalogo=X) sirve exactamente los datos de X
# ---------------------------------------------------------------------------


def test_ca2_cazadores_del_catalogo_inyectado_ordenados_por_id(
    client_prueba: TestClient,
) -> None:
    """CA2: GET /api/cazadores devuelve exactamente los 3 cazadores, ordenados por id."""
    resp = client_prueba.get("/api/cazadores")
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()]
    assert ids == ["alfa", "media", "zeta"]


def test_ca2_griefbound_del_catalogo_inyectado(client_prueba: TestClient) -> None:
    """CA2: GET /api/griefbound devuelve exactamente los 2 Griefbound inyectados."""
    resp = client_prueba.get("/api/griefbound")
    assert resp.status_code == 200
    ids = sorted(g["id"] for g in resp.json())
    assert ids == ["gb-dos", "gb-uno"]


def test_ca2_equipo_aleatorio_usa_catalogo_inyectado(client_prueba: TestClient) -> None:
    """CA2: GET /api/equipos/aleatorio?tamano=3 devuelve exactamente los 3 ids inyectados."""
    resp = client_prueba.get("/api/equipos/aleatorio", params={"tamano": 3})
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()["cazadores"]]
    assert sorted(ids) == ["alfa", "media", "zeta"]


def test_ca2_detalle_cazador_usa_catalogo_inyectado(client_prueba: TestClient) -> None:
    """CA2 (caso limite): el detalle por id busca en el catalogo inyectado, no en el real."""
    resp = client_prueba.get("/api/cazadores/alfa")
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Alfa"

    assert client_prueba.get("/api/cazadores/keeper").status_code == 404


def test_ca2_detalle_griefbound_usa_catalogo_inyectado(client_prueba: TestClient) -> None:
    """CA2 (caso limite): el detalle de Griefbound busca en el catalogo inyectado."""
    resp = client_prueba.get("/api/griefbound/gb-uno")
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Griefbound Uno"

    assert client_prueba.get("/api/griefbound/convergence").status_code == 404


def test_ca2_filtro_tipo_griefbound_sobre_catalogo_inyectado(client_prueba: TestClient) -> None:
    """CA2 (caso limite): el filtro por tipo opera sobre el catalogo inyectado."""
    resp_gb = client_prueba.get("/api/griefbound", params={"tipo": "griefbound"})
    assert resp_gb.status_code == 200
    assert len(resp_gb.json()) == 2

    resp_pr = client_prueba.get("/api/griefbound", params={"tipo": "pretender"})
    assert resp_pr.status_code == 200
    assert resp_pr.json() == []


# ---------------------------------------------------------------------------
# CA3: catalogo insuficiente -> 409, sin unittest.mock.patch
# ---------------------------------------------------------------------------


def test_ca3_catalogo_insuficiente_devuelve_409(client_prueba: TestClient) -> None:
    """CA3: con 3 cazadores, tamano=4 responde 409 con el detail exacto."""
    resp = client_prueba.get("/api/equipos/aleatorio", params={"tamano": 4})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "No hay suficientes cazadores para un equipo de 4"


# ---------------------------------------------------------------------------
# CA4: dos apps en el mismo proceso no comparten estado
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("inyectada_primero", [True, False], ids=["prueba-primero", "real-primero"])
def test_ca4_apps_independientes_en_el_mismo_proceso(
    catalogo_prueba: Catalogo, inyectada_primero: bool
) -> None:
    """CA4: app con catalogo de prueba -> 3 cazadores; app real -> 8, en cualquier orden."""
    if inyectada_primero:
        app_prueba = create_app(catalogo=catalogo_prueba)
        app_real = create_app()
    else:
        app_real = create_app()
        app_prueba = create_app(catalogo=catalogo_prueba)

    datos_prueba = TestClient(app_prueba).get("/api/cazadores").json()
    datos_real = TestClient(app_real).get("/api/cazadores").json()

    assert len(datos_prueba) == 3
    assert len(datos_real) == 8


# ---------------------------------------------------------------------------
# CA5: fallo de carga al arrancar -> create_app propaga ValueError
# ---------------------------------------------------------------------------


def test_ca5_create_app_propaga_value_error_de_cargar_cazadores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA5: si cargar_cazadores lanza ValueError, create_app() lo propaga."""

    def _falla(*_args, **_kwargs):
        raise ValueError("/ruta/secreta/cazadores.json: JSON invalido")

    monkeypatch.setattr(app_mod, "cargar_cazadores", _falla)

    resultado = None
    with pytest.raises(ValueError, match="JSON invalido"):
        resultado = create_app()
    assert resultado is None


def test_ca5_create_app_propaga_value_error_de_cargar_griefbound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA5 (caso limite): un ValueError de cargar_griefbound tambien se propaga."""

    def _falla(*_args, **_kwargs):
        raise ValueError("griefbound.json: JSON invalido")

    monkeypatch.setattr(app_mod, "cargar_griefbound", _falla)

    with pytest.raises(ValueError, match="JSON invalido"):
        create_app()


def test_ca5_catalogo_inyectado_no_invoca_cargadores(
    monkeypatch: pytest.MonkeyPatch, catalogo_prueba: Catalogo
) -> None:
    """CA5 (caso limite): con catalogo inyectado, create_app no llama a los cargadores."""

    def _no_llamar(*_args, **_kwargs):
        raise AssertionError("no debe cargarse el catalogo si se inyecta uno")

    monkeypatch.setattr(app_mod, "cargar_cazadores", _no_llamar)
    monkeypatch.setattr(app_mod, "cargar_griefbound", _no_llamar)

    app = create_app(catalogo=catalogo_prueba)
    assert TestClient(app).get("/api/cazadores").status_code == 200


# ---------------------------------------------------------------------------
# CA6: semilla=42 reproduce exactamente el resultado de main (orden del JSON)
# ---------------------------------------------------------------------------


def test_ca6_semilla_42_identica_a_main() -> None:
    """CA6: tamano=4&semilla=42 devuelve los mismos ids que devolvia main."""
    client = TestClient(create_app())
    resp = client.get("/api/equipos/aleatorio", params={"tamano": 4, "semilla": 42})
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()["cazadores"]]
    assert ids == IDS_SEMILLA_42_TAMANO_4


def test_ca6_catalogo_conserva_orden_del_json() -> None:
    """CA6: el catalogo de create_app() guarda los cazadores en el orden del fichero JSON."""
    ruta = RAIZ / "data" / "cazadores.json"
    ids_json = [c["id"] for c in json.loads(ruta.read_text(encoding="utf-8"))]

    app = create_app()
    catalogo = app.state.catalogo
    assert isinstance(catalogo, Catalogo)
    assert [c.id for c in catalogo.cazadores] == ids_json


# ---------------------------------------------------------------------------
# CA7: obtener_catalogo entrega exactamente el objeto inyectado
# ---------------------------------------------------------------------------


def test_ca7_obtener_catalogo_entrega_el_objeto_inyectado(catalogo_prueba: Catalogo) -> None:
    """CA7: un router de prueba con Depends(obtener_catalogo) recibe X (con 'is')."""
    recibidos: list[Catalogo] = []
    router_prueba = APIRouter()

    @router_prueba.get("/prueba/catalogo")
    def _ruta_prueba(
        catalogo: Catalogo = Depends(obtener_catalogo),  # noqa: B008
    ) -> dict:
        recibidos.append(catalogo)
        return {"cazadores": len(catalogo.cazadores)}

    app = create_app(catalogo=catalogo_prueba)
    app.include_router(router_prueba)

    resp = TestClient(app).get("/prueba/catalogo")
    assert resp.status_code == 200
    assert resp.json() == {"cazadores": 3}
    assert len(recibidos) == 1
    assert recibidos[0] is catalogo_prueba


def test_ca7_catalogo_guardado_en_app_state(catalogo_prueba: Catalogo) -> None:
    """CA7 (caso limite): create_app guarda el catalogo inyectado en app.state.catalogo."""
    app = create_app(catalogo=catalogo_prueba)
    assert isinstance(app, FastAPI)
    assert app.state.catalogo is catalogo_prueba


# ---------------------------------------------------------------------------
# CA8: la API no carga el catalogo ni mantiene estado global
# ---------------------------------------------------------------------------

CARGADORES = {"cargar_cazadores", "cargar_griefbound"}
NOMBRES_GLOBALES_PROHIBIDOS = {
    "init_catalogo",
    "_cazadores_por_id",
    "_cazadores_lista",
    "_griefbound_por_id",
    "_griefbound_lista",
}


def _modulos_api() -> list[Path]:
    modulos = sorted(DIRECTORIO_API.glob("*.py"))
    assert modulos, f"No se encontraron modulos en {DIRECTORIO_API}"
    return modulos


def _nombres_usados(arbol: ast.AST) -> set[str]:
    """Nombres referenciados, importados o definidos en el modulo."""
    nombres: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Name):
            nombres.add(nodo.id)
        elif isinstance(nodo, ast.Attribute):
            nombres.add(nodo.attr)
        elif isinstance(nodo, ast.alias):
            nombres.add(nodo.asname or nodo.name.split(".")[-1])
            nombres.add(nodo.name.split(".")[-1])
        elif isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            nombres.add(nodo.name)
    return nombres


@pytest.mark.parametrize("modulo", _modulos_api(), ids=lambda p: p.name)
def test_ca8_api_no_usa_cargadores_del_catalogo(modulo: Path) -> None:
    """CA8: ningun modulo de api/ llama (ni importa) cargar_cazadores/cargar_griefbound."""
    arbol = ast.parse(modulo.read_text(encoding="utf-8"), filename=str(modulo))
    usados = _nombres_usados(arbol) & CARGADORES
    assert not usados, f"{modulo.name} usa {sorted(usados)}"


@pytest.mark.parametrize("modulo", _modulos_api(), ids=lambda p: p.name)
def test_ca8_api_sin_estado_global_ni_init_catalogo(modulo: Path) -> None:
    """CA8: no existen init_catalogo ni los diccionarios/listas globales del catalogo."""
    arbol = ast.parse(modulo.read_text(encoding="utf-8"), filename=str(modulo))
    usados = _nombres_usados(arbol) & NOMBRES_GLOBALES_PROHIBIDOS
    assert not usados, f"{modulo.name} define o usa {sorted(usados)}"


def test_ca8_modulo_catalogo_api_sin_atributos_globales() -> None:
    """CA8: grimcoven_equipos.api.catalogo no expone init_catalogo ni el estado global."""
    import grimcoven_equipos.api.catalogo as api_catalogo

    presentes = {n for n in NOMBRES_GLOBALES_PROHIBIDOS if hasattr(api_catalogo, n)}
    assert not presentes, f"Siguen existiendo: {sorted(presentes)}"
